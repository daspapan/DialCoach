from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default

@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of dialcoach's runtime configuration."""

    anthropic_api_key: str | None = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY") or None
    )
    live_model: str = field(
        default_factory=lambda: _env("DIALCOACH_LIVE_MODEL", "claude-haiku-4-5")
    )
    summary_model: str = field(
        default_factory=lambda: _env("DIALCOACH_SUMMARY_MODEL", "claude-sonnet-4-5")
    )
    version: str = field(
        default_factory=lambda: os.environ.get("DIALCOACH_VERSION", "v1")
    )
    db_path: Path = field(
        default_factory=lambda: Path(_env("DIALCOACH_DB_PATH", f'./data/dialcoach_{{version}}.db'))
    )
    audio_dir: Path = field(
        default_factory=lambda: Path(_env("DIALCOACH_AUDIO_DIR", "./data/audio"))
    )
    tracker_path: Path = field(
        default_factory=lambda: Path(
            _env("DIALCOACH_TRACKER_PATH", "./data/Campaign_Tracker.xlsx")
        )
    )

    # Pipeline tuning
    chunk_seconds: float = 12.0          # rolling buffer size fed to the transcriber
    suggestion_cooldown_seconds: float = 20.0  # minimum gap between live agent calls
    target_talk_ratio: float = 0.30      # "you" should talk ~30% of the call (Level 2)

    def ensure_directories(self) -> None:
        """Create the data/audio directories if they don't exist yet."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    @property
    def has_api_key(self) -> bool:
        return bool(self.anthropic_api_key)


def get_settings() -> Settings:
    """Return a fresh Settings instance."""
    return Settings()
