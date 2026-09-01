from __future__ import annotations

from callcoach.transcription.base import TranscribedSegment


class LocalWhisperTranscriber:
    """Wraps faster-whisper for fully offline, free transcription.

    Not covered by the default test suite (it needs a real model and
    real audio) - see tests/test_transcription.py for what *is* verified
    about this class (its error handling when the dependency is missing).
    """

    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised via a monkeypatch in tests
            raise RuntimeError(
                "faster-whisper is not installed. Run:\n"
                "    pip install -r requirements-audio.txt\n"
                "    pip install faster-whisper\n"
                "before using LocalWhisperTranscriber. See docs/AUDIO_SETUP.md."
            ) from exc

        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe_chunk(self, audio_path: str, offset_s: float = 0.0) -> list[TranscribedSegment]:
        segments, _info = self._model.transcribe(audio_path, beam_size=5, vad_filter=True)
        return [
            TranscribedSegment(
                text=seg.text.strip(),
                t_start=offset_s + seg.start,
                t_end=offset_s + seg.end,
                speaker="unknown",  # faster-whisper doesn't diarize; see docs/AUDIO_SETUP.md
            )
            for seg in segments
            if seg.text.strip()
        ]