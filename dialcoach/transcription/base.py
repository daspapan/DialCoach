"""
Transcriber interface.

Every transcription backend (local Whisper, a streaming API, or a test
double) implements this one method. The pipeline only ever depends on
this interface, never on a specific backend - that's what lets the whole
call pipeline be tested without whisper.cpp, a GPU, or a microphone
present.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TranscribedSegment:
    """One piece of transcribed speech, in seconds relative to chunk start."""

    text: str
    t_start: float
    t_end: float
    speaker: str = "unknown"  # 'you' | 'them' | 'unknown' - set by diarization, if available


class Transcriber(Protocol):
    """Anything that can turn a chunk of audio into text implements this."""

    def transcribe_chunk(self, audio_path: str, offset_s: float = 0.0) -> list[TranscribedSegment]:
        """Transcribe one audio file/chunk.

        Args:
            audio_path: path to a WAV (or other supported) audio file.
            offset_s: seconds to add to every returned segment's timestamps,
                so segment times stay relative to the start of the whole call
                even when chunks are transcribed one at a time.

        Returns:
            A list of TranscribedSegment, in chronological order. May be
            empty (e.g. a silent chunk).
        """
        ...
