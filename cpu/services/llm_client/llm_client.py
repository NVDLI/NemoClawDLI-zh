"""
LLM Client - Multi-Backend OpenAI Router
Simple, traceable, fail-fast design.

Supports OpenAI-compatible backends (NVIDIA Inference API, NIM, OpenAI)
with AWS Bedrock Converse as a translation-layer fallback.

Streaming architecture:
  - OpenAI-compat backends: true passthrough streaming via httpx.stream()
  - Bedrock ConverseStream: true event streaming with a deferred Converse
    fallback when streaming is unavailable for a model.

Span lifecycle:
  - Non-streaming: proxy_request span is ended by the caller's finally block.
  - Streaming: span ownership transfers to the async generator. The caller
    sets span=None so its finally block is a no-op. The generator ends the
    span in its own finally block, guaranteeing cleanup even on disconnect.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from contextlib import asynccontextmanager
from functools import partial, wraps
from typing import Dict, List, Optional, Tuple
import httpx, os, json, logging, asyncio, time, uuid, hashlib
from collections import OrderedDict
from opentelemetry import trace

from observability import get_observability
from bedrock_stream import iter_eventstream, ConverseStreamAccumulator

logger, tracer, propagator, traced = get_observability("llm-client")

SPAN_ATTR_LIMIT = int(os.getenv("LLM_CLIENT_SPAN_ATTR_LIMIT", "8000"))
# Hard cap so a runaway 10MB payload doesn't bloat every trace.
# When this trips, the leading slice is recoverable; the tail is dropped on purpose.
SPAN_ATTR_MAX_CHUNKS = int(os.getenv("LLM_CLIENT_SPAN_ATTR_MAX_CHUNKS", "32"))

def _set_span_text(span, name: str, value, limit: int = SPAN_ATTR_LIMIT):
    """Set a span attribute that may exceed the per-attribute size cap.

    Short strings: set as a single attribute (unchanged behavior).
    Long strings: chunk across `<name>` + `<name>.chunk.1..N-1`, each at
    `limit` chars. Side attributes mark the shape:
        <name>.full_length  : total chars in the original
        <name>.chunks       : total number of chunks (>=2)
        <name>.truncated    : True only if `chunks` would exceed
                              SPAN_ATTR_MAX_CHUNKS; in that case the tail
                              is dropped. When it is absent or False the
                              full payload is reconstructable.

    Reconstruct with:
        attrs = {tag.key: tag.value for tag in span.tags}
        body  = attrs[name]
        for i in range(1, int(attrs.get(f"{name}.chunks", 1))):
            body += attrs[f"{name}.chunk.{i}"]
    """
    text = value if isinstance(value, str) else str(value)
    total = len(text)
    if total <= limit:
        span.set_attribute(name, text)
        return
    chunks_needed = (total + limit - 1) // limit
    chunks_to_write = min(chunks_needed, SPAN_ATTR_MAX_CHUNKS)
    span.set_attribute(name, text[:limit])
    span.set_attribute(f"{name}.full_length", total)
    span.set_attribute(f"{name}.chunks", chunks_to_write)
    for i in range(1, chunks_to_write):
        span.set_attribute(f"{name}.chunk.{i}", text[i * limit:(i + 1) * limit])
    if chunks_to_write < chunks_needed:
        span.set_attribute(f"{name}.truncated", True)

def _set_span_json(span, name: str, value, limit: int = SPAN_ATTR_LIMIT):
    try:
        text = json.dumps(value)
    except TypeError:
        text = json.dumps(str(value))
    _set_span_text(span, name, text, limit)

# ── HTTP client defaults ──────────────────────────────────────────────────
Client = partial(httpx.AsyncClient, timeout=httpx.Timeout(connect=30, read=900, write=120, pool=120))

# ── Global state (computed once on startup) ───────────────────────────────
BACKENDS = {}  # url -> {models: {id -> model_data}, key_env: str}
MODEL_MAP = {}  # model_id -> backend_url
INITIAL_KEYS = {k: os.getenv(k) for k in ["NVIDIA_API_KEY", "OPENAI_API_KEY", "AWS_BEARER_TOKEN_BEDROCK"]}

# ── Bedrock config ────────────────────────────────────────────────────────
BEDROCK_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_BASE_URL = f"https://bedrock-runtime.{BEDROCK_REGION}.amazonaws.com"
BEDROCK_MAX_RETRIES = int(os.getenv("BEDROCK_MAX_RETRIES", "2"))
BEDROCK_RETRY_DELAY = float(os.getenv("BEDROCK_RETRY_DELAY", "1.0"))
BEDROCK_DEFAULT_MAX_TOKENS = int(os.getenv("BEDROCK_DEFAULT_MAX_TOKENS", "16384"))
BEDROCK_MODEL_ALIASES = {
    # Stable learner-facing aliases used by OpenClaw.
    # Keep these stable even when the real Bedrock model revision changes.
    "bedrock-proxy/global.anthropic.claude-sonnet-4-6": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "bedrock-proxy/global.anthropic.claude-opus-4-6-v1": "us.anthropic.claude-opus-4-1-20250805-v1:0",
    "aws/anthropic/bedrock-claude-sonnet-4-6": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "aws/anthropic/bedrock-claude-opus-4-6": "us.anthropic.claude-opus-4-1-20250805-v1:0",
}

def _resolve_bedrock_model(model: str) -> str:
    return BEDROCK_MODEL_ALIASES.get(model or "", model or "")

def _bedrock_proxy_model_records() -> list[dict]:
    if not _is_bedrock_available():
        return []
    records = []
    for model_id in BEDROCK_MODEL_ALIASES:
        records.append({
            "id": model_id,
            "object": "model",
            "owned_by": "bedrock-proxy",
        })
    return records


# Context tracker: link repeated conversation prefixes and record only each request delta.

class ContextTracker:
    """Track conversation context chains across LLM proxy requests."""

    def __init__(self, max_entries: int = 500, ttl: int = 7200):
        self._cache: OrderedDict = OrderedDict()
        self._max = max_entries
        self._ttl = ttl

    # ── Hashing ───────────────────────────────────────────────────────

    @staticmethod
    def _hash_prefix(messages: list, count: int) -> str:
        """Hash first `count` messages deterministically."""
        raw = json.dumps(messages[:count], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _chain_id(messages: list) -> str:
        """Stable conversation identifier: system prompt + first user msg."""
        seed = []
        for m in messages:
            seed.append(m)
            if m.get("role") == "user":
                break
        return hashlib.sha256(
            json.dumps(seed, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:12]

    # ── Cache management ──────────────────────────────────────────────

    def _evict(self):
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v["ts"] > self._ttl]
        for k in expired:
            del self._cache[k]
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)

    # ── Public API ────────────────────────────────────────────────────

    def analyze(self, messages: list, model: str) -> dict:
        """Find longest cached prefix match for the given messages.

        Returns a context dict with cache-hit metadata (or cache_hit=False).
        """
        if not messages:
            return {"cache_hit": False, "turn": 0, "total_messages": 0}

        chain_id = self._chain_id(messages)
        result = {"cache_hit": False, "chain_id": chain_id,
                  "total_messages": len(messages), "turn": 0}

        for k in range(len(messages) - 1, 0, -1):
            h = self._hash_prefix(messages, k)
            if h in self._cache:
                entry = self._cache[h]
                if time.time() - entry["ts"] < self._ttl:
                    self._cache.move_to_end(h)  # LRU touch
                    result.update({
                        "cache_hit": True,
                        "prefix_hash": h,
                        "cached_messages": k,
                        "new_messages": len(messages) - k,
                        "cache_ratio": round(k / len(messages), 3),
                        "parent_trace_id": entry["trace_id"],
                        "parent_span_id": entry["span_id"],
                        "turn": entry.get("turn", 0) + 1,
                        "cum_input_tokens": entry.get("cum_input_tokens", 0),
                        "cum_output_tokens": entry.get("cum_output_tokens", 0),
                    })
                    break
        return result

    def record(self, messages: list, model: str, trace_id: str, span_id: str,
               input_tokens: int = 0, output_tokens: int = 0,
               ctx: Optional[dict] = None):
        """Register this request's context for future prefix matching."""
        if not messages:
            return
        h = self._hash_prefix(messages, len(messages))
        turn = (ctx or {}).get("turn", 0)
        chain_id = (ctx or {}).get("chain_id", self._chain_id(messages))
        self._cache[h] = {
            "trace_id": trace_id,
            "span_id": span_id,
            "chain_id": chain_id,
            "msg_count": len(messages),
            "model": model,
            "turn": turn,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cum_input_tokens": (ctx or {}).get("cum_input_tokens", 0) + input_tokens,
            "cum_output_tokens": (ctx or {}).get("cum_output_tokens", 0) + output_tokens,
            "cache_ratio": (ctx or {}).get("cache_ratio", 0),
            "ts": time.time(),
        }
        self._evict()

    def set_span_attrs(self, span, ctx: dict, messages: list, body_json: dict):
        """Set context-aware attributes on the span.

        On cache hit: stores only the delta messages (not the full request),
        plus chain linkage and cumulative token stats.
        On miss: stores the full request (truncated).
        """
        span.set_attribute("context.chain_id", ctx.get("chain_id", ""))
        span.set_attribute("context.turn", ctx.get("turn", 0))
        span.set_attribute("context.total_messages", ctx.get("total_messages", 0))

        if ctx.get("cache_hit"):
            span.set_attribute("context.cache_hit", True)
            span.set_attribute("context.parent_trace_id", ctx["parent_trace_id"])
            span.set_attribute("context.parent_span_id", ctx["parent_span_id"])
            span.set_attribute("context.cached_messages", ctx["cached_messages"])
            span.set_attribute("context.new_messages", ctx["new_messages"])
            span.set_attribute("context.cache_ratio", ctx["cache_ratio"])
            span.set_attribute("context.cum_input_tokens", ctx["cum_input_tokens"])
            span.set_attribute("context.cum_output_tokens", ctx["cum_output_tokens"])

            # Store only delta (new messages since prefix)
            delta = messages[ctx["cached_messages"]:]
            delta_body = {k: v for k, v in body_json.items() if k != "messages"}
            delta_body["messages"] = delta
            delta_json = json.dumps(delta_body)
            _set_span_text(span, "request.delta", delta_json)
            span.set_attribute("request.full_size", len(json.dumps(body_json)))
            span.set_attribute("request.delta_size", len(delta_json))
            if len(delta_json) > 8000:
                span.set_attribute("request.delta_truncated", True)
        else:
            span.set_attribute("context.cache_hit", False)
            req_json = json.dumps(body_json)
            _set_span_text(span, "request", req_json)
            if len(req_json) > 8000:
                span.set_attribute("request.truncated", True)
                span.set_attribute("request.full_size", len(req_json))

    def chains(self) -> list[dict]:
        """Group cache entries by chain_id into conversation chains.

        Returns a list of chains sorted by last activity, each containing
        an ordered list of turns with trace linkage and token accounting.
        """
        by_chain: dict[str, list[dict]] = {}
        now = time.time()
        for h, entry in self._cache.items():
            if now - entry["ts"] > self._ttl:
                continue
            cid = entry.get("chain_id", "unknown")
            by_chain.setdefault(cid, []).append({**entry, "prefix_hash": h})

        result = []
        for cid, entries in by_chain.items():
            entries.sort(key=lambda e: e["turn"])
            latest = entries[-1]
            # Build per-turn token series
            token_series = [{
                "turn": e["turn"],
                "input_tokens": e.get("input_tokens", 0),
                "output_tokens": e.get("output_tokens", 0),
                "cum_input": e["cum_input_tokens"],
                "cum_output": e["cum_output_tokens"],
                "cache_ratio": e.get("cache_ratio", 0),
                "msg_count": e["msg_count"],
                "model": e["model"],
                "trace_id": e["trace_id"],
                "span_id": e["span_id"],
                "ts": e["ts"],
            } for e in entries]
            result.append({
                "chain_id": cid,
                "turns": len(entries),
                "model": latest["model"],
                "cum_input_tokens": latest["cum_input_tokens"],
                "cum_output_tokens": latest["cum_output_tokens"],
                "cum_total_tokens": latest["cum_input_tokens"] + latest["cum_output_tokens"],
                "last_active": latest["ts"],
                "latest_trace_id": latest["trace_id"],
                "avg_cache_ratio": round(
                    sum(e.get("cache_ratio", 0) for e in entries) / len(entries), 3
                ) if entries else 0,
                "series": token_series,
            })
        result.sort(key=lambda c: c["last_active"], reverse=True)
        return result

    def chain_detail(self, chain_id: str) -> Optional[dict]:
        """Get a single chain by ID, or None."""
        for c in self.chains():
            if c["chain_id"] == chain_id:
                return c
        return None

    @property
    def stats(self) -> dict:
        """Return cache stats for the debug endpoint."""
        chains = self.chains()
        total_input = sum(c["cum_input_tokens"] for c in chains)
        total_output = sum(c["cum_output_tokens"] for c in chains)
        return {
            "entries": len(self._cache),
            "max": self._max,
            "ttl": self._ttl,
            "active_chains": len(chains),
            "total_turns": sum(c["turns"] for c in chains),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
        }

