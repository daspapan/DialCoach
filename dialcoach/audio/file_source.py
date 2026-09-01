from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Iterator


def _write_silent_wav(path: Path, duration_s: float, sample_rate: int = 16000) -> None:
    """Write a minimal, valid, silent mono 16-bit WAV file - no numpy needed."""
    n_frames = int(duration_s * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        silence_frame = struct.pack("<h", 0)
        wf.writeframes(silence_frame * n_frames)


class SilentChunkSource:
    """Generates `n_chunks` silent WAV files of `chunk_seconds` each.

    Used in tests to verify the pipeline's file-handling and chunk-loop
    behavior without asserting anything about transcription content
    (a real transcriber would return no speech for silence; the test
    suite pairs this with a FixtureTranscriber instead when it needs
    specific transcript content).
    """

    def __init__(self, out_dir: str | Path, n_chunks: int, chunk_seconds: float = 2.0):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.n_chunks = n_chunks
        self.chunk_seconds = chunk_seconds
        self._stopped = False

    def chunks(self) -> Iterator[tuple[Path, float]]:
        for i in range(self.n_chunks):
            if self._stopped:
                return
            offset = i * self.chunk_seconds
            path = self.out_dir / f"chunk_{i:04d}.wav"
            _write_silent_wav(path, self.chunk_seconds)
            yield path, offset

    def stop(self) -> None:
        self._stopped = True


class PreRecordedFileSource:
    """Splits one existing WAV file into fixed-length chunks on disk.

    This is the "post-call import" / Phase 0 capture path: point it at a
    recording you already have (from any call-recording app) and it
    behaves like a live source, chunk by chunk, for the rest of the
    pipeline.
    """

    def __init__(self, source_wav: str | Path, out_dir: str | Path, chunk_seconds: float = 12.0):
        self.source_wav = Path(source_wav)
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_seconds = chunk_seconds
        self._stopped = False

    def chunks(self) -> Iterator[tuple[Path, float]]:
        with wave.open(str(self.source_wav), "rb") as src:
            n_channels = src.getnchannels()
            sampwidth = src.getsampwidth()
            framerate = src.getframerate()
            frames_per_chunk = int(self.chunk_seconds * framerate)

            index = 0
            offset = 0.0
            while True:
                if self._stopped:
                    return
                frames = src.readframes(frames_per_chunk)
                if not frames:
                    return

                chunk_path = self.out_dir / f"chunk_{index:04d}.wav"
                with wave.open(str(chunk_path), "wb") as out:
                    out.setnchannels(n_channels)
                    out.setsampwidth(sampwidth)
                    out.setframerate(framerate)
                    out.writeframes(frames)

                yield chunk_path, offset
                n_frames_read = len(frames) // (sampwidth * n_channels)
                offset += n_frames_read / framerate
                index += 1

    def stop(self) -> None:
        self._stopped = True