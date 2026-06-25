"""Tests for the non-streaming Bedrock↔OpenAI translation functions.

These exercise `_bedrock_to_openai` (Bedrock response → OpenAI chat-completion
shape) and `_openai_to_bedrock` (OpenAI request → Bedrock Converse shape)
across the cases that matter for the course lab:

  - text-only response/request
  - response with reasoningContent (the gap we're fixing)
  - response with tool_use
  - request with assistant.reasoning_content carried over from a previous
    turn (the round-trip gap for thinking+tool_use)
"""
from __future__ import annotations

import json
import pytest


from llm_client import _bedrock_to_openai, _openai_to_bedrock, _is_bedrock_routable

THINKING_BUDGET_TOKENS = 12345


# ── _bedrock_to_openai ──────────────────────────────────────────────────────


class TestBedrockToOpenAINonStreaming:
    def test_text_only_response(self):
        resp = {
            "output": {"message": {"role": "assistant", "content": [{"text": "Hi."}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 5, "outputTokens": 1, "totalTokens": 6},
        }
        openai = _bedrock_to_openai(resp, model="m")
        assert openai["choices"][0]["message"]["content"] == "Hi."
        assert openai["choices"][0]["message"].get("tool_calls") is None
        assert openai["choices"][0]["finish_reason"] == "stop"
        assert openai["usage"]["completion_tokens"] == 1

    def test_reasoning_lifts_to_message_field(self, bedrock_response_with_reasoning):
        """The fix: reasoning lifts into message.reasoning_content (OpenAI-
        compatible), not into a custom `_thinking` top-level field."""
        openai = _bedrock_to_openai(bedrock_response_with_reasoning, model="m")
        msg = openai["choices"][0]["message"]
        assert msg.get("reasoning_content") == "Thinking step.", (
            f"reasoning_content missing or wrong; message: {msg!r}"
        )

    def test_reasoning_signature_preserved(self, bedrock_response_with_reasoning):
        openai = _bedrock_to_openai(bedrock_response_with_reasoning, model="m")
        msg = openai["choices"][0]["message"]
        assert msg.get("reasoning_signature") == "SIG==", (
            f"reasoning_signature missing; message: {msg!r}"
        )

    def test_text_and_reasoning_coexist(self, bedrock_response_with_reasoning):
        openai = _bedrock_to_openai(bedrock_response_with_reasoning, model="m")
        msg = openai["choices"][0]["message"]
        assert msg["content"] == "Final answer."

    def test_tool_use_translates_to_tool_calls(self):
        resp = {
            "output": {"message": {"role": "assistant", "content": [
                {"text": "ok"},
                {"toolUse": {"toolUseId": "t1", "name": "fn", "input": {"x": 1}}},
            ]}},
            "stopReason": "tool_use",
            "usage": {"inputTokens": 5, "outputTokens": 5, "totalTokens": 10},
        }
        openai = _bedrock_to_openai(resp, model="m")
        msg = openai["choices"][0]["message"]
        assert msg["content"] == "ok"
        tc = msg.get("tool_calls", [])
        assert len(tc) == 1
        assert tc[0]["id"] == "t1"
        assert tc[0]["function"]["name"] == "fn"
        assert json.loads(tc[0]["function"]["arguments"]) == {"x": 1}
        assert openai["choices"][0]["finish_reason"] == "tool_calls"

    def test_no_text_returns_null_content_not_empty_string(self):
        resp = {
            "output": {"message": {"role": "assistant", "content": [
                {"toolUse": {"toolUseId": "t", "name": "fn", "input": {}}},
            ]}},
            "stopReason": "tool_use",
            "usage": {},
        }
        openai = _bedrock_to_openai(resp, model="m")
        # OpenAI convention: when only tool_calls are present, content is None.
        assert openai["choices"][0]["message"]["content"] is None


# ── _openai_to_bedrock ──────────────────────────────────────────────────────


class TestOpenAIToBedrock:
    def test_system_user_text_request(self):
        body = {"messages": [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hi"},
        ]}
        bedrock = _openai_to_bedrock(body)
        assert bedrock["system"] == [{"text": "be helpful"}]
        assert bedrock["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]

    def test_tool_call_round_trip(self):
        body = {"messages": [
            {"role": "user", "content": "what time is it?"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "t1", "type": "function",
                             "function": {"name": "now", "arguments": '{"tz":"UTC"}'}}]},
            {"role": "tool", "tool_call_id": "t1", "content": "12:00 UTC"},
        ]}
        bedrock = _openai_to_bedrock(body)
        # Two user messages get merged into one because Bedrock requires alternating roles.
        # The tool result becomes a toolResult block.
        roles = [m["role"] for m in bedrock["messages"]]
        assert roles == ["user", "assistant", "user"]
        # tool_use block on the assistant
        asst_blocks = bedrock["messages"][1]["content"]
        tool_use_blocks = [b for b in asst_blocks if "toolUse" in b]
        assert len(tool_use_blocks) == 1
        assert tool_use_blocks[0]["toolUse"]["input"] == {"tz": "UTC"}
        # toolResult on the user message after
        user_blocks = bedrock["messages"][2]["content"]
        tool_result_blocks = [b for b in user_blocks if "toolResult" in b]
        assert len(tool_result_blocks) == 1
        assert tool_result_blocks[0]["toolResult"]["toolUseId"] == "t1"

    def test_assistant_reasoning_round_tripped(self, openai_assistant_with_reasoning):
        """The fix: when an OpenAI message carries reasoning_content +
        reasoning_signature, the translation re-emits a reasoningContent
        block on the assistant side. Without this, Anthropic-via-Bedrock
        rejects subsequent tool_use turns: it requires the signed thinking
        block to be present in the input to validate the conversation."""
        body = {"messages": [
            {"role": "user", "content": "what time is it?"},
            openai_assistant_with_reasoning,
            {"role": "tool", "tool_call_id": "tool_xyz", "content": "12:00 UTC"},
        ]}
        bedrock = _openai_to_bedrock(body)
        asst = bedrock["messages"][1]
        block_kinds = [next(iter(b)) for b in asst["content"]]
        assert "reasoningContent" in block_kinds, (
            f"reasoning_content not round-tripped; blocks: {asst['content']!r}"
        )
        # And the signature is preserved
        rc_block = next(b for b in asst["content"] if "reasoningContent" in b)
        rt = rc_block["reasoningContent"]["reasoningText"]
        assert rt["text"] == "I need to check the time."
        assert rt["signature"] == "SIG1=="

    def test_assistant_reasoning_appears_before_text_and_tool_use(
            self, openai_assistant_with_reasoning):
        """Anthropic requires reasoning blocks to come first in the content
        list when present."""
        body = {"messages": [
            {"role": "user", "content": "what time is it?"},
            openai_assistant_with_reasoning,
        ]}
        bedrock = _openai_to_bedrock(body)
        block_kinds = [next(iter(b)) for b in bedrock["messages"][1]["content"]]
        # reasoning must come before any text or toolUse
        idx_reason = block_kinds.index("reasoningContent")
        for other in ("text", "toolUse"):
            if other in block_kinds:
                assert idx_reason < block_kinds.index(other), (
                    f"reasoning must precede {other}; got order {block_kinds!r}"
                )

    def test_assistant_reasoning_dropped_silently_when_no_signature(self):
        """If signature is missing we can't safely round-trip, because
        Anthropic will reject the block. The translation should drop it
        silently rather than send an invalid request."""
        body = {"messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant",
             "content": "ok",
             "reasoning_content": "some thinking with no signature attached"},
        ]}
        bedrock = _openai_to_bedrock(body)
        kinds = [next(iter(b)) for b in bedrock["messages"][1]["content"]]
        assert "reasoningContent" not in kinds, (
            "unsigned reasoning must be dropped to avoid Bedrock rejection"
        )

    def test_reasoning_effort_high_maps_to_thinking_budget(self):
        """OpenAI's `reasoning_effort` (low|medium|high) translates to
        Anthropic's `thinking.budget_tokens` so reasoning can be enabled
        through the standard OpenAI-compat field."""
        body = {"messages": [{"role": "user", "content": "hi"}],
                "reasoning_effort": "high"}
        bedrock = _openai_to_bedrock(body)
        amrf = bedrock.get("additionalModelRequestFields") or {}
        thinking = amrf.get("thinking") or {}
        assert thinking.get("type") == "enabled", f"thinking not enabled; got {amrf!r}"
        assert isinstance(thinking.get("budget_tokens"), int)
        assert thinking["budget_tokens"] >= 8000  # high should reserve a real budget

    def test_reasoning_effort_low_smaller_budget(self):
        body = {"messages": [{"role": "user", "content": "hi"}],
                "reasoning_effort": "low"}
        bedrock = _openai_to_bedrock(body)
        thinking = (bedrock.get("additionalModelRequestFields") or {}).get("thinking") or {}
        assert thinking.get("type") == "enabled"
        assert 1000 <= thinking["budget_tokens"] <= 4000, (
            f"low budget should be modest; got {thinking['budget_tokens']}"
        )

    def test_reasoning_effort_none_disables_thinking(self):
        body = {"messages": [{"role": "user", "content": "hi"}],
                "reasoning_effort": "none"}
        bedrock = _openai_to_bedrock(body)
        amrf = bedrock.get("additionalModelRequestFields") or {}
        # `none` should not enable a thinking budget
        assert "thinking" not in amrf or amrf["thinking"].get("type") != "enabled"

    def test_direct_thinking_block_passes_through(self):
        """If the caller already shaped a `thinking` dict (Anthropic-native),
        it round-trips into additionalModelRequestFields untouched."""
        body = {"messages": [{"role": "user", "content": "hi"}],
                "thinking": {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}}
        bedrock = _openai_to_bedrock(body)
        thinking = bedrock["additionalModelRequestFields"]["thinking"]
        assert thinking == {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}

    def test_additional_model_request_fields_passthrough(self):
        body = {"messages": [{"role": "user", "content": "hi"}],
                "additional_model_request_fields": {
                    "thinking": {"type": "enabled", "budget_tokens": 7777},
                    "custom_anthropic_flag": True,
                }}
        bedrock = _openai_to_bedrock(body)
        amrf = bedrock["additionalModelRequestFields"]
        assert amrf["thinking"]["budget_tokens"] == 7777
        assert amrf["custom_anthropic_flag"] is True

    def test_no_thinking_when_unrequested(self):
        body = {"messages": [{"role": "user", "content": "hi"}]}
        bedrock = _openai_to_bedrock(body)
        assert "additionalModelRequestFields" not in bedrock

    def test_max_tokens_auto_bumped_when_smaller_than_thinking_budget(self):
        """Anthropic rejects requests where max_tokens <= thinking.budget_tokens.
        When thinking is enabled and max_tokens would conflict, bump max_tokens
        to leave at least 1024 tokens of headroom for the actual answer."""
        body = {"messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 800,
                "reasoning_effort": "low"}  # 2000 budget
        bedrock = _openai_to_bedrock(body)
        budget = bedrock["additionalModelRequestFields"]["thinking"]["budget_tokens"]
        max_t = bedrock["inferenceConfig"]["maxTokens"]
        assert max_t > budget, (
            f"max_tokens ({max_t}) must exceed thinking budget ({budget})"
        )
        assert max_t >= budget + 1024  # at least 1K of answer headroom

    def test_explicit_max_tokens_kept_when_compatible(self):
        body = {"messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 16000,
                "reasoning_effort": "low"}  # 2000 budget; fits
        bedrock = _openai_to_bedrock(body)
        # No clamping needed; user's max_tokens preserved verbatim
        assert bedrock["inferenceConfig"]["maxTokens"] == 16000


