from __future__ import annotations

import json

import pytest

from dialcoach.agent.client import AgentError, ClaudeAgent


class _FakeTextBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeMessage:
    def __init__(self, text: str):
        self.content = [_FakeTextBlock(text)]


class FakeAnthropicClient:
    """Records every call and returns a pre-programmed response each time."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[dict] = []
        self.messages = self  # so `self._client.messages.create(...)` works

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeAnthropicClient ran out of programmed responses")
        return _FakeMessage(self._responses.pop(0))


def test_agent_requires_api_key_or_client():
    with pytest.raises(AgentError, match="No Anthropic API key"):
        ClaudeAgent()


def test_live_coach_parses_well_formed_json():
    response = json.dumps(
        {
            "suggestion": "Ask what's taking up the most time.",
            "violation": None,
            "temperature": "warm",
            "temperature_reason": "described a real problem",
        }
    )
    client = FakeAnthropicClient([response])
    agent = ClaudeAgent(client=client)

    result = agent.live_coach("you: hi\nthem: invoicing is a mess")

    assert result.suggestion == "Ask what's taking up the most time."
    assert result.violation is None
    assert result.temperature == "warm"
    assert client.calls[0]["model"] == agent.live_model