import threading

class CompletionLog:
    """Streaming-aware completion tracker with in-flight visibility.

    Lifecycle: start() → stream_update() (0..N) → finish()
    In-flight requests are visible immediately via recent().
    SSE subscribers get real-time start/update/done events.
    """
    def __init__(self, max_size: int = 100):
        self._buf = []          # completed entries
        self._inflight = {}     # req_id -> entry (active requests)
        self._seq = 0
        self._lock = threading.Lock()
        self._max = max_size
        self._sse_queues = []   # list of queue.Queue for SSE subscribers

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _push_sse(self, event_type: str, data: dict):
        """Push event to all SSE subscribers (non-blocking)."""
        import queue as _queue
        dead = []
        for q in self._sse_queues:
            try:
                q.put_nowait({"event": event_type, "data": data})
            except _queue.Full:
                dead.append(q)
        for q in dead:
            try: self._sse_queues.remove(q)
            except ValueError: pass

    def start(self, req_id: str, model: str, session_key: str = "", 
            chain_id: str = "", trace_id: str = "", backend: str = "",
            input_tokens: int = 0, caller: str = "", ) -> dict:
        """Mark a request as in-flight. Call before the upstream request."""
        with self._lock:
            entry = {
                "req_id": req_id,
                "seq": self._next_seq(),
                "ts": time.time(),
                "model": model,
                "session_key": session_key,
                "chain_id": chain_id,
                "caller": caller or "",
                "trace_id": trace_id,
                "backend": backend,
                "response_id": "",
                "input_tokens": input_tokens,
                "output_tokens": 0,
                "elapsed_ms": 0,
                "status": "inflight",
                "content_preview": "",
                "response": None,
            }
            self._inflight[req_id] = entry
            self._push_sse("start", {
                "req_id": req_id, 
                "model": model, 
                "session_key": session_key,
                "chain_id": chain_id,
                "backend": backend, 
                "response_id": "", 
                "ts": entry["ts"],
                "input_tokens": input_tokens,
            })
            return entry

    def stream_update(self, req_id: str, content_delta: str = "",
                      output_tokens: int = 0,
                      tool_call_delta: Optional[dict] = None):
        """Update an in-flight request with streaming content or tool call progress."""
        with self._lock:
            entry = self._inflight.get(req_id)
            if not entry:
                return
            if content_delta:
                entry["content_preview"] = (entry.get("content_preview", "") + content_delta)
            if tool_call_delta:
                tc_list = entry.setdefault("tool_calls_inflight", [])
                idx = tool_call_delta.get("index", 0)
                while len(tc_list) <= idx:
                    tc_list.append({"name": "", "arguments": ""})
                fn = tool_call_delta.get("function", {})
                if fn.get("name"):
                    tc_list[idx]["name"] = fn["name"]
                if fn.get("arguments"):
                    tc_list[idx]["arguments"] += fn["arguments"]
                # Build a tool preview string for the dashboard
                tool_preview = " | ".join(
                    f"⚙ {tc['name']}({tc['arguments']}…)" if len(tc['arguments']) > 120
                    else f"⚙ {tc['name']}({tc['arguments']})"
                    for tc in tc_list if tc["name"]
                )
                entry["tool_preview"] = tool_preview[:300] + "..." + tool_preview[-200:]
            if output_tokens:
                entry["output_tokens"] = output_tokens
            entry["elapsed_ms"] = int((time.time() - entry["ts"]) * 1000)
            self._push_sse("update", {
                "req_id": req_id,
                "response_id": entry.get("response_id", ""),
                "content_delta": content_delta,
                "content_preview": entry["content_preview"],
                "tool_preview": entry.get("tool_preview", ""),
                "tool_calls_inflight": entry.get("tool_calls_inflight", []),
                "output_tokens": entry["output_tokens"],
                "elapsed_ms": entry["elapsed_ms"],
            })

    def set_response_id(self, req_id: str, response_id: str):
        """Set the upstream response ID once known (first chunk or final response)."""
        with self._lock:
            entry = self._inflight.get(req_id)
            if entry and not entry.get("response_id"):
                entry["response_id"] = response_id
                self._push_sse("update", {
                    "req_id": req_id,
                    "response_id": response_id,
                })

    @staticmethod
    def _content_preview_from_response(response: dict) -> str:
        """Extract preview text from Chat Completions or Responses objects."""
        try:
            msg = (response.get("choices", [{}])[0].get("message") or {})
            content = msg.get("content")
            if isinstance(content, str):
                return content
        except (IndexError, AttributeError):
            pass
        try:
            parts = []
            for output in response.get("output", []) or []:
                for block in output.get("content", []) or []:
                    if block.get("type") == "output_text":
                        parts.append(block.get("text", ""))
            if parts:
                return "".join(parts)
        except AttributeError:
            pass
        try:
            return _converse_text(response)
        except Exception:
            return ""

    def finish(self, req_id: str, input_tokens: int = 0, output_tokens: int = 0,
               elapsed_ms: int = 0, response: Optional[dict] = None):
        """Move request from inflight to completed buffer."""
        with self._lock:
            entry = self._inflight.pop(req_id, None)
            if entry is None:
                # Was never started (edge case). Create the completed entry directly.
                entry = {
                    "req_id": req_id,
                    "seq": self._next_seq(),
                    "ts": time.time(),
                    "model": "?",
                    "session_key": "",
                    "chain_id": "",
                    "trace_id": "",
                    "backend": "",
                    "response_id": "",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "elapsed_ms": 0,
                    "status": "done",
                    "content_preview": "",
                    "response": None,
                }
            entry["status"] = "done"
            if input_tokens:
                entry["input_tokens"] = input_tokens
            if output_tokens:
                entry["output_tokens"] = output_tokens
            if elapsed_ms:
                entry["elapsed_ms"] = elapsed_ms
            else:
                entry["elapsed_ms"] = int((time.time() - entry["ts"]) * 1000)
            if response:
                entry["response"] = response
                # Extract content preview from response if not already set
                if not entry.get("content_preview"):
                    entry["content_preview"] = self._content_preview_from_response(response)
                if response.get("id") and not entry.get("response_id"):
                    entry["response_id"] = response["id"]
            entry["seq"] = self._next_seq()  # Re-sequence for ordering
            self._buf.append(entry)
            if len(self._buf) > self._max:
                self._buf = self._buf[-self._max:]
            self._push_sse("done", {
                "req_id": req_id,
                "response_id": entry.get("response_id", ""),
                "model": entry["model"],
                "session_key": entry["session_key"],
                "chain_id": entry["chain_id"],
                "input_tokens": entry["input_tokens"],
                "output_tokens": entry["output_tokens"],
                "elapsed_ms": entry["elapsed_ms"],
                "backend": entry["backend"],
                "ts": entry["ts"],
                "content_preview": entry.get("content_preview", ""),
            })

    def record(self, model: str, input_tokens: int, output_tokens: int,
               chain_id: str = "", trace_id: str = "", elapsed_ms: int = 0,
               response: Optional[dict] = None, backend: str = ""):
        """Legacy compatibility path. Records a completed entry directly with no inflight phase."""
        req_id = f"legacy-{time.time()}-{self._seq}"
        with self._lock:
            self._seq += 1
            entry = {
                "req_id": req_id,
                "seq": self._seq,
                "ts": time.time(),
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "chain_id": chain_id,
                "trace_id": trace_id,
                "elapsed_ms": elapsed_ms,
                "backend": backend,
                "response_id": "",
                "status": "done",
                "content_preview": "",
                "response": response,
            }
            if response:
                entry["content_preview"] = self._content_preview_from_response(response)
            self._buf.append(entry)
            if len(self._buf) > self._max:
                self._buf = self._buf[-self._max:]

    def recent(self, after_seq: int = 0) -> dict:
        """Return completed + inflight entries."""
        with self._lock:
            completed = [e for e in self._buf if e["seq"] > after_seq]
            inflight = []
            now = time.time()
            for e in self._inflight.values():
                entry = dict(e)  # shallow copy to avoid mutation
                entry["elapsed_ms"] = int((now - entry["ts"]) * 1000)
                inflight.append(entry)
            return {
                "completions": completed,
                "inflight": inflight,
                "latest_seq": self._seq,
            }

    def subscribe_sse(self):
        """Return a queue.Queue that receives SSE events."""
        import queue as _queue
        q = _queue.Queue(maxsize=200)
        with self._lock:
            self._sse_queues.append(q)
        return q

    def unsubscribe_sse(self, q):
        with self._lock:
            try: self._sse_queues.remove(q)
            except ValueError: pass

ctx_tracker = ContextTracker()
completion_log = CompletionLog()

def get_missing_model_msg(model):
    return {"error": {
        "message": f"The model \'{model}\' does not exist",
        "type": "invalid_request_error",
        "param": "model",
        "code": "model_not_found"}}

