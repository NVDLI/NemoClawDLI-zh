"""
Bedrock ConverseStream binary EventStream parser and OpenAI SSE translator.

AWS Bedrock ConverseStream returns responses in the AWS EventStream binary
encoding (application/vnd.amazon.eventstream), not standard SSE. This module
provides:

  1. _parse_eventstream_frame() decodes a single binary frame
  2. iter_eventstream()         is an async generator yielding parsed events
  3. bedrock_stream_to_openai() translates Bedrock events to OpenAI SSE chunks

Frame format (AWS EventStream encoding):
  [total_byte_length:  4 bytes, big-endian uint32]
  [headers_byte_length: 4 bytes, big-endian uint32]
  [prelude_crc:         4 bytes]
  [headers:             variable, key-value pairs]
  [payload:             variable, typically JSON]
  [message_crc:         4 bytes]

Header entry format:
  [name_byte_length:  1 byte uint8]
  [name:              variable UTF-8]
  [value_type:        1 byte uint8]  (7 = string, 6 = bytes, ...)
  [value_byte_length: 2 bytes big-endian uint16]
  [value:             variable]

Events emitted by ConverseStream:
  messageStart       → {"role": "assistant"}
  contentBlockStart   → {"contentBlockIndex": N, "start": {...}}
  contentBlockDelta   → {"contentBlockIndex": N, "delta": {"text": "..."}}
  contentBlockStop    → {"contentBlockIndex": N}
  messageStop         → {"stopReason": "end_turn"|"tool_use"|...}
  metadata            → {"usage": {...}, "metrics": {...}}
"""

import struct
import json
import logging
import time
from typing import AsyncIterator, Optional

logger = logging.getLogger("bedrock-stream")


def _parse_headers(data: bytes) -> dict:
    """Parse EventStream headers from binary data."""
    headers = {}
    pos = 0
    while pos < len(data):
        # Name
        name_len = data[pos]
        pos += 1
        name = data[pos:pos + name_len].decode("utf-8")
        pos += name_len
        # Value type
        value_type = data[pos]
        pos += 1
        # Value: type 7 is a string and type 6 is bytes. Both carry a 2-byte length prefix.
        if value_type in (6, 7):
            value_len = struct.unpack("!H", data[pos:pos + 2])[0]
            pos += 2
            raw = data[pos:pos + value_len]
            headers[name] = raw.decode("utf-8") if value_type == 7 else raw
            pos += value_len
        elif value_type == 4:  # bool true
            headers[name] = True
        elif value_type == 5:  # bool false
            headers[name] = False
        elif value_type == 8:  # timestamp (8 bytes)
            pos += 8
        elif value_type == 0:  # bool true (alternative)
            headers[name] = True
        else:
            # Unknown type. Break to skip it safely.
            logger.warning(f"Unknown EventStream header type {value_type} for {name}")
            break
    return headers


def parse_eventstream_frame(data: bytes) -> Optional[tuple[dict, bytes, int]]:
    """Parse one EventStream frame from the start of `data`.

    Returns (headers_dict, payload_bytes, total_frame_length) or None if
    not enough data for a complete frame.
    """
    if len(data) < 12:  # minimum: 4 + 4 + 4 prelude
        return None
    total_len = struct.unpack("!I", data[0:4])[0]
    headers_len = struct.unpack("!I", data[4:8])[0]
    if len(data) < total_len:
        return None  # incomplete frame
    # Skip prelude CRC (bytes 8-12)
    headers_start = 12
    headers_end = headers_start + headers_len
    payload_start = headers_end
    payload_end = total_len - 4  # exclude message CRC
    headers = _parse_headers(data[headers_start:headers_end])
    payload = data[payload_start:payload_end]
    return headers, payload, total_len


