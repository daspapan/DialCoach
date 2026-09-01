from __future__ import annotations

from pathlib import Path
from typing import Iterator


class MicrophoneSource:
    def __init__(
        self,
        out_dir: str | Path,
        chunk_seconds: float = 12.0,
        sample_rate: int = 16000,
        device: int | str | None = None,
    ):
        try:
            import sounddevice  # noqa: F401  (import-checked here, used in chunks())
            import soundfile  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch in tests
            raise RuntimeError(
                "sounddevice/soundfile are not installed. Run:\n"
                "    pip install -r requirements-audio.txt\n"
                "before capturing live audio. See docs/AUDIO_SETUP.md.\n"
                "(The dashboard, tracker sync, and test suite all work fine without this.)"
            ) from exc

        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_seconds = chunk_seconds
        self.sample_rate = sample_rate
        self.device = device
        self._stopped = False

    def chunks(self) -> Iterator[tuple[Path, float]]:
        import sounddevice as sd
        import soundfile as sf

        index = 0
        offset = 0.0
        frames_per_chunk = int(self.chunk_seconds * self.sample_rate)

        while not self._stopped:
            recording = sd.rec(
                frames_per_chunk,
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=self.device,
            )
            sd.wait()

            chunk_path = self.out_dir / f"chunk_{index:04d}.wav"
            sf.write(str(chunk_path), recording, self.sample_rate)
            yield chunk_path, offset

            offset += self.chunk_seconds
            index += 1

    def stop(self) -> None:
        self._stopped = True

    @staticmethod
    def list_devices() -> str:
        """Human-readable list of available input devices - handy for picking
        the right `device=` value (e.g. a USB mic instead of the built-in one).
        """
        import sounddevice as sd

        return str(sd.query_devices())