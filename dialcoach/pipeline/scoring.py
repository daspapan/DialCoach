from __future__ import annotations

from dialcoach.db.models import TranscriptSegment


def talk_ratio(segments: list[TranscriptSegment]) -> float | None:
    """Fraction of total speaking TIME (not turns) that was 'you'.

    Returns None if there's no timed speech from either side to measure
    (e.g. an empty transcript), so callers can distinguish "0% you talked"
    from "nothing to measure yet".
    """
    total = 0.0
    you = 0.0
    for seg in segments:
        duration = max(seg.t_end - seg.t_start, 0.0)
        total += duration
        if seg.speaker == "you":
            you += duration

    if total <= 0:
        return None
    return you / total


def transcript_to_text(segments: list[TranscriptSegment]) -> str:
    """Render segments as "speaker: text" lines, in chronological order.

    This is the exact format the agent prompts expect (see
    dialcoach/agent/prompts.py) - keeping the formatting in one place
    means the live and post-call paths can't drift apart.
    """
    ordered = sorted(segments, key=lambda s: s.t_start)
    lines = []
    for seg in ordered:
        label = "you" if seg.speaker == "you" else ("them" if seg.speaker == "them" else "unknown")
        lines.append(f"{label}: {seg.text}")
    return "\n".join(lines)