# ── Backend configs (static, validated on startup) ────────────────────────
BACKEND_CONFIGS = [
    {
        "url": "https://inference-api.nvidia.com/v1",
        "key_env": "NVINFR_API_KEY",
        "exclude": [],
    },
    {
        "url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
        "exclude": [],
    },
    {"url": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY", "exclude": []},
]

# =============================================================================
# BEDROCK CONVERSE TRANSLATION
# =============================================================================

def _coerce_text(content) -> str:
    """Safely coerce content to a string. Handles None, str, list, dict."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def _openai_content_to_bedrock_blocks(content) -> list:
    """Convert OpenAI content (str or array) to Bedrock content blocks."""
    if content is None:
        return []
    if isinstance(content, str):
        if content.strip():
            return [{"text": content}]
        return []
    if isinstance(content, list):
        blocks = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    blocks.append({"text": item})
            elif isinstance(item, dict):
                t = item.get("type", "text")
                if t == "text":
                    text = item.get("text", "")
                    if text.strip():
                        blocks.append({"text": text})
                elif t == "image_url":
                    url = item.get("image_url", {}).get("url", "")
                    if url.startswith("data:"):
                        try:
                            header, b64data = url.split(",", 1)
                            media_type = header.split(":")[1].split(";")[0]
                            blocks.append({
                                "image": {
                                    "format": media_type.split("/")[1] if "/" in media_type else "png",
                                    "source": {"bytes": b64data}
                                }
                            })
                        except (ValueError, IndexError):
                            logger.warning("Could not parse data URI for image")
                    else:
                        logger.warning("Bedrock Converse does not support URL-based images, skipping")
        return blocks
    text = str(content)
    if text.strip():
        return [{"text": text}]
    return []


def _openai_tools_to_bedrock(tools: list) -> dict:
    bedrock_tools = []
    for tool in tools:
        fn = tool.get("function", {})
        spec = {"name": fn.get("name", ""), "description": fn.get("description", "")}
        params = fn.get("parameters")
        if params:
            spec["inputSchema"] = {"json": params}
        bedrock_tools.append({"toolSpec": spec})
    if not bedrock_tools:
        return {}
    return {"toolConfig": {"tools": bedrock_tools}}


def _openai_tool_choice_to_bedrock(tool_choice, tool_config: dict) -> dict:
    if not tool_choice or not tool_config:
        return tool_config
    if isinstance(tool_choice, str):
        if tool_choice == "none":
            return {}
        elif tool_choice == "required":
            tool_config["toolChoice"] = {"any": {}}
        elif tool_choice == "auto":
            tool_config["toolChoice"] = {"auto": {}}
    elif isinstance(tool_choice, dict):
        fn = tool_choice.get("function", {})
        name = fn.get("name", "")
        if name:
            tool_config["toolChoice"] = {"tool": {"name": name}}
    return tool_config


def _merge_consecutive_roles(messages: list) -> list:
    if not messages:
        return messages
    merged = [messages[0]]
    for msg in messages[1:]:
        if msg["role"] == merged[-1]["role"]:
            merged[-1]["content"].extend(msg["content"])
        else:
            merged.append(msg)
    return merged


def _openai_to_bedrock(body: dict) -> dict:
    """Translate OpenAI chat completion request to Bedrock Converse format."""
    messages = body.get("messages", [])
    bedrock_messages, system_parts = [], []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if role == "system":
            text = _coerce_text(content)
            if text.strip():
                system_parts.append({"text": text})
            continue

        if role == "tool":
            text = _coerce_text(content)
            tool_result_block = {
                "toolResult": {
                    "toolUseId": msg.get("tool_call_id", ""),
                    "content": [{"text": text if text else "(empty)"}]
                }
            }
            if bedrock_messages and bedrock_messages[-1]["role"] == "user":
                bedrock_messages[-1]["content"].append(tool_result_block)
            else:
                bedrock_messages.append({"role": "user", "content": [tool_result_block]})
            continue

        if role == "assistant" and (msg.get("tool_calls") or msg.get("reasoning_content")):
            content_blocks = []
            # Reasoning blocks must come FIRST in Anthropic's block ordering when present.
            # Without a signature we can't safely round-trip (Anthropic rejects unsigned reasoning), so drop in that case.
            r_text = msg.get("reasoning_content")
            r_sig = msg.get("reasoning_signature")
            if r_text and r_sig:
                content_blocks.append({"reasoningContent": {
                    "reasoningText": {"text": r_text, "signature": r_sig}
                }})
            elif r_text and not r_sig:
                logger.warning(
                    "dropping assistant.reasoning_content with no reasoning_signature; "
                    "Bedrock would reject this block (Anthropic requires signed thinking)"
                )
            text = _coerce_text(content)
            if text.strip():
                content_blocks.append({"text": text})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                try:
                    tool_input = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    tool_input = {}
                content_blocks.append({
                    "toolUse": {
                        "toolUseId": tc.get("id", str(uuid.uuid4())),
                        "name": fn.get("name", ""),
                        "input": tool_input
                    }
                })
            if content_blocks:
                bedrock_messages.append({"role": "assistant", "content": content_blocks})
            continue

        content_blocks = _openai_content_to_bedrock_blocks(content)
        if not content_blocks:
            continue
        bedrock_messages.append({"role": role, "content": content_blocks})

    bedrock_messages = _merge_consecutive_roles(bedrock_messages)
    if not bedrock_messages:
        bedrock_messages = [{"role": "user", "content": [{"text": "(empty)"}]}]

    result = {"messages": bedrock_messages}
    if system_parts:
        result["system"] = system_parts

    config = {}
    if "max_tokens" in body:
        config["maxTokens"] = body["max_tokens"]
    elif "max_completion_tokens" in body:
        config["maxTokens"] = body["max_completion_tokens"]
    else:
        config["maxTokens"] = BEDROCK_DEFAULT_MAX_TOKENS
    if "temperature" in body:
        config["temperature"] = body["temperature"]
    if "top_p" in body:
        config["topP"] = body["top_p"]
    if "stop" in body:
        stop = body["stop"]
        if isinstance(stop, str):
            config["stopSequences"] = [stop]
        elif isinstance(stop, list):
            config["stopSequences"] = stop
    if config:
        result["inferenceConfig"] = config

    tools = body.get("tools")
    if tools:
        tool_config = _openai_tools_to_bedrock(tools)
        tool_choice = body.get("tool_choice")
        if tool_choice:
            tool_config = _openai_tool_choice_to_bedrock(tool_choice, tool_config)
        if tool_config:
            result.update(tool_config)

    # Anthropic thinking pass-through. Caller config wins; the env default only fills silent Anthropic chats.
    BUDGETS = {"low": 2000, "medium": 8000, "high": 32000}

    amrf: dict = {}
    caller_specified_reasoning = False

    raw_passthrough = body.get("additional_model_request_fields")
    if isinstance(raw_passthrough, dict):
        amrf.update(raw_passthrough)
        caller_specified_reasoning = True

    if "thinking" in body and isinstance(body["thinking"], dict):
        amrf["thinking"] = body["thinking"]
        caller_specified_reasoning = True

    if "reasoning_effort" in body:
        caller_specified_reasoning = True
        re = body.get("reasoning_effort")
        if isinstance(re, str) and "thinking" not in amrf:
            b = BUDGETS.get(re.lower())
            if b is not None:
                amrf["thinking"] = {"type": "enabled", "budget_tokens": b}

    # Default only for plain Anthropic chats; tool exchanges stay text-first or Bedrock 400s.
    msgs = body.get("messages") or []
    is_tool_exchange = bool(body.get("tools")) or any(
        isinstance(m, dict) and (m.get("role") == "tool" or m.get("tool_calls")) for m in msgs)
    if not caller_specified_reasoning and not is_tool_exchange:
        model_name = body.get("model") or ""
        if isinstance(model_name, str) and "anthropic" in model_name.lower():
            default = os.environ.get("LLM_CLIENT_BEDROCK_DEFAULT_REASONING", "").lower()
            b = BUDGETS.get(default)
            if b is not None:
                amrf["thinking"] = {"type": "enabled", "budget_tokens": b}

    if amrf:
        result["additionalModelRequestFields"] = amrf
        # Bedrock counts thinking inside max_tokens; leave answer headroom.
        budget = (amrf.get("thinking") or {}).get("budget_tokens", 0)
        if isinstance(budget, int) and budget > 0:
            current_max = result.get("inferenceConfig", {}).get("maxTokens", 0)
            min_required = budget + 1024  # leave headroom for the answer
            if current_max < min_required:
                result.setdefault("inferenceConfig", {})["maxTokens"] = min_required

    return result


def _bedrock_to_openai(resp: dict, model: str) -> dict:
    """Translate Bedrock Converse response to OpenAI chat completion format."""
    output = resp.get("output", {}).get("message", {})
    content_blocks = output.get("content", [])
    usage = resp.get("usage", {})
    stop = resp.get("stopReason", "end_turn")
    finish_map = {"end_turn": "stop", "max_tokens": "length", "stop_sequence": "stop",
                  "tool_use": "tool_calls"}

    text_parts = []
    tool_calls = []
    reasoning_text = None
    reasoning_signature = None
    for block in content_blocks:
        if "text" in block:
            text_parts.append(block["text"])
        elif "toolUse" in block:
            tu = block["toolUse"]
            tool_calls.append({
                "id": tu.get("toolUseId", f"call_{uuid.uuid4().hex[:8]}"),
                "type": "function",
                "function": {
                    "name": tu.get("name", ""),
                    "arguments": json.dumps(tu.get("input", {}))
                }
            })
        elif "reasoningContent" in block:
            # Accept both Bedrock reasoningContent shapes.
            rc = block["reasoningContent"]
            if isinstance(rc, dict) and "reasoningText" in rc:
                rt = rc["reasoningText"] or {}
                reasoning_text = rt.get("text") or reasoning_text
                reasoning_signature = rt.get("signature") or reasoning_signature
            elif isinstance(rc, dict):
                reasoning_text = rc.get("text") or reasoning_text
                reasoning_signature = rc.get("signature") or reasoning_signature

    text = "".join(text_parts)
    message = {"role": "assistant", "content": text or None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    # Keep reasoning text/signature visible and round-trippable.
    if reasoning_text:
        message["reasoning_content"] = reasoning_text
    if reasoning_signature:
        message["reasoning_signature"] = reasoning_signature

    choice = {"index": 0, "message": message,
              "finish_reason": finish_map.get(stop, "stop")}

    return {
        "id": f"bedrock-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [choice],
        "usage": {"prompt_tokens": usage.get("inputTokens", 0),
                  "completion_tokens": usage.get("outputTokens", 0),
                  "total_tokens": usage.get("totalTokens", 0)}
    }


def _is_bedrock_available() -> bool:
    return bool(os.getenv("AWS_BEARER_TOKEN_BEDROCK"))


# Route only ids that look like Bedrock names; unknown ids should fail cleanly here.
_BEDROCK_PREFIXES = ("bedrock-proxy/", "aws/")
_BEDROCK_PATTERN_HINTS = (
    "global.anthropic.",
    "us.anthropic.",
    "eu.anthropic.",
    "apac.anthropic.",
)


def _is_bedrock_routable(model) -> bool:
    """True if `model` looks like a Bedrock model identifier.

    We allow our prefixed aliases (bedrock-proxy/..., aws/...) and the
    raw Bedrock id shapes (global.anthropic.foo, us.anthropic.foo, etc.).
    Arbitrary unknown names are *not* routed to Bedrock. Without this
    guard the AWS endpoint can return a 200 with empty content for bogus
    model names, producing a fake-success response that is worse than a
    clean 4xx."""
    if not isinstance(model, str) or not model:
        return False
    if model in BEDROCK_MODEL_ALIASES:
        return True
    if any(model.startswith(p) for p in _BEDROCK_PREFIXES):
        return True
    if any(h in model for h in _BEDROCK_PATTERN_HINTS):
        return True
    return False


def _is_retryable_status(status_code: int) -> bool:
    return status_code in (429, 500, 502, 503, 529)


# =============================================================================
# BEDROCK CONVERSE. Retries, translates, and streams the upstream call.
# =============================================================================

async def _bedrock_converse(
    bedrock_body: dict,
    model: str,
    converse_url: str,
    headers: dict,
) -> Tuple[Optional[httpx.Response], Optional[dict]]:
    """Execute Bedrock Converse with retries.

    Returns:
        (httpx.Response, None) on success
        (None, error_info) on failure, where error_info = {
            "status": int,
            "body": dict   # OpenAI-shaped error envelope
        }

    Does NOT touch spans. The caller is responsible for all tracing.
    """
    for attempt in range(BEDROCK_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600)) as c:
                r = await c.post(
                    url=converse_url,
                    content=json.dumps(bedrock_body).encode(),
                    headers=headers,
                )

            if r.status_code == 200:
                return r, None

            logger.warning(
                f"Bedrock request failed (attempt {attempt + 1}/{BEDROCK_MAX_RETRIES + 1}): "
                f"status={r.status_code} model={model} body={r.text}"
            )

            if _is_retryable_status(r.status_code) and attempt < BEDROCK_MAX_RETRIES:
                await asyncio.sleep(BEDROCK_RETRY_DELAY * (2 ** attempt))
                continue

            return None, {
                "status": r.status_code if r.status_code >= 400 else 502,
                "body": {"error": {
                    "message": f"Bedrock returned {r.status_code}: {r.text}",
                    "type": "upstream_error", "param": None,
                    "code": f"bedrock_{r.status_code}",
                }},
            }

        except httpx.TimeoutException as e:
            logger.warning(f"Bedrock timeout (attempt {attempt + 1}/{BEDROCK_MAX_RETRIES + 1}): {e}")
            if attempt < BEDROCK_MAX_RETRIES:
                await asyncio.sleep(BEDROCK_RETRY_DELAY * (2 ** attempt))
                continue
            return None, {
                "status": 504,
                "body": {"error": {
                    "message": f"Bedrock request timed out after {BEDROCK_MAX_RETRIES + 1} attempts",
                    "type": "timeout_error", "param": None, "code": "bedrock_timeout",
                }},
            }

        except httpx.ConnectError as e:
            logger.error(f"Bedrock connection error: {e}")
            return None, {
                "status": 502,
                "body": {"error": {
                    "message": f"Could not connect to Bedrock: {e}",
                    "type": "connection_error", "param": None,
                    "code": "bedrock_connection_error",
                }},
            }

    # Should be unreachable, but be safe
    return None, {
        "status": 502,
        "body": {"error": {"message": "Exhausted retries", "type": "upstream_error",
                           "param": None, "code": "bedrock_exhausted"}},
    }


def _bedrock_openai_sse(openai_resp: dict, model: str) -> list[bytes]:
    """Build SSE byte frames from a complete OpenAI-translated response."""
    cid = openai_resp["id"]
    msg = openai_resp["choices"][0]["message"]
    finish = openai_resp["choices"][0].get("finish_reason", "stop")

    delta = {"role": "assistant"}
    if msg.get("content"):
        delta["content"] = msg["content"]
    if msg.get("tool_calls"):
        delta["tool_calls"] = msg["tool_calls"]

    return [
        f"data: {json.dumps({'id': cid, 'object': 'chat.completion.chunk', 'model': model, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]})}\n\n".encode(),
        f"data: {json.dumps({'id': cid, 'object': 'chat.completion.chunk', 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}], 'usage': openai_resp.get('usage')})}\n\n".encode(),
        b"data: [DONE]\n\n",
    ]


async def proxy_bedrock(body_json: dict, model: str, stream: bool, span, ctx: dict, caller: str = "", session_key: str = "") -> Response:
    """Proxy OpenAI-format request to Bedrock Converse.

    Non-streaming: blocks on Converse, translates, returns Response.
        Span lifecycle: caller owns span (ends it in its own finally).

    Streaming: returns StreamingResponse immediately. The Bedrock call
        runs inside the async generator so HTTP 200 headers flow back
        before Bedrock starts processing.
        Span lifecycle: generator owns span (ends it in try/finally).
    """
    key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
    # ── In-flight tracking ────────────────────────────────────────────
    _req_id = f"bedrock-{uuid.uuid4().hex[:12]}"
    completion_log.start(
        req_id=_req_id, model=model,
        session_key=session_key,
        chain_id=ctx.get("chain_id", ""),
        trace_id="",  # filled after span is available
        backend="bedrock",
        input_tokens=len(json.dumps(body_json.get("messages", []))) // 4,  # rough estimate
        caller=caller,
    )
    requested_model = model
    bedrock_model = _resolve_bedrock_model(model)
    if bedrock_model != requested_model:
        logger.info(f"Bedrock alias resolved: {requested_model} -> {bedrock_model}")
        body_json = dict(body_json)
        body_json["model"] = bedrock_model

    bedrock_body = _openai_to_bedrock(body_json)
    converse_url = f"{BEDROCK_BASE_URL}/model/{bedrock_model}/converse"
    converse_headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # ── Shared: call Converse, translate, record on span ──────────────
    async def _call_and_translate(owner_span) -> Tuple[Optional[dict], Optional[list]]:
        """Call Bedrock, translate response, set span attributes.

        Returns:
            (openai_resp, sse_frames) on success
            (None, sse_error_frames) on failure

        Always sets status_code + content/error on owner_span.
        Creates a child dispatch_span that wraps the actual Bedrock call.
        """
        # Wrap the real Bedrock call and keep the parent link across StreamingResponse boundaries.
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
        parent_ctx = trace.set_span_in_context(owner_span)
        dispatch_span = tracer.start_span(
            "upstream_dispatch",
            context=parent_ctx,
        )
        dispatch_span.set_attribute("bedrock.url", converse_url)
        dispatch_span.set_attribute("bedrock.model", bedrock_model)
        dispatch_span.set_attribute("bedrock.stream", stream)
        _set_span_json(dispatch_span, "bedrock.request_body", bedrock_body)

        t0 = time.monotonic()
        logger.info(f"Bedrock converse start: model={model} stream={stream} msg_count={len(bedrock_body.get('messages', []))}")
        r, err = await _bedrock_converse(bedrock_body, bedrock_model, converse_url, converse_headers)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if err:
            dispatch_span.set_attribute("status_code", err["status"])
            _set_span_json(dispatch_span, "error", err["body"])
            dispatch_span.set_status(trace.StatusCode.ERROR, err["body"]["error"]["message"])
            dispatch_span.end()

            owner_span.set_attribute("status_code", err["status"])
            _set_span_json(owner_span, "error", err["body"])
            owner_span.set_status(trace.StatusCode.ERROR, err["body"]["error"]["message"])
            error_frames = [
                f"data: {json.dumps(err['body'])}\n\n".encode(),
                b"data: [DONE]\n\n",
            ]
            return None, error_frames

        try:
            bedrock_resp = r.json()
            openai_resp = _bedrock_to_openai(bedrock_resp, requested_model)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse Bedrock response: {e}, body={r.text}")
            parse_err = {"error": {"message": f"Failed to parse Bedrock response: {e}",
                                   "type": "parse_error", "param": None,
                                   "code": "bedrock_parse_error"}}
            dispatch_span.set_attribute("status_code", 502)
            dispatch_span.set_attribute("error", f"Parse error: {e}")
            dispatch_span.set_status(trace.StatusCode.ERROR, f"Failed to parse Bedrock response: {e}")
            dispatch_span.end()

            owner_span.set_attribute("status_code", 502)
            _set_span_json(owner_span, "error", parse_err)
            owner_span.set_status(trace.StatusCode.ERROR, f"Failed to parse Bedrock response: {e}")
            error_frames = [
                f"data: {json.dumps(parse_err)}\n\n".encode(),
                b"data: [DONE]\n\n",
            ]
            return None, error_frames

        # ── Structured attributes (small, always visible in an OTEL viewer) ───
        usage = bedrock_resp.get("usage", {})
        stop_reason = bedrock_resp.get("stopReason", "")
        latency = bedrock_resp.get("metrics", {}).get("latencyMs", elapsed_ms)
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)

        for s in (dispatch_span, owner_span):
            s.set_attribute("status_code", 200)
            s.set_attribute("bedrock.input_tokens", input_tokens)
            s.set_attribute("bedrock.output_tokens", output_tokens)
            s.set_attribute("bedrock.total_tokens", input_tokens + output_tokens)
            s.set_attribute("bedrock.stop_reason", stop_reason)
            s.set_attribute("bedrock.latency_ms", latency)

        dispatch_span.set_status(trace.StatusCode.OK)
        dispatch_span.end()
        # Force-flush to ensure child span is exported before generator may exit
        try:
            from opentelemetry.sdk.trace import TracerProvider as _TP
            provider = trace.get_tracer_provider()
            if isinstance(provider, _TP):
                provider.force_flush(timeout_millis=2000)
        except Exception:
            pass

        owner_span.set_status(trace.StatusCode.OK)

        # Store long response bodies with chunking so OTel caps do not truncate them.
        _set_span_json(owner_span, "bedrock.response", bedrock_resp)
        _set_span_text(owner_span, "content", json.dumps(openai_resp))

        # ── Record in context chain ───────────────────────────────────
        messages = body_json.get("messages", [])
        ctx_tracker.record(
            messages, model,
            format(owner_span.context.trace_id, '032x'),
            format(owner_span.context.span_id, '016x'),
            input_tokens, output_tokens, ctx,
        )

        completion_log.finish(
            req_id=_req_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_ms=elapsed_ms,
            response=openai_resp,
        )

        sse_frames = _bedrock_openai_sse(openai_resp, requested_model)
        return openai_resp, sse_frames

    # ── Non-streaming path ────────────────────────────────────────────
    if not stream:
        openai_resp, sse_frames = await _call_and_translate(span)
        if openai_resp is None:
            # On error, finish the inflight entry.
            completion_log.finish(req_id=_req_id, elapsed_ms=0)
            # sse_frames[0] contains the error JSON as SSE, extract raw body
            error_json = sse_frames[0].decode().removeprefix("data: ").strip()
            status = 502
            try:
                err_parsed = json.loads(error_json)
                # Recover original status from the error message
                msg = err_parsed.get("error", {}).get("code", "")
                if msg.startswith("bedrock_") and msg[8:].isdigit():
                    status = int(msg[8:])
            except (json.JSONDecodeError, ValueError):
                pass
            return Response(content=error_json.encode(), status_code=status,
                            media_type="application/json")
        return Response(content=json.dumps(openai_resp).encode(), status_code=200,
                        media_type="application/json")

    # ── Streaming path. ConverseStream with deferred fallback ─────────
    converse_stream_url = f"{BEDROCK_BASE_URL}/model/{bedrock_model}/converse-stream"

    async def _real_stream():
        """True streaming via ConverseStream. Falls back to deferred Converse
        if ConverseStream returns non-200 (model doesn't support it)."""
        t0 = time.monotonic()
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
        parent_ctx = trace.set_span_in_context(span)
        dispatch_span = tracer.start_span("upstream_dispatch", context=parent_ctx)
        dispatch_span.set_attribute("bedrock.url", converse_stream_url)
        dispatch_span.set_attribute("bedrock.model", bedrock_model)
        dispatch_span.set_attribute("bedrock.stream", True)
        _set_span_json(dispatch_span, "bedrock.request_body", bedrock_body)

        acc = ConverseStreamAccumulator(model)
        fallback = False
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600)) as client:
                async with client.stream(
                    "POST", url=converse_stream_url,
                    content=json.dumps(bedrock_body).encode(),
                    headers=converse_headers,
                ) as response:
                    dispatch_span.set_attribute("status_code", response.status_code)
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.warning(f"ConverseStream {response.status_code} for {model}, falling back")
                        dispatch_span.set_attribute("error", f"ConverseStream {response.status_code}")
                        dispatch_span.set_status(trace.StatusCode.ERROR, f"ConverseStream {response.status_code}")
                        dispatch_span.end()
                        fallback = True
                    else:
                        async for event_type, body in iter_eventstream(response):
                            if event_type == "error":
                                err_msg = body.get("message", str(body))
                                logger.error(f"Bedrock stream error: {err_msg}")
                                for s in (dispatch_span, span):
                                    s.set_attribute("error", err_msg)
                                    s.set_status(trace.StatusCode.ERROR, err_msg)
                                completion_log.finish(req_id=_req_id, elapsed_ms=int((time.monotonic() - t0) * 1000))
                                yield f"data: {json.dumps({'error': {'message': err_msg, 'type': 'upstream_error'}})}\n\n".encode()
                                yield b"data: [DONE]\n\n"
                                return
                            chunk = acc.process(event_type, body)
                            if chunk:
                                yield f"data: {json.dumps(chunk)}\n\n".encode()
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if delta.get("content"):
                                    completion_log.stream_update(_req_id, content_delta=delta["content"], output_tokens=acc.output_tokens)
                                for _tcd in (delta.get("tool_calls") or []):
                                    completion_log.stream_update(_req_id, tool_call_delta=_tcd, output_tokens=acc.output_tokens)

            if fallback:
                # Deferred Converse fallback with keepalive
                _t0_fb = time.monotonic()
                task = asyncio.create_task(_call_and_translate(span))
                while not task.done():
                    if time.monotonic() - _t0_fb > 600:
                        task.cancel()
                        completion_log.finish(req_id=_req_id, elapsed_ms=int((time.monotonic() - t0) * 1000))
                        yield f"data: {json.dumps({'error': {'message': 'Bedrock timeout', 'type': 'timeout_error'}})}\n\n".encode()
                        yield b"data: [DONE]\n\n"
                        return
                    yield b": keepalive\n\n"
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=15)
                    except asyncio.TimeoutError:
                        continue
                _openai_resp, sse_frames = task.result()
                for frame in sse_frames:
                    yield frame
                return

            # ── Stream completed successfully ─────────────────────
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            finish = acc.finish_chunk()
            yield f"data: {json.dumps(finish)}\n\n".encode()
            yield b"data: [DONE]\n\n"

            bedrock_resp = acc.to_bedrock_response()
            openai_resp = _bedrock_to_openai(bedrock_resp, requested_model)
            openai_resp["id"] = acc._response_id
            for s in (dispatch_span, span):
                s.set_attribute("status_code", 200)
                s.set_attribute("bedrock.input_tokens", acc.input_tokens)
                s.set_attribute("bedrock.output_tokens", acc.output_tokens)
                s.set_attribute("bedrock.stop_reason", acc.stop_reason)
            dispatch_span.set_status(trace.StatusCode.OK)
            dispatch_span.end()
            try:
                from opentelemetry.sdk.trace import TracerProvider as _TP
                provider = trace.get_tracer_provider()
                if isinstance(provider, _TP):
                    provider.force_flush(timeout_millis=2000)
            except Exception:
                pass
            span.set_status(trace.StatusCode.OK)
            _set_span_json(span, "bedrock.response", bedrock_resp)
            _set_span_json(span, "content", openai_resp)

            messages = body_json.get("messages", [])
            trace_id_str = format(span.context.trace_id, '032x')
            ctx_tracker.record(messages, model, trace_id_str, format(span.context.span_id, '016x'), acc.input_tokens, acc.output_tokens, ctx)
            completion_log.finish(req_id=_req_id, input_tokens=acc.input_tokens, output_tokens=acc.output_tokens, elapsed_ms=elapsed_ms, response=openai_resp)

        except httpx.TimeoutException as e:
            logger.error(f"Bedrock stream timeout: {e}")
            span.set_attribute("error", str(e)); span.set_status(trace.StatusCode.ERROR, str(e))
            completion_log.finish(req_id=_req_id, elapsed_ms=int((time.monotonic() - t0) * 1000))
            try: dispatch_span.end()
            except: pass
            yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'timeout_error'}})}\n\n".encode()
            yield b"data: [DONE]\n\n"
        except asyncio.CancelledError:
            logger.warning(f"Bedrock stream cancelled for {model}")
            completion_log.finish(req_id=_req_id, elapsed_ms=int((time.monotonic() - t0) * 1000))
            try: dispatch_span.end()
            except: pass
        except Exception as e:
            logger.error(f"Bedrock stream error: {e}", exc_info=True)
            span.set_attribute("error", str(e)); span.set_status(trace.StatusCode.ERROR, str(e))
            completion_log.finish(req_id=_req_id, elapsed_ms=int((time.monotonic() - t0) * 1000))
            try: dispatch_span.end()
            except: pass
        finally:
            span.end()

    return StreamingResponse(_real_stream(), media_type="text/event-stream")


