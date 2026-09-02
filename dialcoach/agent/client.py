"""
Claude agent wrapper.
"""
from __future__ import annotations

import json
import logging
import anthropic
from dataclasses import dataclass

from dialcoach.agent.prompts import LIVE_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

VALID_TEMPERATURES = {"hot", "warm", "cold", "unclear"}


@dataclass
class LiveCoachResult:
    suggestion: str | None
    violation: str | None
    temperature: str
    temperature_reason: str | None
    raw: str = ""


@dataclass
class CallSummaryResult:
    summary: str
    actual_problem: str | None
    temperature: str
    next_step: str
    talk_time_note: str | None
    raw: str = ""


class AgentError(RuntimeError):
    """Raised when the agent can't be used at all (e.g. no API key/client)."""


def _extract_text(response) -> str:
    """Pull the text out of an anthropic Message response object.

    Written against the shape of anthropic's Message: `response.content`
    is a list of content blocks, each with a `.text` attribute for text
    blocks. Tests supply simple fakes with this same shape.
    """
    parts = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _parse_json_object(raw_text: str) -> dict:
    """Parse a JSON object out of a model response.

    Tolerates the model wrapping the JSON in a code fence or adding
    stray whitespace, which happens occasionally even with a "return
    only JSON" instruction.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in model response: {raw_text!r}")
    return json.loads(text[start : end + 1])


class ClaudeAgent:
    def __init__(
        self,
        api_key: str | None = None,
        client: object | None = None,
        live_model: str = "claude-haiku-4-5",
        summary_model: str = "claude-sonnet-4-5",
    ):
        if client is not None:
            self._client = client
        else:
            if not api_key:
                raise AgentError(
                    "No Anthropic API key configured. Set ANTHROPIC_API_KEY in your "
                    ".env file, or pass a pre-built `client` for testing. "
                    "See .env.example."
                )
            import anthropic  # imported lazily so the module loads without the SDK's

            self._client = anthropic.Anthropic(api_key=api_key)

        self.live_model = live_model
        self.summary_model = summary_model

    # ------------------------------------------------------------------ #
    def live_coach(self, transcript_so_far: str, max_tokens: int = 300) -> LiveCoachResult:
        """Ask for a live suggestion / playbook check / temperature read.

        `transcript_so_far` should be the call transcript up to now, one
        "you: ..." / "them: ..." line per utterance.
        """
        response = self._client.messages.create(
            model=self.live_model,
            max_tokens=max_tokens,
            system=LIVE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": transcript_so_far}],
        )
        raw = _extract_text(response)
        print("[RAW]", raw)
        try:
            data = _parse_json_object(raw)
            print("[DATA]", data)

            temperature = data.get("temperature", "unclear")
            if temperature not in VALID_TEMPERATURES:
                temperature = "unclear"
            return LiveCoachResult(
                suggestion=data.get("suggestion") or None,
                violation=data.get("violation") or None,
                temperature=temperature,
                temperature_reason=data.get("temperature_reason") or None,
                raw=raw,
            )
        except (ValueError, json.JSONDecodeError):
            logger.warning("live_coach: could not parse model response as JSON: %r", raw)
            return LiveCoachResult(
                suggestion=None, violation=None, temperature="unclear",
                temperature_reason=None, raw=raw,
            )

    # ------------------------------------------------------------------ #
    def summarize_call(self, full_transcript: str, max_tokens: int = 500) -> CallSummaryResult:
        """Summarize a completed call and draft a Log entry."""
        response = self._client.messages.create(
            model=self.summary_model,
            max_tokens=max_tokens,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full_transcript}],
        )
        raw = _extract_text(response)

        try:
            data = _parse_json_object(raw)
            temperature = data.get("temperature", "cold")
            if temperature not in ("hot", "warm", "cold"):
                temperature = "cold"
            return CallSummaryResult(
                summary=data.get("summary", "").strip() or "(no summary returned)",
                actual_problem=data.get("actual_problem") or None,
                temperature=temperature,
                next_step=data.get("next_step", "").strip() or "Review call manually",
                talk_time_note=data.get("talk_time_note") or None,
                raw=raw,
            )
        except (ValueError, json.JSONDecodeError):
            logger.warning("summarize_call: could not parse model response as JSON: %r", raw)
            return CallSummaryResult(
                summary="(could not parse model response - see raw transcript)",
                actual_problem=None,
                temperature="cold",
                next_step="Review call manually",
                talk_time_note=None,
                raw=raw,
            )