from __future__ import annotations

from pathlib import Path
from typing import Iterator, Protocol


class AudioSource(Protocol):
    """Yields (chunk_path, offset_seconds) pairs until the call ends."""

    def chunks(self) -> Iterator[tuple[Path, float]]:
        """Iterate over audio chunks as they become available.

        Each item is (path_to_wav_chunk, offset_seconds) where
        offset_seconds is how far into the call this chunk starts -
        needed so transcript timestamps stay call-relative even though
        each chunk is transcribed independently.
        """
        ...

    def stop(self) -> None:
        """Stop capturing (no-op for sources that are already finite)."""
        ...