# =============================================================================
# BACKEND DISCOVERY
# =============================================================================

async def validate_backend(config: Dict) -> bool:
    """Validate backend is accessible and has valid auth."""
    url, key_env = config["url"], config["key_env"]
    key = os.getenv(key_env)

    if not key:
        logger.warning(f"No key for {url} - skipping")
        return False

    models = {}

    try:
        async with Client() as c:
            headers = {"authorization": f"Bearer {key}"}
            r = await c.get(f"{url}/models", headers=headers, timeout=10.0)

            if r.status_code in [401, 403]:
                logger.error(f"Auth failed for {url} - ejecting backend")
            elif r.status_code == 200:
                data = r.json().get('data', [])
                models = {m['id']: m for m in data if m['id'] not in config.get('exclude', [])}
            else:
                logger.warning(f"Backend {url} returned {r.status_code}")
    except Exception as e:
        logger.error(f"Failed to validate {url}: {e}")

    for mid in config.get("manual_models", []):
        if mid not in models:
            models[mid] = {"id": mid, "object": "model", "owned_by": "manual"}

    if not models:
        return False

    BACKENDS[url] = {"models": models, "key_env": key_env}
    MODEL_MAP.update({mid: url for mid in models.keys()})

    if url == "https://integrate.api.nvidia.com/v1":
        # Rerankers use dedicated retrieval endpoints; MODEL_TABLE wins, static table backs it up.
        try:
            from langchain_nvidia_ai_endpoints._statics import MODEL_TABLE
            FORCE_MODELS = {
                mid: m.endpoint
                for mid, m in MODEL_TABLE.items()
                if getattr(m, "endpoint", None) and "/reranking" in m.endpoint
            }
        except Exception:
            FORCE_MODELS = {
                "nv-rerank-qa-mistral-4b:1":
                    "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking",
                "nvidia/llama-3.2-nv-rerankqa-1b-v1":
                    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-3_2-nv-rerankqa-1b-v1/reranking",
                "nvidia/llama-3.2-nv-rerankqa-1b-v2":
                    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-3_2-nv-rerankqa-1b-v2/reranking",
                "nvidia/llama-nemotron-rerank-1b-v2":
                    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-1b-v2/reranking",
                "nvidia/llama-nemotron-rerank-vl-1b-v2":
                    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking",
            }
        MODEL_MAP.update(FORCE_MODELS)
        for mid, murl in FORCE_MODELS.items():
            BACKENDS[murl] = {"models": {mid: {"id": mid}}, "key_env": key_env}
        logger.info(f"  reranker force-routes: {list(FORCE_MODELS.keys())}")
    logger.info(f"✓ {url}: {len(models)} models")
    return True