class TestAnthropicDefaultReasoning:
    """When the caller does not specify thinking, but the model is
    Anthropic-on-Bedrock, an env-driven default kicks in. This is the
    lever that lets the openclaw gateway path surface reasoning_content
    without forwarding its own thinking config."""

    def test_default_fires_for_anthropic_when_caller_silent(self, monkeypatch):
        monkeypatch.setenv("LLM_CLIENT_BEDROCK_DEFAULT_REASONING", "low")
        body = {"model": "bedrock-proxy/global.anthropic.claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "hi"}]}
        bedrock = _openai_to_bedrock(body)
        thinking = bedrock["additionalModelRequestFields"]["thinking"]
        assert thinking == {"type": "enabled", "budget_tokens": 2000}

    def test_default_skipped_for_non_anthropic_models(self, monkeypatch):
        monkeypatch.setenv("LLM_CLIENT_BEDROCK_DEFAULT_REASONING", "low")
        body = {"model": "bedrock-proxy/meta.llama4-405b",
                "messages": [{"role": "user", "content": "hi"}]}
        bedrock = _openai_to_bedrock(body)
        # Meta has no thinking blocks; default must not fire
        assert "additionalModelRequestFields" not in bedrock

    def test_default_skipped_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("LLM_CLIENT_BEDROCK_DEFAULT_REASONING", raising=False)
        body = {"model": "bedrock-proxy/global.anthropic.claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "hi"}]}
        bedrock = _openai_to_bedrock(body)
        assert "additionalModelRequestFields" not in bedrock

    def test_explicit_reasoning_effort_wins_over_default(self, monkeypatch):
        monkeypatch.setenv("LLM_CLIENT_BEDROCK_DEFAULT_REASONING", "high")
        body = {"model": "bedrock-proxy/global.anthropic.claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "hi"}],
                "reasoning_effort": "low"}
        bedrock = _openai_to_bedrock(body)
        # The explicit "low" beats the env-default "high"
        assert bedrock["additionalModelRequestFields"]["thinking"]["budget_tokens"] == 2000

    def test_explicit_thinking_block_wins_over_default(self, monkeypatch):
        monkeypatch.setenv("LLM_CLIENT_BEDROCK_DEFAULT_REASONING", "high")
        body = {"model": "bedrock-proxy/global.anthropic.claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "hi"}],
                "thinking": {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}}
        bedrock = _openai_to_bedrock(body)
        # Caller-supplied thinking block wins
        assert bedrock["additionalModelRequestFields"]["thinking"]["budget_tokens"] == THINKING_BUDGET_TOKENS

    def test_invalid_env_value_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("LLM_CLIENT_BEDROCK_DEFAULT_REASONING", "supreme")
        body = {"model": "bedrock-proxy/global.anthropic.claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "hi"}]}
        bedrock = _openai_to_bedrock(body)
        # Unknown effort silently does nothing instead of erroring
        assert "additionalModelRequestFields" not in bedrock


class TestBedrockRoutability:
    """Bedrock fallback should be invoked only for model names that look
    like Bedrock targets. Arbitrary unknown strings shouldn't silently
    return a fake-success response from the AWS endpoint."""

    @pytest.mark.parametrize("model", [
        "bedrock-proxy/global.anthropic.claude-sonnet-4-6",
        "bedrock-proxy/global.anthropic.claude-opus-4-6-v1",
        "aws/anthropic/bedrock-claude-sonnet-4-6",
        "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "us.anthropic.claude-opus-4-1-20250805-v1:0",
    ])
    def test_known_bedrock_shapes_are_routable(self, model):
        assert _is_bedrock_routable(model) is True

    @pytest.mark.parametrize("model", [
        "definitely/not-a-real-model",
        "totally/made/up",
        "",
        None,
        "meta/llama-3.1-8b-instruct",                  # NIM, not Bedrock
        "nvidia/nemotron-nano-12b-v2-vl",              # NIM, not Bedrock
        "openai/gpt-4-turbo",                          # OpenAI, not Bedrock
    ])
    def test_non_bedrock_shapes_are_not_routable(self, model):
        assert _is_bedrock_routable(model) is False
