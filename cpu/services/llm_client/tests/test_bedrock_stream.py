"""Tests for ConverseStreamAccumulator, covering Bedrock event to OpenAI SSE.

Each test drives a synthetic Bedrock event sequence through the accumulator
and asserts on (a) the OpenAI chunks emitted on the wire and (b) the final
to_bedrock_response() shape used by the OTel span.

The current accumulator has known gaps (reasoning_content is accumulated but
never emitted as a chunk). Tests marked `xfail(strict=True)` document those
gaps so the test suite stays red until the fix lands; switching to strict
means an accidental pass will *also* fail, surfacing implementation drift.
"""
from __future__ import annotations

import json
import pytest

from bedrock_stream import ConverseStreamAccumulator


def _drive(events, model="test-model"):
    """Run events through the accumulator; collect non-None chunks."""
    acc = ConverseStreamAccumulator(model)
    chunks = []
    for kind, body in events:
        chunk = acc.process(kind, body)
        if chunk is not None:
            chunks.append(chunk)
    return acc, chunks


def _chunk_deltas(chunks):
    """Flatten the delta dicts from a list of SSE chunks for assertions."""
    return [c["choices"][0]["delta"] for c in chunks]


# ── Text-only stream ────────────────────────────────────────────────────────


class TestTextOnly:
    def test_text_chunks_appear_in_order(self, event_text_only):
        _, chunks = _drive(event_text_only)
        deltas = _chunk_deltas(chunks)
        contents = [d.get("content") for d in deltas if "content" in d]
        assert contents == ["Hello", " world."]

    def test_no_reasoning_chunks_emitted_for_text_only(self, event_text_only):
        _, chunks = _drive(event_text_only)
        for d in _chunk_deltas(chunks):
            assert "reasoning_content" not in d
            assert "reasoning_signature" not in d

    def test_final_response_assembles_full_text(self, event_text_only):
        acc, _ = _drive(event_text_only)
        resp = acc.to_bedrock_response()
        blocks = resp["output"]["message"]["content"]
        text = "".join(b.get("text", "") for b in blocks if "text" in b)
        assert text == "Hello world."

    def test_usage_recorded_from_metadata(self, event_text_only):
        acc, _ = _drive(event_text_only)
        resp = acc.to_bedrock_response()
        assert resp["usage"]["inputTokens"] == 12
        assert resp["usage"]["outputTokens"] == 3

    def test_stop_reason_recorded(self, event_text_only):
        acc, _ = _drive(event_text_only)
        assert acc.to_bedrock_response()["stopReason"] == "end_turn"


# ── Reasoning + text (the headline gap) ─────────────────────────────────────


class TestReasoningStreaming:
    """The accumulator currently swallows reasoningContent deltas. They get
    rolled into to_bedrock_response() but never surface as SSE chunks. Once
    the fix lands these xfails flip to pass."""

    def test_reasoning_chunks_emitted_on_wire(self, event_text_with_reasoning):
        _, chunks = _drive(event_text_with_reasoning)
        deltas = _chunk_deltas(chunks)
        reasoning = [d.get("reasoning_content") for d in deltas
                     if "reasoning_content" in d and d.get("reasoning_content") is not None]
        assert reasoning == ["Let me think. ", "Two plus two."], (
            f"expected two reasoning deltas, got {reasoning!r} from {deltas!r}"
        )

    def test_reasoning_signature_emitted_on_wire(self, event_text_with_reasoning):
        _, chunks = _drive(event_text_with_reasoning)
        deltas = _chunk_deltas(chunks)
        sigs = [d.get("reasoning_signature") for d in deltas if "reasoning_signature" in d]
        assert "ABCDEF==" in sigs, f"signature not emitted on wire: {deltas!r}"

    def test_text_chunks_still_emitted_after_reasoning_block(self, event_text_with_reasoning):
        _, chunks = _drive(event_text_with_reasoning)
        contents = [d.get("content") for d in _chunk_deltas(chunks) if "content" in d]
        assert contents == ["4."]

    def test_reasoning_preserved_in_final_response(self, event_text_with_reasoning):
        acc, _ = _drive(event_text_with_reasoning)
        resp = acc.to_bedrock_response()
        blocks = resp["output"]["message"]["content"]
        reasoning_blocks = [b for b in blocks if "reasoningContent" in b]
        assert len(reasoning_blocks) == 1
        rc = reasoning_blocks[0]["reasoningContent"]["reasoningText"]
        assert rc["text"] == "Let me think. Two plus two."
        assert rc["signature"] == "ABCDEF=="


# ── Tool use ────────────────────────────────────────────────────────────────