async def _probe_key_inference(env_var: str, key: str) -> Tuple[bool, str]:
    """Confirm a key can actually run a completion, not merely list models.

    integrate.api's GET /models accepts any key string, so the only honest test
    of a key is a real inference call. Picks a representative chat model served
    by a backend that uses ``env_var`` (skipping rerank/embed endpoints, which
    are not /chat/completions) and runs a 1-token completion with ``key``.
    Returns (ok, detail). If there is no chat model on that backend to probe,
    returns ok=True (nothing to verify)."""
    _PREFERRED = ["nvidia/nemotron-3-super-120b-a12b", "meta/llama-3.3-70b-instruct"]
    _SKIP = ("rerank", "embed", "embedqa", "emb-")

    def _routes_here(m: str) -> bool:
        u = MODEL_MAP.get(m)
        return (isinstance(u, str) and u.endswith("/v1")
                and BACKENDS.get(u, {}).get("key_env") == env_var)

    model = next((m for m in _PREFERRED if _routes_here(m)), None)
    if not model:
        model = next((m for m in MODEL_MAP
                      if _routes_here(m) and not any(s in m.lower() for s in _SKIP)), None)
    if not model:
        return True, "no chat model on this backend to probe"

    url = MODEL_MAP[model]
    try:
        async with Client() as c:
            r = await c.post(
                f"{url}/chat/completions",
                headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
                content=json.dumps({"model": model,
                                    "messages": [{"role": "user", "content": "ok"}],
                                    "max_tokens": 1}).encode(),
                timeout=30.0,
            )
        return (r.status_code == 200), f"{model.split('/')[-1]} -> {r.status_code}"
    except Exception as e:
        return False, f"{model.split('/')[-1]} -> {type(e).__name__}"


async def discover_backends():
    """Pre-compute all accessible backends. Runs once on startup."""
    BACKENDS.clear()
    MODEL_MAP.clear()

    results = await asyncio.gather(*[validate_backend(cfg) for cfg in BACKEND_CONFIGS])
    valid_count = sum(results)

    if _is_bedrock_available():
        logger.info(f"✓ Bedrock fallback available (region: {BEDROCK_REGION})")
        valid_count += 1

    if valid_count == 0:
        logger.error("No backends available!")
    else:
        logger.info(f"Ready: {valid_count} backends, {len(MODEL_MAP)} models")
    return results


# =============================================================================
# FASTAPI APP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await discover_backends()
    yield

app = FastAPI(title="LLM Client", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"backends": len(BACKENDS), "models": len(MODEL_MAP),
            "bedrock_fallback": _is_bedrock_available(),
            "context_cache": ctx_tracker.stats}


@app.get("/v1/models")
async def list_models():
    all_models = [m for b in BACKENDS.values() for m in b["models"].values()]
    listed = {m.get("id") for m in all_models}
    for model in _bedrock_proxy_model_records():
        if model["id"] not in listed:
            all_models.append(model)
    return {"object": "list", "data": all_models}


@app.get("/v1/models/{model:path}")
async def get_model(model: str):
    if url := MODEL_MAP.get(model):
        return BACKENDS[url]["models"][model]
    if _is_bedrock_available() and model in BEDROCK_MODEL_ALIASES:
        return {"id": model, "object": "model", "owned_by": "bedrock-proxy"}
    raise HTTPException(404, get_missing_model_msg(model))

@app.get("/v1/completions/recent")
async def api_completions_recent(after: int = 0):
    return completion_log.recent(after)

@app.get("/v1/completions/stream")
async def api_completions_stream(request: Request):
    """SSE endpoint for real-time completion events (start/update/done)."""
    import queue as _queue
    q = completion_log.subscribe_sse()

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Poll the thread-safe queue from async context
                    loop = asyncio.get_event_loop()
                    item = await loop.run_in_executor(None, lambda: q.get(timeout=5.0))
                    yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
                except _queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            completion_log.unsubscribe_sse(q)

    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/v1/context-chains")
async def api_context_chains():
    """Return all active conversation chains with per-turn token series."""
    return {"chains": ctx_tracker.chains(), **ctx_tracker.stats}


@app.get("/v1/context-chains/{chain_id}")
async def api_context_chain_detail(chain_id: str):
    """Return a single conversation chain by ID."""
    chain = ctx_tracker.chain_detail(chain_id)
    if chain is None:
        raise HTTPException(404, {"error": f"Chain '{chain_id}' not found"})
    return chain




def _responses_input_to_messages(input_value, instructions: str = "") -> list:
    """Translate the common Responses API input shape to chat messages.

    This intentionally covers the simple/stable shapes used by the course and
    OpenAI SDK examples: a string input, a list of role/content messages, or a
    list of content blocks. Unknown structured items are preserved as JSON text
    rather than dropped, so the request remains inspectable in traces.
    """
    messages = []
    if instructions:
        messages.append({"role": "system", "content": instructions})

    if isinstance(input_value, str):
        messages.append({"role": "user", "content": input_value})
        return messages

    if isinstance(input_value, list):
        for item in input_value:
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
                continue
            if not isinstance(item, dict):
                messages.append({"role": "user", "content": json.dumps(item, ensure_ascii=False)})
                continue
            role = item.get("role") or "user"
            content = item.get("content", item.get("text", item.get("input", "")))
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, str):
                        text_parts.append(block)
                    elif isinstance(block, dict):
                        if block.get("type") in ("input_text", "output_text", "text") and "text" in block:
                            text_parts.append(str(block["text"]))
                        elif "text" in block:
                            text_parts.append(str(block["text"]))
                        else:
                            text_parts.append(json.dumps(block, ensure_ascii=False))
                    else:
                        text_parts.append(str(block))
                content = "\n".join(part for part in text_parts if part)
            elif isinstance(content, dict):
                content = content.get("text") or json.dumps(content, ensure_ascii=False)
            messages.append({"role": role, "content": content})
        return messages or [{"role": "user", "content": ""}]

    if input_value is None:
        return messages or [{"role": "user", "content": ""}]
    return messages + [{"role": "user", "content": json.dumps(input_value, ensure_ascii=False)}]


