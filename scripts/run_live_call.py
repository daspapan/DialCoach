#!/usr/bin/env python3
"""
Live call runner - the local-script entry point for an actual phone call.
"""
from __future__ import annotations

import sys

from dialcoach.agent import ClaudeAgent, AgentError
from dialcoach.config import get_settings
from dialcoach.db import Database
from dialcoach.pipeline import CallSession


def _print_live_update(update) -> None:
    if update.suggestion:
        print(f"\n💡 Suggestion: {update.suggestion}")
    if update.violation:
        print(f"\n⚠️  Playbook check: {update.violation}")
    print(f"   (read so far: {update.temperature}"
          f"{' - ' + update.temperature_reason if update.temperature_reason else ''})")



def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} \"Business Name\"", file=sys.stderr)
        sys.exit(2)

    business_name = sys.argv[1]
    settings = get_settings()
    settings.ensure_directories()

    try:
        from dialcoach.audio.mic_source import MicrophoneSource
        from dialcoach.transcription.local_whisper import LocalWhisperTranscriber
    except RuntimeError as exc:
        print(f"Cannot start live capture: {exc}", file=sys.stderr)
        sys.exit(1)

    db = Database(settings.db_path)
    business = db.get_business_by_name(business_name)
    if business is None:
        print(f"No business named {business_name!r} in the database. "
              f"Run `dialcoach sync-tracker` first.", file=sys.stderr)
        sys.exit(1)

    agent = None
    if settings.has_api_key:
        try:
            agent = ClaudeAgent(
                api_key=settings.anthropic_api_key,
                live_model=settings.live_model,
                summary_model=settings.summary_model,
            )
        except AgentError as exc:
            print(f"Warning: {exc} - continuing without live coaching.", file=sys.stderr)
    else:
        print("No ANTHROPIC_API_KEY set - recording and transcribing only, no coaching.")

    print(f"Recording {business_name}. Speak with the call on speakerphone. Ctrl+C to end the call.\n")

    try:
        mic = MicrophoneSource(
            out_dir=settings.audio_dir / f"call_{business.id}_live",
            chunk_seconds=settings.chunk_seconds,
        )
        transcriber = LocalWhisperTranscriber()
    except RuntimeError as exc:
        print(f"Cannot start live capture: {exc}", file=sys.stderr)
        sys.exit(1)

    session = CallSession(
        db=db,
        transcriber=transcriber,
        business_id=business.id,
        agent=agent,
        suggestion_cooldown_seconds=settings.suggestion_cooldown_seconds,
        on_live_update=_print_live_update,
    )

    try:
        result = session.run(mic)
    except KeyboardInterrupt:
        mic.stop()
        print("\n\nCall ended.")
        return

    print(f"\nCall #{result.call.id} saved.")
    if result.summary:
        print(f"Temperature: {result.summary.temperature}")
        print(f"Summary: {result.summary.summary}")
        print(f"Next step: {result.summary.next_step}")
    print("Review it in the dashboard, then run `dialcoach push-log` once confirmed.")

if __name__ == "__main__":
    main()