class TestToolUse:
    def test_tool_call_start_emitted(self, event_tool_use):
        _, chunks = _drive(event_tool_use)
        # First non-text chunk is the tool_call start.
        tool_starts = [d for d in _chunk_deltas(chunks)
                       if "tool_calls" in d and d["tool_calls"][0].get("id")]
        assert tool_starts, "no tool_call start chunk emitted"
        first = tool_starts[0]["tool_calls"][0]
        assert first["id"] == "tool_abc"
        assert first["function"]["name"] == "get_time"

    def test_tool_input_streamed_incrementally(self, event_tool_use):
        _, chunks = _drive(event_tool_use)
        arg_deltas = []
        for d in _chunk_deltas(chunks):
            for tc in d.get("tool_calls", []) or []:
                fn = tc.get("function") or {}
                if "arguments" in fn and not tc.get("id"):
                    # tool_call_args_delta has no id, only arguments
                    arg_deltas.append(fn["arguments"])
        assert "".join(arg_deltas) == '{"timezone":"UTC"}', (
            f"tool input not streamed correctly: {arg_deltas!r}"
        )

    def test_final_response_has_parsed_tool_use(self, event_tool_use):
        acc, _ = _drive(event_tool_use)
        resp = acc.to_bedrock_response()
        blocks = resp["output"]["message"]["content"]
        tool_blocks = [b for b in blocks if "toolUse" in b]
        assert len(tool_blocks) == 1
        tu = tool_blocks[0]["toolUse"]
        assert tu["toolUseId"] == "tool_abc"
        assert tu["name"] == "get_time"
        assert tu["input"] == {"timezone": "UTC"}

    def test_stop_reason_tool_use(self, event_tool_use):
        acc, _ = _drive(event_tool_use)
        assert acc.to_bedrock_response()["stopReason"] == "tool_use"


# ── Reasoning + tool_use combined ───────────────────────────────────────────


class TestReasoningWithToolUse:
    """The signature-carrying reasoning block must be preserved alongside
    tool_use so the round-trip to Anthropic works."""

    def test_reasoning_emitted_before_tool_call_start(self, event_reasoning_then_tool_use):
        _, chunks = _drive(event_reasoning_then_tool_use)
        deltas = _chunk_deltas(chunks)
        reasoning_idxs = [i for i, d in enumerate(deltas) if "reasoning_content" in d]
        tool_start_idxs = [i for i, d in enumerate(deltas)
                            if "tool_calls" in d and d["tool_calls"][0].get("id")]
        assert reasoning_idxs, "no reasoning chunks emitted"
        assert tool_start_idxs, "no tool_call start chunk emitted"
        assert max(reasoning_idxs) < min(tool_start_idxs), (
            "reasoning chunks must arrive before the tool_call start; "
            f"got reasoning at {reasoning_idxs}, tool_start at {tool_start_idxs}"
        )

    def test_response_preserves_both_blocks(self, event_reasoning_then_tool_use):
        acc, _ = _drive(event_reasoning_then_tool_use)
        resp = acc.to_bedrock_response()
        blocks = resp["output"]["message"]["content"]
        kinds = [next(iter(b)) for b in blocks]
        assert "reasoningContent" in kinds
        assert "toolUse" in kinds


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_lazy_text_block_after_tool_use(self, event_lazy_text_block):
        """Real Bedrock streams sometimes emit text deltas without a fresh
        contentBlockStart after a tool_use ends. The accumulator must not drop
        them. The symptom of a drop is output_tokens>0 with content:[]."""
        acc, chunks = _drive(event_lazy_text_block)
        text_contents = [d.get("content") for d in _chunk_deltas(chunks) if "content" in d]
        assert "Done." in text_contents
        resp = acc.to_bedrock_response()
        text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"]
                       if "text" in b)
        assert "Done." in text

    def test_empty_stream_yields_minimal_response(self):
        acc, chunks = _drive([])
        assert chunks == []
        resp = acc.to_bedrock_response()
        assert resp["output"]["message"]["content"] == []
        assert resp["usage"] == {}

    def test_signature_without_text(self):
        """Signature can arrive without preceding text (unusual but legal)."""
        events = [
            ("messageStart", {"role": "assistant"}),
            ("contentBlockStart", {"contentBlockIndex": 0, "start": {}}),
            ("contentBlockDelta", {"contentBlockIndex": 0,
                                    "delta": {"reasoningContent": {"signature": "S=="}}}),
            ("contentBlockStop", {"contentBlockIndex": 0}),
            ("messageStop", {"stopReason": "end_turn"}),
        ]
        acc, _ = _drive(events)
        resp = acc.to_bedrock_response()
        rc_blocks = [b for b in resp["output"]["message"]["content"] if "reasoningContent" in b]
        assert rc_blocks
        rt = rc_blocks[0]["reasoningContent"]["reasoningText"]
        assert rt["signature"] == "S=="

    def test_metadata_after_messagestop_recorded(self, event_text_only):
        # Already covered by usage test above; this just pins the order.
        acc, _ = _drive(event_text_only)
        assert acc.to_bedrock_response()["usage"]["totalTokens"] == 15

    def test_unknown_event_type_is_noop(self):
        acc, chunks = _drive([("greetingExtension", {"hello": "world"})])
        assert chunks == []
