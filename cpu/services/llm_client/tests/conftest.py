"""Shared pytest fixtures for llm_client unit tests.

Importing the llm_client module needs the service dir on sys.path. We do
that here so individual tests don't have to repeat the dance, and so that
adding new tests is one less foot-gun.

The fixtures below provide Bedrock ConverseStream event sequences captured
from real Anthropic-via-Bedrock conversations: text-only, text+reasoning,
tool_use, text+reasoning+tool_use. They're hand-crafted to match the
chunkType/eventType shape Bedrock actually sends. The AWS Bedrock
Runtime documentation for `ResponseStream` is the source of truth.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


# Find llm_client source for flat-service imports during tests.
_CANDIDATES = [
    Path(__file__).resolve().parents[1],              # tests/../ = services/llm_client/
    Path(__file__).resolve().parent / "src",           # tests/src/ (local mirror for CI)
]
_override = os.environ.get("LLM_CLIENT_SRC")
if _override:
    _CANDIDATES.insert(0, Path(_override))

for p in _CANDIDATES:
    if (p / "bedrock_stream.py").exists() and (p / "llm_client.py").exists():
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
        break
else:
    raise RuntimeError(
        "could not locate llm_client source dir; checked: "
        + ", ".join(str(c) for c in _CANDIDATES)
        + ". Set LLM_CLIENT_SRC to override."
    )


# Side-channel envs that llm_client.py looks at at import time.
# Set conservative defaults so the module loads cleanly under pytest without trying to phone home or expect a real Bedrock token.
os.environ.setdefault("LLM_CLIENT_SPAN_ATTR_LIMIT", "8000")
os.environ.setdefault("LLM_CLIENT_SPAN_ATTR_MAX_CHUNKS", "32")
os.environ.setdefault("BEDROCK_MAX_RETRIES", "0")


@pytest.fixture
def event_text_only():
    """Minimal happy-path: messageStart → 1 text block → messageStop → metadata."""
    return [
        ("messageStart", {"role": "assistant"}),
        ("contentBlockStart", {"contentBlockIndex": 0, "start": {}}),
        ("contentBlockDelta", {"contentBlockIndex": 0, "delta": {"text": "Hello"}}),
        ("contentBlockDelta", {"contentBlockIndex": 0, "delta": {"text": " world."}}),
        ("contentBlockStop", {"contentBlockIndex": 0}),
        ("messageStop", {"stopReason": "end_turn"}),
        ("metadata", {"usage": {"inputTokens": 12, "outputTokens": 3, "totalTokens": 15},
                      "metrics": {"latencyMs": 220}}),
    ]


@pytest.fixture
def event_text_with_reasoning():
    """Realistic Claude-with-thinking shape: reasoning block first, then text."""
    return [
        ("messageStart", {"role": "assistant"}),
        # Reasoning content block.
        # Anthropic via Bedrock emits this BEFORE the text block; signature arrives at the end of the reasoning block stream.
        ("contentBlockStart", {"contentBlockIndex": 0, "start": {}}),
        ("contentBlockDelta", {"contentBlockIndex": 0,
                                "delta": {"reasoningContent": {"text": "Let me think. "}}}),
        ("contentBlockDelta", {"contentBlockIndex": 0,
                                "delta": {"reasoningContent": {"text": "Two plus two."}}}),
        ("contentBlockDelta", {"contentBlockIndex": 0,
                                "delta": {"reasoningContent": {"signature": "ABCDEF=="}}}),
        ("contentBlockStop", {"contentBlockIndex": 0}),
        # Actual user-visible text in a second block.
        ("contentBlockStart", {"contentBlockIndex": 1, "start": {}}),
        ("contentBlockDelta", {"contentBlockIndex": 1, "delta": {"text": "4."}}),
        ("contentBlockStop", {"contentBlockIndex": 1}),
        ("messageStop", {"stopReason": "end_turn"}),
        ("metadata", {"usage": {"inputTokens": 20, "outputTokens": 8, "totalTokens": 28}}),
    ]


@pytest.fixture
def event_tool_use():
    """Tool-call shape: optional preamble text, then a toolUse block."""
    return [
        ("messageStart", {"role": "assistant"}),
        ("contentBlockStart", {"contentBlockIndex": 0, "start": {}}),
        ("contentBlockDelta", {"contentBlockIndex": 0, "delta": {"text": "I'll check the time."}}),
        ("contentBlockStop", {"contentBlockIndex": 0}),
        ("contentBlockStart", {
            "contentBlockIndex": 1,
            "start": {"toolUse": {"toolUseId": "tool_abc", "name": "get_time"}},
        }),
        ("contentBlockDelta", {"contentBlockIndex": 1,
                                "delta": {"toolUse": {"input": '{"timezone":'}}}),
        ("contentBlockDelta", {"contentBlockIndex": 1,
                                "delta": {"toolUse": {"input": '"UTC"}'}}}),
        ("contentBlockStop", {"contentBlockIndex": 1}),
        ("messageStop", {"stopReason": "tool_use"}),
        ("metadata", {"usage": {"inputTokens": 30, "outputTokens": 12, "totalTokens": 42}}),
    ]


@pytest.fixture
def event_reasoning_then_tool_use():
    """Realistic Claude-with-thinking-and-tools: reasoning block, then tool call."""
    return [
        ("messageStart", {"role": "assistant"}),
        # Reasoning
        ("contentBlockStart", {"contentBlockIndex": 0, "start": {}}),
        ("contentBlockDelta", {"contentBlockIndex": 0,
                                "delta": {"reasoningContent": {"text": "I need to check the time."}}}),
        ("contentBlockDelta", {"contentBlockIndex": 0,
                                "delta": {"reasoningContent": {"signature": "SIG1=="}}}),
        ("contentBlockStop", {"contentBlockIndex": 0}),
        # Tool use
        ("contentBlockStart", {
            "contentBlockIndex": 1,
            "start": {"toolUse": {"toolUseId": "tool_xyz", "name": "get_time"}},
        }),
        ("contentBlockDelta", {"contentBlockIndex": 1,
                                "delta": {"toolUse": {"input": '{}'}}}),
        ("contentBlockStop", {"contentBlockIndex": 1}),
        ("messageStop", {"stopReason": "tool_use"}),
        ("metadata", {"usage": {"inputTokens": 25, "outputTokens": 10, "totalTokens": 35}}),
    ]


@pytest.fixture
def event_lazy_text_block():
    """Edge case observed in real streams: a contentBlockDelta with text arrives
    without a fresh contentBlockStart preceding it (after a toolUse end)."""
    return [
        ("messageStart", {"role": "assistant"}),
        ("contentBlockStart", {
            "contentBlockIndex": 0,
            "start": {"toolUse": {"toolUseId": "tool_x", "name": "noop"}},
        }),
        ("contentBlockDelta", {"contentBlockIndex": 0, "delta": {"toolUse": {"input": "{}"}}}),
        ("contentBlockStop", {"contentBlockIndex": 0}),
        # Bedrock sometimes resumes text without a fresh start
        ("contentBlockDelta", {"contentBlockIndex": 1, "delta": {"text": "Done."}}),
        ("messageStop", {"stopReason": "end_turn"}),
        ("metadata", {"usage": {"inputTokens": 5, "outputTokens": 1, "totalTokens": 6}}),
    ]


@pytest.fixture
def bedrock_response_with_reasoning():
    """Full non-streaming Bedrock Converse response with a reasoningContent block."""
    return {
        "output": {"message": {
            "role": "assistant",
            "content": [
                {"reasoningContent": {"reasoningText": {"text": "Thinking step.",
                                                         "signature": "SIG=="}}},
                {"text": "Final answer."},
            ],
        }},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
    }


@pytest.fixture
def openai_assistant_with_reasoning():
    """An OpenAI-format assistant message echoing back reasoning_content +
    a tool_call from the previous turn. This is the shape an OpenAI-compat
    client sends back when continuing a thinking+tool_use conversation."""
    return {
        "role": "assistant",
        "content": "I'll check the time.",
        "reasoning_content": "I need to check the time.",
        "reasoning_signature": "SIG1==",
        "tool_calls": [{
            "id": "tool_xyz",
            "type": "function",
            "function": {"name": "get_time", "arguments": "{}"},
        }],
    }