def _responses_to_chat_body(body_json: dict) -> dict:
    """Build an OpenAI chat-completions request from a Responses request."""
    chat_body = {k: v for k, v in body_json.items() if k not in {"input", "instructions", "max_output_tokens"}}
    chat_body["messages"] = _responses_input_to_messages(body_json.get("input"), body_json.get("instructions", ""))
    if "max_output_tokens" in body_json and "max_tokens" not in chat_body:
        chat_body["max_tokens"] = body_json["max_output_tokens"]
    # The Responses API has a different stream event schema.
    # Until that is explicitly implemented, fallback translation is non-streaming only.
    chat_body.pop("stream", None)
    return chat_body


def _chat_completion_text(chat_resp: dict) -> str:
    try:
        msg = (chat_resp.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and "text" in block:
                    parts.append(str(block["text"]))
            return "".join(parts)
    except Exception:
        pass
    return ""


def _chat_usage_to_responses_usage(usage: dict) -> dict:
    usage = usage or {}
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    total_tokens = usage.get("total_tokens", input_tokens + output_tokens) or 0
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens}


def _chat_to_responses_response(chat_resp: dict, original_body: dict) -> dict:
    """Return a minimal Responses API object compatible with SDK output_text."""
    text = _chat_completion_text(chat_resp)
    created = chat_resp.get("created") or int(time.time())
    response_id = chat_resp.get("id", f"resp_{uuid.uuid4().hex}")
    model = chat_resp.get("model", original_body.get("model"))
    finish_reason = None
    try:
        finish_reason = (chat_resp.get("choices") or [{}])[0].get("finish_reason")
    except Exception:
        pass
    return {
        "id": response_id if str(response_id).startswith("resp_") else f"resp_{response_id}",
        "object": "response",
        "created_at": created,
        "status": "completed",
        "model": model,
        "output": [{
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }],
        "usage": _chat_usage_to_responses_usage(chat_resp.get("usage", {})),
        "metadata": original_body.get("metadata"),
        "finish_reason": finish_reason,
        "_proxied_via": "chat.completions",
    }


def _is_responses_route_miss(response: httpx.Response) -> bool:
    if response.status_code not in (404, 405):
        return False
    body = (response.text or "").lower()
    return "not found" in body or "no route" in body or "page not found" in body


def _responses_base(response_id: str, model: str, created_at: int, status: str = "in_progress", output=None, usage=None) -> dict:
    return {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "status": status,
        "model": model,
        "output": output or [],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "metadata": {},
        "usage": usage,
    }


async def _responses_sse_from_response(response_obj: dict):
    response_id = response_obj.get("id", f"resp_{uuid.uuid4().hex}")
    model = response_obj.get("model")
    created_at = response_obj.get("created_at") or int(time.time())
    output = response_obj.get("output") or []
    message = output[0] if output else {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "", "annotations": []}],
    }
    content = message.get("content") or [{"type": "output_text", "text": "", "annotations": []}]
    part = content[0] if content else {"type": "output_text", "text": "", "annotations": []}
    text = part.get("text", "")
    usage = response_obj.get("usage")

    def frame(event_type: str, payload: dict) -> bytes:
        payload = dict(payload)
        payload.setdefault("type", event_type)
        return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()

    base = _responses_base(response_id, model, created_at, "in_progress")
    yield frame("response.created", {"sequence_number": 0, "response": base})
    yield frame("response.in_progress", {"sequence_number": 1, "response": base})
    yield frame("response.output_item.added", {
        "sequence_number": 2,
        "output_index": 0,
        "item": {k: v for k, v in message.items() if k != "content"} | {"content": []},
    })
    yield frame("response.content_part.added", {
        "sequence_number": 3,
        "output_index": 0,
        "item_id": message.get("id"),
        "content_index": 0,
        "part": {"type": "output_text", "text": "", "annotations": []},
    })
    if text:
        yield frame("response.output_text.delta", {
            "sequence_number": 4,
            "output_index": 0,
            "item_id": message.get("id"),
            "content_index": 0,
            "delta": text,
        })
    yield frame("response.output_text.done", {
        "sequence_number": 5,
        "output_index": 0,
        "item_id": message.get("id"),
        "content_index": 0,
        "text": text,
    })
    yield frame("response.content_part.done", {
        "sequence_number": 6,
        "output_index": 0,
        "item_id": message.get("id"),
        "content_index": 0,
        "part": part,
    })
    yield frame("response.output_item.done", {
        "sequence_number": 7,
        "output_index": 0,
        "item": message,
    })
    completed = dict(response_obj)
    completed["status"] = "completed"
    yield frame("response.completed", {
        "sequence_number": 8,
        "response": completed,
    })
    yield b"data: [DONE]\n\n"


async def _responses_sse_error(model: str, message: str, code: str = "upstream_error", status_code: int = 500):
    response_id = f"resp_{uuid.uuid4().hex}"
    created_at = int(time.time())
    response_obj = _responses_base(response_id, model, created_at, "failed", output=[], usage=None)
    response_obj["error"] = {
        "type": "server_error",
        "code": code,
        "message": message,
        "status_code": status_code,
    }

    def frame(event_type: str, payload: dict) -> bytes:
        payload = dict(payload)
        payload.setdefault("type", event_type)
        return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()

    yield frame("response.created", {
        "sequence_number": 0,
        "response": _responses_base(response_id, model, created_at),
    })
    yield frame("response.failed", {
        "sequence_number": 1,
        "response": response_obj,
    })
    yield b"data: [DONE]\n\n"



def _bedrock_blocks_to_text(blocks) -> str:
    if isinstance(blocks, str):
        return blocks
    if not isinstance(blocks, list):
        return str(blocks or "")
    parts = []
    for block in blocks:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if "text" in block:
                parts.append(str(block["text"]))
            elif "toolResult" in block:
                parts.append(json.dumps(block["toolResult"], ensure_ascii=False))
            elif "toolUse" in block:
                parts.append(json.dumps(block["toolUse"], ensure_ascii=False))
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
    return "\n".join(part for part in parts if part)


def _converse_request_messages(body_json: dict) -> list:
    messages = []
    system = body_json.get("system")
    if isinstance(system, str) and system.strip():
        messages.append({"role": "system", "content": system})
    elif isinstance(system, list):
        text = _bedrock_blocks_to_text(system)
        if text.strip():
            messages.append({"role": "system", "content": text})

    raw_messages = body_json.get("messages", [])
    if isinstance(raw_messages, str):
        messages.append({"role": "user", "content": raw_messages})
    elif isinstance(raw_messages, list):
        for msg in raw_messages:
            if not isinstance(msg, dict):
                messages.append({"role": "user", "content": str(msg)})
                continue
            role = msg.get("role", "user")
            if role not in {"system", "user", "assistant", "tool"}:
                role = "user"
            messages.append({"role": role, "content": _bedrock_blocks_to_text(msg.get("content", ""))})

    if not messages and body_json.get("input") is not None:
        messages = _responses_input_to_messages(body_json.get("input"), body_json.get("instructions", ""))
    return messages or [{"role": "user", "content": ""}]


def _converse_to_chat_body(body_json: dict) -> dict:
    chat_body = {
        "model": body_json.get("model"),
        "messages": _converse_request_messages(body_json),
    }
    inference = body_json.get("inferenceConfig") or {}
    if "maxTokens" in inference:
        chat_body["max_tokens"] = inference["maxTokens"]
    elif "max_tokens" in body_json:
        chat_body["max_tokens"] = body_json["max_tokens"]
    if "temperature" in inference:
        chat_body["temperature"] = inference["temperature"]
    elif "temperature" in body_json:
        chat_body["temperature"] = body_json["temperature"]
    if "topP" in inference:
        chat_body["top_p"] = inference["topP"]
    elif "top_p" in body_json:
        chat_body["top_p"] = body_json["top_p"]
    if "stopSequences" in inference:
        chat_body["stop"] = inference["stopSequences"]
    elif "stop" in body_json:
        chat_body["stop"] = body_json["stop"]
    return {k: v for k, v in chat_body.items() if v is not None}


