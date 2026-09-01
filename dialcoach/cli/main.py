from __future__ import annotations

import sys
from pathlib import Path

import click

from dialcoach.agent.client import AgentError, ClaudeAgent
from dialcoach.config import get_settings
from dialcoach.db.models import Business, LogEntry
from dialcoach.db.repository import Database
from dialcoach.pipeline.call_session import CallSession
from dialcoach.pipeline.scoring import transcript_to_text
from dialcoach.tracker.sync import LogRow, TrackerRow, TrackerSync


def _open_db() -> Database:
    settings = get_settings()
    settings.ensure_directories()
    return Database(settings.db_path)


@click.group()
def cli() -> None:
    """callcoach: a local phone-outreach call tracker."""


@cli.command()
def init() -> None:
    """Create the local database and tracker workbook if they don't exist yet."""
    settings = get_settings()
    settings.ensure_directories()
    db = Database(settings.db_path)
    db.close()
    TrackerSync(settings.tracker_path)
    click.echo(f"Database ready at {settings.db_path}")
    click.echo(f"Tracker ready at {settings.tracker_path}")
    if not settings.has_api_key:
        click.echo(
            "Note: ANTHROPIC_API_KEY is not set - live coaching and call summaries "
            "will be skipped until you add one to .env (see .env.example)."
        )


@cli.command("sync-tracker")
def sync_tracker() -> None:
    """Pull every row from Campaign_Tracker.xlsx into the local database."""
    settings = get_settings()
    settings.ensure_directories()
    tracker = TrackerSync(settings.tracker_path)
    rows = tracker.read_rows()

    with _open_db() as db:
        for row in rows:
            db.upsert_business(
                Business(
                    id=None,
                    name=row.company,
                    contact_name=row.contact_name,
                    contact_info=row.contact_info,
                    source=row.source,
                    problem_hypothesis=row.problem_hypothesis,
                    status=row.status,
                    next_step=row.next_step,
                    notes=row.notes,
                    tracker_row_id=row.row_number,
                )
            )
    click.echo(f"Synced {len(rows)} business(es) from {settings.tracker_path}")


@cli.command("list-businesses")
def list_businesses() -> None:
    """List every business currently in the local database."""
    with _open_db() as db:
        businesses = db.list_businesses()
    if not businesses:
        click.echo("No businesses yet - run `callcoach sync-tracker` first.")
        return
    for b in businesses:
        click.echo(f"[{b.id}] {b.name} - {b.status} ({b.contact_name or 'no contact name'})")


@cli.command("import-call")
@click.option("--business", required=True, help="Business name (must exist - run sync-tracker first).")
@click.option(
    "--transcript",
    "transcript_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Plain text transcript file, "speaker: text" per line (speaker is "you" or "them").',
)
@click.option("--no-agent", is_flag=True, help="Skip the Claude agent even if an API key is configured.")
def import_call(business: str, transcript_path: Path, no_agent: bool) -> None:
    """Import an already-transcribed call (e.g. from a call-recording app).

    This is the Phase 0 path from the build plan: no live audio, no
    microphone, just a transcript in -> a scored, summarized, logged
    call out. See docs/AUDIO_SETUP.md for turning on live capture later.
    """
    from callcoach.transcription.mock import LineFileTranscriber

    settings = get_settings()
    with _open_db() as db:
        biz = db.get_business_by_name(business)
        if biz is None:
            click.echo(f"No business named {business!r} found. Run `callcoach sync-tracker` first.", err=True)
            sys.exit(1)

        agent = None
        if not no_agent and settings.has_api_key:
            try:
                agent = ClaudeAgent(
                    api_key=settings.anthropic_api_key,
                    live_model=settings.live_model,
                    summary_model=settings.summary_model,
                )
            except AgentError as exc:
                click.echo(f"Warning: {exc}", err=True)

        transcriber = LineFileTranscriber(transcript_path)
        session = CallSession(db=db, transcriber=transcriber, business_id=biz.id, agent=agent)

        class _TranscriptFileSource:
            """Drives one `transcribe_chunk` call per line in the transcript
            file, so LineFileTranscriber yields every utterance rather than
            just the first (it hands back one line per call). The offset
            passed each time is just the line index, not a real audio
            timestamp - there's no real audio here, only an already-written
            transcript - but it's monotonically increasing, which is all
            that's needed to keep segments in the right order.
            """

            def __init__(self, path: Path, line_count: int):
                self.path = path
                self.line_count = line_count
                self._stopped = False

            def chunks(self):
                for i in range(self.line_count):
                    if self._stopped:
                        return
                    yield self.path, float(i)

            def stop(self):
                self._stopped = True

        result = session.run(_TranscriptFileSource(transcript_path, len(transcriber)))

    click.echo(f"Imported call #{result.call.id} for {business}")
    if result.summary:
        click.echo(f"  Temperature: {result.summary.temperature}")
        click.echo(f"  Summary: {result.summary.summary}")
        click.echo(f"  Next step: {result.summary.next_step}")
    else:
        click.echo("  (No agent summary - transcript stored, call db/tracker manually if needed.)")


@cli.command("show-call")
@click.argument("call_id", type=int)
def show_call(call_id: int) -> None:
    """Print the full transcript and details for one call."""
    with _open_db() as db:
        call = db.get_call(call_id)
        if call is None:
            click.echo(f"No call #{call_id}", err=True)
            sys.exit(1)
        segments = db.list_segments(call_id)

    click.echo(f"Call #{call.id} - status={call.status} temperature={call.temperature} "
               f"talk_ratio={call.talk_ratio}")
    click.echo(transcript_to_text(segments) or "(no transcript segments)")


@cli.command("push-log")
def push_log() -> None:
    """Write every confirmed-but-unsynced log entry to the tracker's Log sheet."""
    settings = get_settings()
    tracker = TrackerSync(settings.tracker_path)

    with _open_db() as db:
        pending = db.list_unsynced_log_entries()
        for entry in pending:
            call = db.get_call(entry.call_id)
            business = db.get_business(call.business_id)
            tracker.append_log_row(
                LogRow(company=business.name, outcome=entry.summary or "")
            )
            tracker.upsert_row(
                TrackerRow(
                    company=business.name,
                    status=business.status,
                    next_step=entry.next_step,
                )
            )
            db.mark_log_entry_synced(entry.id)

    click.echo(f"Pushed {len(pending)} log entr(y/ies) to {settings.tracker_path}")


@cli.command()
@click.argument("query")
def search(query: str) -> None:
    """Full-text search across every stored transcript."""
    with _open_db() as db:
        matches = db.search_segments(query)
    if not matches:
        click.echo("No matches.")
        return
    for m in matches:
        click.echo(f"call #{m.call_id} [{m.speaker}] {m.text}")


if __name__ == "__main__":
    cli()