from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dialcoach.transcription.base import TranscribedSegment


@dataclass
class FixtureTranscriber:
    """Replays a fixed script of segments, ignoring the actual audio file.

    `script` is a list of (speaker, text, duration_seconds) tuples. Each
    call to `transcribe_chunk` pops the next `segments_per_chunk` entries
    off the front of the script (default 1), so a pipeline chunking loop
    can be exercised deterministically without any audio at all.
    """

    script: list[tuple[str, str, float]]
    segments_per_chunk: int = 1
    _cursor: int = field(default=0, repr=False)
    _clock: float = field(default=0.0, repr=False)

    def transcribe_chunk(self, audio_path: str, offset_s: float = 0.0) -> list[TranscribedSegment]:
        del audio_path  # unused - this backend never touches real audio
        batch = self.script[self._cursor : self._cursor + self.segments_per_chunk]
        self._cursor += len(batch)

        segments: list[TranscribedSegment] = []
        for speaker, text, duration in batch:
            t_start = offset_s + self._clock
            t_end = t_start + duration
            segments.append(TranscribedSegment(text=text, t_start=t_start, t_end=t_end, speaker=speaker))
            self._clock += duration
        return segments

    def is_exhausted(self) -> bool:
        return self._cursor >= len(self.script)


class LineFileTranscriber:
    """Reads a "speaker: text" transcript file, one line per segment.

    Format, one utterance per line::

        you: Hi Ramesh, this is Papan from JJB, do you have two minutes?
        them: Sure, go ahead.

    Lines are assigned a synthetic duration based on word count (roughly
    2.5 words/second of speech) so downstream talk-ratio math has
    something reasonable to work with even though no real audio was
    transcribed.
    """

    WORDS_PER_SECOND = 2.5

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lines = self._parse(self.path)
        self._cursor = 0

    @staticmethod
    def _parse(path: Path) -> list[tuple[str, str]]:
        lines: list[tuple[str, str]] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw or ":" not in raw:
                continue
            speaker, text = raw.split(":", 1)
            speaker = speaker.strip().lower()
            if speaker not in ("you", "them"):
                speaker = "unknown"
            lines.append((speaker, text.strip()))
        return lines

    def transcribe_chunk(self, audio_path: str, offset_s: float = 0.0) -> list[TranscribedSegment]:
        del audio_path
        if self._cursor >= len(self._lines):
            return []
        speaker, text = self._lines[self._cursor]
        self._cursor += 1
        duration = max(len(text.split()) / self.WORDS_PER_SECOND, 0.5)
        return [
            TranscribedSegment(
                text=text, t_start=offset_s, t_end=offset_s + duration, speaker=speaker
            )
        ]

    def __len__(self) -> int:
        """Number of parsed utterances - lets a caller drive one chunk call
        per line (see callcoach.cli.main.import_call)."""
        return len(self._lines)