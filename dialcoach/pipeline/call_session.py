"""
CallSession: the orchestrator that ties audio -> transcription -> agent -> db
together for one phone call.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from dialcoach.agent.client import CallSummaryResult, ClaudeAgent, LiveCoachResult
from dialcoach.db.models import Call, TranscriptSegment
from dialcoach.db.repository import Database
from dialcoach.pipeline.scoring import talk_ratio, transcript_to_text
from dialcoach.transcription.base import Transcriber

logger = logging.getLogger(__name__)


@dataclass
class CallSessionResult:
    call: Call
    live_updates: list[LiveCoachResult] = field(default_factory=list)
    summary: Optional[CallSummaryResult] = None


class CallSession:
    def __init__(
        self,
        db: Database,
        transcriber: Transcriber,
        business_id: int,
        agent: ClaudeAgent | None = None,
        suggestion_cooldown_seconds: float = 20.0,
        on_live_update: Callable[[LiveCoachResult], None] | None = None,
        audio_path: str | None = None,
    ):
        self.db = db
        self.transcriber = transcriber
        self.agent = agent
        self.business_id = business_id
        self.suggestion_cooldown_seconds = suggestion_cooldown_seconds
        self.on_live_update = on_live_update
        self.audio_path = audio_path

        self._segments: list[TranscriptSegment] = []
        self._last_agent_offset: float | None = None

    def run(self, audio_source) -> CallSessionResult:
        """Consume every chunk from `audio_source` until it's exhausted, then
        finalize the call (compute talk ratio, get a summary, write to db).
        """

        call = self.db.start_call(self.business_id, audio_path=self.audio_path)
        print(f"Start call: {call.id}")
        result = CallSessionResult(call=call)
        # print(f"Result: {type(result)} - {result}")
        # print("Audio Source:", type(audio_source), audio_source)

        last_offset = 0.0
        for chunk_path, offset in audio_source.chunks():
            print("[chunk_path, offset]", chunk_path, offset)
            last_offset = offset
            new_segments = self.transcriber.transcribe_chunk(str(chunk_path), offset_s=offset)
            for seg in new_segments:
                record = self.db.add_segment(
                    TranscriptSegment(
                        id=None,
                        call_id=call.id,
                        speaker=seg.speaker,
                        text=seg.text,
                        t_start=seg.t_start,
                        t_end=seg.t_end,
                    )
                )
                print("[Chunk to Text]", record.speaker, record.text)
                self._segments.append(record)
                print("[Length Segments]", len(self._segments))

            if new_segments and self._should_call_agent(offset):
                self._run_live_coach(result)
                self._last_agent_offset = offset

        ratio = talk_ratio(self._segments)
        summary = self._finalize(call, last_offset, ratio)
        result.summary = summary
        result.call = self.db.get_call(call.id)
        return result

    def _should_call_agent(self, offset: float) -> bool:
        if self.agent is None:
            return False
        if self._last_agent_offset is None:
            return True
        return (offset - self._last_agent_offset) >= self.suggestion_cooldown_seconds

    def _run_live_coach(self, result: CallSessionResult) -> None:
        transcript = transcript_to_text(self._segments)
        try:
            print("[Transcript]", transcript)
            update = self.agent.live_coach(transcript)
        except Exception:  # noqa: BLE001 - a dropped live suggestion must not kill the call
            logger.exception("live_coach call failed; continuing without a suggestion")
            return
        result.live_updates.append(update)
        if self.on_live_update:
            self.on_live_update(update)

    def _finalize(self, call: Call, duration_s: float, ratio: float | None) -> CallSummaryResult | None:
        summary_result: CallSummaryResult | None = None
        temperature = None
        outcome = None

        if self.agent is not None and self._segments:
            transcript = transcript_to_text(self._segments)
            try:
                summary_result = self.agent.summarize_call(transcript)
                temperature = summary_result.temperature
                outcome = summary_result.summary
            except Exception:  # noqa: BLE001
                logger.exception("summarize_call failed; call will be saved without a summary")

        self.db.end_call(
            call.id,
            duration_s=duration_s,
            outcome=outcome,
            temperature=temperature,
            talk_ratio=ratio,
        )

        if summary_result is not None:
            from dialcoach.db.models import LogEntry

            self.db.add_log_entry(
                LogEntry(
                    id=None,
                    call_id=call.id,
                    summary=summary_result.summary,
                    next_step=summary_result.next_step,
                    confirmed=False,
                )
            )

        return summary_result