def _chat_to_converse_response(chat_resp: dict, original_body: dict, elapsed_ms: int = 0) -> dict:
    text = _chat_completion_text(chat_resp)
    usage = chat_resp.get("usage", {}) or {}
    finish = "end_turn"
    try:
        reason = (chat_resp.get("choices") or [{}])[0].get("finish_reason")
        finish = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use"}.get(reason, reason or "end_turn")
    except Exception:
        pass
    return {
        "id": f"converse_{chat_resp.get('id', uuid.uuid4().hex)}",
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": finish,
        "usage": {
            "inputTokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0,
            "outputTokens": usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0,
            "totalTokens": usage.get("total_tokens", 0) or (
                (usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + (usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
            ),
        },
        "metrics": {"latencyMs": elapsed_ms},
        "_proxied_via": "chat.completions",
        "_model": chat_resp.get("model", original_body.get("model")),
    }


def _converse_text(converse_resp: dict) -> str:
    try:
        return _bedrock_blocks_to_text(converse_resp.get("output", {}).get("message", {}).get("content", []))
    except AttributeError:
        return ""

def merge_openai_chunks(chunks: dict[int, dict]) -> dict:
    """Reassemble streamed SSE chunks into a single OpenAI response for tracing."""
    content = []
    tool_calls = {}
    usage = None
    first = chunks.get(0, {})
    text_class = ""
    acc_choice = {"index": 0}

    for _, c in chunks.items():
        if not c or not c.get("choices"):
            continue

        choice = c["choices"][0]

        if "delta" in choice:
            delta = choice.get("delta", {})

            if "content" in delta and delta["content"]:
                content.append(delta["content"])
                text_class = "content"

            for tc in delta.get("tool_calls", []) or []:
                idx = tc.get("index", 0)
                entry = tool_calls.setdefault(
                    idx,
                    {"id": "", "type": "function",
                     "function": {"name": "", "arguments": ""}}
                )
                if tc.get("id"):
                    entry["id"] = tc["id"]
                if tc.get("type"):
                    entry["type"] = tc["type"]
                fn = tc.get("function", {})
                if fn.get("name"):
                    entry["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    entry["function"]["arguments"] += fn["arguments"]

        elif "text" in choice:
            content.append(choice.get("text", ""))
            text_class = "text"

        usage = c.get("usage", usage)
        if choice.get("finish_reason"):
            acc_choice["finish_reason"] = choice["finish_reason"]
            acc_choice["stop_reason"] = choice.get("stop_reason")

    if text_class == "content":
        msg = {"role": "assistant", "content": "".join(content)}
        if tool_calls:
            msg["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
        acc_choice["message"] = msg
    elif text_class == "text":
        acc_choice["text"] = "".join(content)

    return {
        "id": first.get("id", "synthetic"),
        "object": first.get("object", "chat.completion"),
        "created": first.get("created"),
        "model": first.get("model"),
        "choices": [acc_choice],
        "usage": usage,
        "num_chunks": len(chunks),
    }


# =============================================================================
# CORE PROXY
# =============================================================================


async def _call_chat_backend_for_adapter(
    body_json: dict,
    request: Request,
    route_name: str,
    response_builder,
):
    model = body_json.get("model")
    chat_body = _converse_to_chat_body(body_json) if route_name.startswith("converse") else _responses_to_chat_body(body_json)
    messages = chat_body.get("messages", [])
    stream = bool(body_json.get("stream", False))
    caller = request.headers.get("x-caller", "") or body_json.get("caller", "")
    session_key = request.headers.get("x-openclaw-session-id", "") or request.headers.get("x-session-key", "") or body_json.get("session_key", "")
    span = tracer.start_span(f"{route_name}_request")
    span.set_attribute("path", route_name)
    span.set_attribute("model", model)
    span.set_attribute("stream", stream)
    _set_span_json(span, "request", body_json)
    ctx = ctx_tracker.analyze(messages, model or "")
    ctx_tracker.set_span_attrs(span, ctx, messages, chat_body)

    url = MODEL_MAP.get(model)
    if not url:
        span.set_attribute("error", f"model_not_found: {model}")
        span.set_status(trace.StatusCode.ERROR, f"model_not_found: {model}")
        span.end()
        raise HTTPException(status_code=400, detail=get_missing_model_msg(model))

    backend = BACKENDS[url]
    key = os.getenv(backend["key_env"])
    chat_payload_url = url if url.endswith("ranking") else f"{url}/chat/completions"
    headers = {"authorization": f"Bearer {key}", "content-type": "application/json", "accept": "application/json"}
    req_id = f"{route_name}-{uuid.uuid4().hex[:12]}"
    completion_log.start(
        req_id=req_id, model=model,
        session_key=session_key,
        chain_id=ctx.get("chain_id", ""),
        backend=f"{route_name}-adapter",
        caller=caller,
    )
    dispatch_span = tracer.start_span("upstream_dispatch", context=trace.set_span_in_context(span))
    dispatch_span.set_attribute("backend_url", chat_payload_url)
    dispatch_span.set_attribute("model", model)
    dispatch_span.set_attribute("adapter.route", route_name)
    _set_span_json(dispatch_span, "request_body", chat_body)
    t0 = time.monotonic()
    try:
        async with Client() as c:
            r = await c.post(chat_payload_url, content=json.dumps(chat_body).encode(), headers=headers)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        dispatch_span.set_attribute("status_code", r.status_code)
        span.set_attribute("status_code", r.status_code)
        if r.status_code != 200:
            _set_span_text(dispatch_span, "error.body", r.text)
            dispatch_span.set_status(trace.StatusCode.ERROR, f"Upstream {r.status_code}")
            _set_span_text(span, "error.body", r.text)
            span.set_status(trace.StatusCode.ERROR, f"Upstream {r.status_code}")
            completion_log.finish(req_id=req_id, elapsed_ms=elapsed_ms)
            return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type", "application/json"))

        chat_resp = r.json()
        adapted = response_builder(chat_resp, body_json, elapsed_ms)
        dispatch_span.set_status(trace.StatusCode.OK)
        span.set_status(trace.StatusCode.OK)
        # Chunked write so large adapted responses stay recoverable from the span; never silently truncated at OTel's per-attribute cap.
        _set_span_text(span, "content", json.dumps(adapted))
        su = adapted.get("usage", {})
        input_tokens = su.get("inputTokens", su.get("input_tokens", 0)) or 0
        output_tokens = su.get("outputTokens", su.get("output_tokens", 0)) or 0
        ctx_tracker.record(
            messages, model,
            format(span.context.trace_id, '032x'),
            format(span.context.span_id, '016x'),
            input_tokens, output_tokens, ctx,
        )
        completion_log.finish(
            req_id=req_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_ms=elapsed_ms,
            response=adapted,
        )
        return Response(content=adapted_json.encode(), status_code=200, media_type="application/json")
    except Exception as exc:
        dispatch_span.set_attribute("error", str(exc))
        dispatch_span.set_status(trace.StatusCode.ERROR, str(exc))
        span.set_attribute("error", str(exc))
        span.set_status(trace.StatusCode.ERROR, str(exc))
        completion_log.finish(req_id=req_id)
        raise
    finally:
        dispatch_span.end()
        span.end()


@app.post("/v1/converse")
async def converse(request: Request):
    body = await request.body()
    try:
        body_json = json.loads(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": f"Malformed JSON {exc}"})
    return await _call_chat_backend_for_adapter(body_json, request, "converse", _chat_to_converse_response)


@app.post("/v1/converse-stream")
async def converse_stream(request: Request):
    body = await request.body()
    try:
        body_json = json.loads(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": f"Malformed JSON {exc}"})

    async def _events():
        response = await _call_chat_backend_for_adapter(body_json, request, "converse-stream", _chat_to_converse_response)
        if response.status_code != 200:
            yield response.body
            return
        payload = json.loads(response.body)
        text = _converse_text(payload)
        yield f"data: {json.dumps({'messageStart': {'role': 'assistant'}})}\n\n".encode()
        yield f"data: {json.dumps({'contentBlockStart': {'contentBlockIndex': 0, 'start': {'text': ''}}})}\n\n".encode()
        if text:
            yield f"data: {json.dumps({'contentBlockDelta': {'contentBlockIndex': 0, 'delta': {'text': text}}})}\n\n".encode()
        yield f"data: {json.dumps({'contentBlockStop': {'contentBlockIndex': 0}})}\n\n".encode()
        yield f"data: {json.dumps({'messageStop': {'stopReason': payload.get('stopReason', 'end_turn')}})}\n\n".encode()
        yield f"data: {json.dumps({'metadata': {'usage': payload.get('usage', {}), 'metrics': payload.get('metrics', {})}})}\n\n".encode()
        yield b"data: [DONE]\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream")


@app.post("/v1/{path:path}")
async def proxy(request: Request, path: str):
    """Route /v1/* to the right backend.

    1. Bedrock Converse fallback fires when the model is not in MODEL_MAP and
       Bedrock credentials are present.
    2. OpenAI-compat non-streaming forwards the POST and returns a Response.
    3. OpenAI-compat streaming forwards the POST via httpx.stream and yields
       chunks.
    """
    body = await request.body()
    span = tracer.start_span("proxy_request")
    span.set_attribute("path", path)
    try:
        # ── Parse request ─────────────────────────────────────────────
        try:
            body_json = json.loads(body)
        except Exception as e:
            span.set_attribute("error", f"Malformed JSON: {e}")
            raise HTTPException(status_code=400, detail={"error": f"Malformed JSON {e}"})

        original_body_json = dict(body_json)
        model = body_json.get("model")
        stream = body_json.get("stream", False)
        if path == "responses":
            body_json = dict(body_json)
            body_json["messages"] = _responses_input_to_messages(body_json.get("input"), body_json.get("instructions", ""))
            body_json.setdefault("max_tokens", body_json.get("max_output_tokens", 1024))
        _caller = request.headers.get("x-caller", "") or body_json.get("caller", "")
        _session_key = request.headers.get("x-openclaw-session-id", "") or request.headers.get("x-session-key", "") or body_json.get("session_key", "")
        span.set_attribute("model", model)
        span.set_attribute("stream", stream)

        # ── Context chain analysis ────────────────────────────────────
        messages = (_responses_input_to_messages(body_json.get("input"), body_json.get("instructions", ""))
                    if path == "responses" else body_json.get("messages", []))
        ctx = ctx_tracker.analyze(messages, model or "")
        ctx_tracker.set_span_attrs(span, ctx, messages, body_json)

        # Reject bad inputs here; upstream errors are harder to read.
        mt = body_json.get("max_tokens")
        if mt is not None and (not isinstance(mt, int) or mt < 1):
            span.set_attribute("error", f"invalid max_tokens: {mt!r}")
            raise HTTPException(
                status_code=400,
                detail={"error": {"message": f"max_tokens must be a positive integer; got {mt!r}",
                                  "type": "invalid_request_error",
                                  "param": "max_tokens",
                                  "code": "invalid_max_tokens"}},
            )

        url = MODEL_MAP.get(model)

        # Forward only Bedrock-shaped misses; arbitrary unknown models stay clean 404s.
        if not url and _is_bedrock_available() and _is_bedrock_routable(model):
            logger.info(f"Bedrock fallback for unknown model: {model}")
            span.set_attribute("bedrock_fallback", True)
            if path == "responses":
                chat_resp = await proxy_bedrock(body_json, model, False, span, ctx, caller=_caller, session_key=_session_key)
                if chat_resp.status_code != 200:
                    return chat_resp
                adapted = _chat_to_responses_response(json.loads(chat_resp.body), original_body_json)
                adapted_json = json.dumps(adapted).encode()
                if stream:
                    return StreamingResponse(_responses_sse_from_response(adapted), media_type="text/event-stream")
                return Response(content=adapted_json, status_code=200, media_type="application/json")
            resp = await proxy_bedrock(body_json, model, stream, span, ctx, caller=_caller, session_key=_session_key)
            if stream:
                span = None  # generator owns span lifecycle
            return resp

        # ── No backend found ──────────────────────────────────────────
        if not url:
            span.set_attribute("error", f"model_not_found: {model}")
            raise HTTPException(status_code=400, detail=get_missing_model_msg(model))

        # ── Path 2 & 3: OpenAI-compat passthrough ─────────────────────
        backend = BACKENDS[url]
        key = os.getenv(backend["key_env"])
        span.set_attribute("backend_url", url)

        headers = {
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
            "accept": "text/event-stream" if stream else "application/json",
        }

        payload_url = url if url.endswith("ranking") else f"{url}/{path}"
        payload = dict(url=payload_url, content=json.dumps(body_json).encode(), headers=headers)

        dispatch_span = tracer.start_span(
            "upstream_dispatch",
            context=trace.set_span_in_context(span),
        )
        dispatch_span.set_attribute("backend_url", payload_url)
        dispatch_span.set_attribute("model", model)
        dispatch_span.set_attribute("stream", stream)
        _set_span_json(dispatch_span, "request_body", body_json)

        # ── Path 2: Non-streaming ─────────────────────────────────────
        if not stream:
            responses_fallback = False
            try:
                async with Client() as c:
                    r = await c.post(**payload)
                    if path == "responses" and _is_responses_route_miss(r):
                        responses_fallback = True
                        chat_body = _responses_to_chat_body(body_json)
                        chat_payload_url = url if url.endswith("ranking") else f"{url}/chat/completions"
                        dispatch_span.set_attribute("responses.passthrough_status_code", r.status_code)
                        _set_span_text(dispatch_span, "responses.passthrough_body", r.text)
                        dispatch_span.set_attribute("responses.fallback", "chat.completions")
                        dispatch_span.set_attribute("responses.fallback_url", chat_payload_url)
                        _set_span_json(dispatch_span, "responses.fallback_request_body", chat_body)
                        r = await c.post(
                            url=chat_payload_url,
                            content=json.dumps(chat_body).encode(),
                            headers=headers,
                        )
                dispatch_span.set_attribute("status_code", r.status_code)
                if r.status_code != 200:
                    _set_span_text(dispatch_span, "error.body", r.text)
                    dispatch_span.set_status(trace.StatusCode.ERROR, f"Upstream {r.status_code}")
                else:
                    dispatch_span.set_status(trace.StatusCode.OK)
            except Exception as e:
                dispatch_span.set_attribute("error", str(e))
                dispatch_span.set_status(trace.StatusCode.ERROR, str(e))
                raise
            finally:
                dispatch_span.end()

            span.set_attribute("status_code", r.status_code)
            if responses_fallback:
                span.set_attribute("responses.fallback", "chat.completions")
            if r.status_code != 200:
                _set_span_text(span, "error.body", r.text)
                span.set_status(trace.StatusCode.ERROR, f"Upstream {r.status_code}")
            _ns_req_id = f"openai-{uuid.uuid4().hex[:12]}"
            completion_log.start(
                req_id=_ns_req_id, model=model,
                session_key=_session_key,
                chain_id=ctx.get("chain_id", ""),
                backend="openai-compat",
                caller=_caller,
            )
            try:
                resp_data = r.json()
                if responses_fallback:
                    resp_data = _chat_to_responses_response(resp_data, body_json)
                    content_bytes = json.dumps(resp_data).encode()
                    media_type = "application/json"
                else:
                    content_bytes = r.content
                    media_type = r.headers.get("content-type", "application/json")
                _set_span_json(span, "content", resp_data)
                su = resp_data.get("usage", {})
                completion_log.finish(
                    req_id=_ns_req_id,
                    input_tokens=su.get("prompt_tokens", su.get("input_tokens", 0)),
                    output_tokens=su.get("completion_tokens", su.get("output_tokens", 0)),
                    response=resp_data,
                )
                if r.status_code == 200:
                    ctx_tracker.record(
                        messages, model,
                        format(span.context.trace_id, '032x'),
                        format(span.context.span_id, '016x'),
                        su.get("prompt_tokens", su.get("input_tokens", 0)),
                        su.get("completion_tokens", su.get("output_tokens", 0)),
                        ctx,
                    )
            except Exception:
                content_bytes = r.content
                media_type = r.headers.get("content-type", "application/json")
                _set_span_text(span, "content", r.text)
                completion_log.finish(req_id=_ns_req_id)
            return Response(content=content_bytes, status_code=r.status_code, media_type=media_type)

        # ── Path 3: Streaming ─────────────────────────────────────────
        # Transfer span ownership to the generator.
        stream_span = span
        span = None
        _s_req_id = f"stream-{uuid.uuid4().hex[:12]}"
        completion_log.start(
            req_id=_s_req_id, model=model,
            session_key=_session_key,
            chain_id=ctx.get("chain_id", ""),
            backend="openai-compat",
            caller=_caller,
        )

        async def _openai_stream():
            t0_stream = time.monotonic()
            all_chunks = []
            try:
                async with Client().stream("POST", **payload) as r:
                    dispatch_span.set_attribute("status_code", r.status_code)
                    dispatch_span.end()

                    stream_span.set_attribute("status_code", r.status_code)
                    if r.status_code != 200:
                        error_body = await r.aread()
                        error_text = error_body.decode(errors="replace")
                        if path == "responses" and r.status_code in (404, 405):
                            low = error_text.lower()
                            if "not found" in low or "no route" in low or "page not found" in low:
                                chat_body = _responses_to_chat_body(original_body_json)
                                chat_payload_url = url if url.endswith("ranking") else f"{url}/chat/completions"
                                stream_span.set_attribute("responses.fallback", "stream-chat.completions")
                                stream_span.set_attribute("responses.fallback_url", chat_payload_url)
                                async with Client() as fallback_client:
                                    fallback_resp = await fallback_client.post(
                                        url=chat_payload_url,
                                        content=json.dumps(chat_body).encode(),
                                        headers={**headers, "accept": "application/json"},
                                    )
                                stream_span.set_attribute("responses.fallback_status_code", fallback_resp.status_code)
                                if fallback_resp.status_code == 200:
                                    adapted = _chat_to_responses_response(fallback_resp.json(), original_body_json)
                                    async for frame in _responses_sse_from_response(adapted):
                                        yield frame
                                    stream_span.set_status(trace.StatusCode.OK)
                                    return
                                error_body = fallback_resp.content
                                error_text = error_body.decode(errors="replace")
                        _set_span_text(stream_span, "error.body", error_text)
                        stream_span.set_status(trace.StatusCode.ERROR, f"Upstream {r.status_code}")
                        if path == "responses":
                            async for frame in _responses_sse_error(model, error_text, status_code=r.status_code):
                                yield frame
                            return
                        yield error_body
                        return

                    async for chunk in r.aiter_bytes():
                        yield chunk
                        all_chunks.append(chunk)
                        # Push streaming update for in-flight visibility
                        try:
                            for _line in chunk.decode(errors="replace").split("\n"):
                                _line = _line.strip()
                                if _line.startswith("data: ") and _line != "data: [DONE]":
                                    _cdata = json.loads(_line[6:])
                                    if _cdata.get("id"):
                                        completion_log.set_response_id(_s_req_id, _cdata["id"])
                                    _delta = (_cdata.get("choices", [{}])[0].get("delta") or {})
                                    _content_d = _delta.get("content", "")
                                    _tc_deltas = _delta.get("tool_calls") or []
                                    if _content_d or _tc_deltas:
                                        for _tcd in _tc_deltas:
                                            completion_log.stream_update(_s_req_id, tool_call_delta=_tcd)
                                        if _content_d:
                                            completion_log.stream_update(_s_req_id, content_delta=_content_d)
                        except Exception:
                            pass

            except httpx.ReadTimeout:
                try:
                    dispatch_span.set_attribute("error", "ReadTimeout")
                    dispatch_span.end()
                except Exception:
                    pass
                stream_span.set_attribute("error", "ReadTimeout during streaming")
                stream_span.set_status(trace.StatusCode.ERROR, "ReadTimeout during streaming")
                logger.error(f"ReadTimeout streaming {model} from {url}")
                return
            except Exception as e:
                try:
                    dispatch_span.set_attribute("error", str(e))
                    dispatch_span.end()
                except Exception:
                    pass
                stream_span.set_attribute("error", str(e))
                logger.error(f"Stream error for {model}: {e}")
                stream_span.set_status(trace.StatusCode.ERROR, str(e))
                return
            finally:
                # Aggregate chunks for trace content (no truncation)
                if all_chunks:
                    try:
                        raw = b"".join(all_chunks).decode(errors="replace")
                        parts = [p for p in raw.split("\ndata: ")
                                 if p.strip() and p.strip() != "[DONE]"]
                        if parts and parts[0].startswith("data: "):
                            parts[0] = parts[0][6:]
                        parsed = {}
                        for i, p in enumerate(parts):
                            p = p.rstrip("\n")
                            if not p:
                                continue
                            try:
                                parsed[i] = json.loads(p)
                            except json.JSONDecodeError:
                                continue
                        if parsed:
                            summary = merge_openai_chunks(parsed)
                            # _set_span_text already records chunk count and full_length.
                            _set_span_text(stream_span, "content", json.dumps(summary))
                            # Extract usage for structured attributes
                            su = summary.get("usage") or {}
                            if su:
                                stream_span.set_attribute("usage.prompt_tokens", su.get("prompt_tokens", 0))
                                stream_span.set_attribute("usage.completion_tokens", su.get("completion_tokens", 0))
                            fr = (summary.get("choices") or [{}])[0].get("finish_reason")
                            if fr:
                                stream_span.set_attribute("finish_reason", fr)
                            stream_span.set_status(trace.StatusCode.OK)
                            # Record in context chain
                            ctx_tracker.record(
                                messages, model,
                                format(stream_span.context.trace_id, '032x'),
                                format(stream_span.context.span_id, '016x'),
                                su.get("prompt_tokens", 0) if su else 0,
                                su.get("completion_tokens", 0) if su else 0,
                                ctx,
                            )

                            completion_log.finish(
                                req_id=_s_req_id,
                                input_tokens=su.get("prompt_tokens", 0) if su else 0,
                                output_tokens=su.get("completion_tokens", 0) if su else 0,
                                elapsed_ms=int((time.monotonic() - t0_stream) * 1000) if 't0_stream' in dir() else 0,
                                response=summary,
                            )
                    except Exception as e:
                        logger.warning(f"Trace aggregation failed: {e}")
                stream_span.end()

        gen = _openai_stream()

        # Pull first chunk to detect immediate errors before committing to SSE
        try:
            first_chunk = await gen.__anext__()
        except StopAsyncIteration:
            raise HTTPException(status_code=502, detail="Empty upstream response")

        if isinstance(first_chunk, bytes) and first_chunk.startswith(b'{"error'):
            try:
                err = json.loads(first_chunk)
                await gen.aclose()
                raise HTTPException(status_code=502, detail=err)
            except (json.JSONDecodeError, HTTPException):
                raise

        async def _prepend_first():
            yield first_chunk
            async for chunk in gen:
                yield chunk

        return StreamingResponse(_prepend_first(), media_type="text/event-stream")

    finally:
        if span is not None:
            span.end()


@app.post("/admin/set-key")
async def set_key(request: Request):
    """Set an upstream API key at runtime, with no container restart.

    Accepts any one of the three keys this gateway can use, telling them apart
    by prefix unless an explicit ``provider`` is given:
      - ``nvapi-...``  -> NVIDIA_API_KEY      (NVIDIA build / NIM endpoints)
      - ``sk-...``     -> OPENAI_API_KEY      (OpenAI)
      - anything else  -> AWS_BEARER_TOKEN_BEDROCK (Bedrock bearer token)

    The browser key panel and the kickstart notebook POST here. Per-request
    code reads keys fresh via os.getenv, so updating os.environ takes effect
    immediately; we then re-run discovery so the model map repopulates (model
    discovery runs at boot, and would otherwise be empty if no key was set
    then). Best-effort persistence to the env file lets the key survive a
    gateway restart when that file is writable. The key is never returned.

    Gated upstream by the nginx /lab/svc/llm/ JUPYTER_TOKEN auth_request.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "expected a JSON body"})
    key = (body.get("key") or body.get("nvapi") or body.get("NVIDIA_API_KEY") or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail={"error": "expected a non-empty 'key'"})

    provider = (body.get("provider") or "").strip().lower()
    if not provider:
        if key.startswith("nvapi-"):
            provider = "nvidia"
        elif key.startswith("sk-"):
            provider = "openai"
        else:
            provider = "bedrock"
    env_var = {"nvidia": "NVIDIA_API_KEY", "openai": "OPENAI_API_KEY",
               "bedrock": "AWS_BEARER_TOKEN_BEDROCK"}.get(provider)
    if not env_var:
        raise HTTPException(status_code=400, detail={"error": f"unknown provider '{provider}'"})

    # Shared-key guard: a student key may add capability, never remove working class-wide access.
    # Discovery is not enough because integrate.api lists models for bad keys; prove inference too.
    before = set(MODEL_MAP)
    old_key = os.environ.get(env_var)
    old_ok = bool(old_key) and (await _probe_key_inference(env_var, old_key))[0]
    os.environ[env_var] = key
    await discover_backends()
    new_ok, detail = await _probe_key_inference(env_var, key)
    lost = before - set(MODEL_MAP)
    if old_key and old_key != key and old_ok and (lost or not new_ok):
        os.environ[env_var] = old_key          # restore the shared key
        await discover_backends()
        reason = (f"it would remove {len(lost)} model(s) the shared key serves "
                  f"(e.g. {sorted(lost)[:3]})" if lost
                  else f"it cannot run inference ({detail})")
        raise HTTPException(status_code=409, detail={"error":
            f"key rejected: {reason}. The existing shared key is preserved. To use "
            "your own account, call the model endpoint directly with your key rather "
            "than re-keying the shared gateway."})

    # Accepted. Best-effort persist so the key survives a gateway restart.
    # Skipped silently if the env file is not mounted writable into this container.
    try:
        from pathlib import Path
        envf = Path(os.getenv("LLM_CLIENT_ENV_FILE", "/dli/.env-dev"))
        if envf.parent.exists():
            kept = [ln for ln in (envf.read_text().splitlines() if envf.exists() else [])
                    if not ln.strip().startswith(env_var)]
            kept.append(f"{env_var}={key}")
            envf.write_text("\n".join(kept) + "\n")
    except Exception:
        pass

    return {"ok": len(MODEL_MAP) > 0, "provider": provider, "models": len(MODEL_MAP), "backends": len(BACKENDS)}


@app.post("/rediscover")
async def rediscover():
    await discover_backends()
    return {"backends": len(BACKENDS), "models": len(MODEL_MAP), "bedrock_fallback": _is_bedrock_available()}


if __name__ == "__main__":
    import uvicorn
    DEBUG_MODE = os.getenv("DEBUG", "0") == "1"
    uvicorn.run("llm_client:app", host="0.0.0.0", port=9000, log_level="debug" if DEBUG_MODE else "info")