async def iter_eventstream(response) -> AsyncIterator[tuple[str, dict]]:
    """Yield (event_type, payload_dict) from an httpx streaming response.

    Handles the binary EventStream framing, buffering partial frames
    across chunks.
    """
    buf = b""
    async for chunk in response.aiter_bytes():
        buf += chunk
        while True:
            result = parse_eventstream_frame(buf)
            if result is None:
                break
            headers, payload, frame_len = result
            buf = buf[frame_len:]

            event_type = headers.get(":event-type", "")
            message_type = headers.get(":message-type", "")

            if message_type == "exception":
                # Error event
                try:
                    err = json.loads(payload)
                except json.JSONDecodeError:
                    err = {"message": payload.decode("utf-8", errors="replace")}
                yield "error", err
                return

            if not event_type:
                continue

            try:
                body = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                body = {"raw": payload.decode("utf-8", errors="replace")}

            yield event_type, body


class ConverseStreamAccumulator:
    """Accumulate ConverseStream events into a complete Bedrock response.

    Tracks content blocks (text + tool_use), usage, and stop reason. That is
    everything needed to reconstruct the full Bedrock Converse response dict
    and to emit progressive OpenAI SSE chunks.
    """

    def __init__(self, model: str):
        self.model = model
        self._response_id=f"bedrock-{int(time.time())}"
        self._role = "assistant"
        self._blocks: list[dict] = []  # [{type: "text", text: "..."}, {type: "toolUse", ...}]
        self._current_block_idx = -1
        self._current_block_type = ""
        self._tool_input_json = ""  # accumulates partial JSON for tool input
        self._usage = {}
        self._metrics = {}
        self._stop_reason = ""
        self._text_so_far = ""  # for content preview
        self._output_tokens = 0
        self._reasoning_text = ""        # extended-thinking content (Claude reasoning)
        self._reasoning_signature = ""   # signature accompanying the reasoning block
        
    def process(self, event_type: str, body: dict) -> Optional[dict]:
        """
        Process one event. Returns an OpenAI SSE chunk dict if there's
        content to stream, or None for non-content events.
        """
        if event_type == "messageStart":
            self._role = body.get("role", "assistant")
            return None

        elif event_type == "contentBlockStart":
            idx = body.get("contentBlockIndex", 0)
            start = body.get("start", {})
            self._current_block_idx = idx

            if "toolUse" in start:
                tu = start["toolUse"]
                self._current_block_type = "toolUse"
                self._tool_input_json = ""
                self._blocks.append({
                    "type": "toolUse",
                    "toolUseId": tu.get("toolUseId", ""),
                    "name": tu.get("name", ""),
                    "input_json": "",
                })
                # Emit tool_call start chunk
                return self._make_chunk(tool_call_start={
                    "index": idx,
                    "id": tu.get("toolUseId", ""),
                    "type": "function",
                    "function": {"name": tu.get("name", ""), "arguments": ""},
                })
            else:
                self._current_block_type = "text"
                self._blocks.append({"type": "text", "text": ""})
                return None

        elif event_type == "contentBlockDelta":
            delta = body.get("delta", {})

            if "text" in delta:
                text = delta["text"]
                # Bedrock can send text without a fresh text block; create one instead of dropping output.
                if not self._blocks or self._blocks[-1].get("type") != "text":
                    self._blocks.append({"type": "text", "text": ""})
                    self._current_block_type = "text"
                self._blocks[-1]["text"] = self._blocks[-1].get("text", "") + text
                self._text_so_far += text
                return self._make_chunk(content_delta=text)

            elif "toolUse" in delta:
                partial = delta["toolUse"].get("input", "")
                if self._blocks and self._blocks[-1]["type"] == "toolUse":
                    self._blocks[-1]["input_json"] = self._blocks[-1].get("input_json", "") + partial
                return self._make_chunk(tool_call_args_delta={
                    "index": self._current_block_idx,
                    "function": {"arguments": partial},
                })

            elif "reasoningContent" in delta:
                # Mirror Bedrock reasoning onto OpenAI-compatible delta fields.
                rc = delta["reasoningContent"]
                text = rc.get("text", "")
                sig = rc.get("signature", "")
                if text:
                    self._reasoning_text += text
                if sig:
                    self._reasoning_signature = sig
                if text or sig:
                    return self._make_chunk(
                        reasoning_delta=text or None,
                        reasoning_signature=sig or None,
                    )
                return None

            return None

        elif event_type == "contentBlockStop":
            self._current_block_type = ""
            return None

        elif event_type == "messageStop":
            self._stop_reason = body.get("stopReason", "end_turn")
            return None

        elif event_type == "metadata":
            self._usage = body.get("usage", {})
            self._metrics = body.get("metrics", {})
            self._output_tokens = self._usage.get("outputTokens", 0)
            return None

        return None

    def _make_chunk(self, content_delta: str = None,
                    tool_call_start: dict = None,
                    tool_call_args_delta: dict = None,
                    reasoning_delta: str = None,
                    reasoning_signature: str = None) -> dict:
        """Build an OpenAI-format SSE chunk.

        Exactly one of the keyword arguments is expected to be non-None per
        call, with the exception of reasoning_delta + reasoning_signature
        which can coexist in a single chunk (text delta + final signature
        in the same Bedrock event)."""
        chunk = {
            "id": self._response_id,
            "object": "chat.completion.chunk",
            "model": self.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
        }
        delta = chunk["choices"][0]["delta"]

        if content_delta is not None:
            delta["content"] = content_delta
        elif tool_call_start is not None:
            delta["tool_calls"] = [tool_call_start]
        elif tool_call_args_delta is not None:
            delta["tool_calls"] = [tool_call_args_delta]
        else:
            # Reasoning channels are additive (text and signature can both appear in a single Bedrock delta).
            if reasoning_delta is not None:
                delta["reasoning_content"] = reasoning_delta
            if reasoning_signature is not None:
                delta["reasoning_signature"] = reasoning_signature

        return chunk

    def to_bedrock_response(self) -> dict:
        """Reconstruct the full Bedrock Converse response dict (for spans)."""
        content_blocks = []
        if self._reasoning_text or self._reasoning_signature:
            reasoning_text_obj = {"text": self._reasoning_text}
            if self._reasoning_signature:
                reasoning_text_obj["signature"] = self._reasoning_signature
            content_blocks.append({
                "reasoningContent": {"reasoningText": reasoning_text_obj}
            })
        for b in self._blocks:
            if b["type"] == "text":
                content_blocks.append({"text": b.get("text", "")})
            elif b["type"] == "toolUse":
                input_json = b.get("input_json", "{}")
                try:
                    parsed_input = json.loads(input_json)
                except json.JSONDecodeError:
                    parsed_input = {}
                content_blocks.append({
                    "toolUse": {
                        "toolUseId": b.get("toolUseId", ""),
                        "name": b.get("name", ""),
                        "input": parsed_input,
                    }
                })

        return {
            "output": {"message": {"role": self._role, "content": content_blocks}},
            "usage": self._usage,
            "stopReason": self._stop_reason,
            "metrics": self._metrics,
        }

    def finish_chunk(self) -> dict:
        """Build the final SSE chunk with finish_reason + usage."""
        finish_map = {"end_turn": "stop", "max_tokens": "length",
                      "stop_sequence": "stop", "tool_use": "tool_calls"}
        return {
            "id": f"bedrock-stream-{id(self)}",
            "object": "chat.completion.chunk",
            "model": self.model,
            "choices": [{"index": 0, "delta": {},
                         "finish_reason": finish_map.get(self._stop_reason, "stop")}],
            "usage": {
                "prompt_tokens": self._usage.get("inputTokens", 0),
                "completion_tokens": self._usage.get("outputTokens", 0),
                "total_tokens": self._usage.get("totalTokens", 0),
            },
        }

    @property
    def content_preview(self) -> str:
        return self._text_so_far

    @property
    def input_tokens(self) -> int:
        return self._usage.get("inputTokens", 0)

    @property
    def output_tokens(self) -> int:
        return self._usage.get("outputTokens", 0)

    @property
    def stop_reason(self) -> str:
        return self._stop_reason

    @property
    def latency_ms(self) -> int:
        return self._metrics.get("latencyMs", 0)
