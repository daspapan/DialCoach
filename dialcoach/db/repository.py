from __future__ import annotations

import sqlite3
from pathlib import Path

from dialcoach.db.models import Business, Call, LogEntry, TranscriptSegment

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    @classmethod
    def in_memory(cls) -> "Database":
        """A fresh, isolated in-memory database - used heavily in tests."""
        return cls(":memory:")

    def _init_schema(self) -> None:
        sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Businesses
    # ------------------------------------------------------------------ #
    def upsert_business(self, business: Business) -> Business:
        """Insert a business, or update it in place if the name already exists.

        Name is the natural key here (there's one row per company, same as
        one row per company in Campaign_Tracker.xlsx).
        """
        existing = self.get_business_by_name(business.name)
        if existing is None:
            cur = self._conn.execute(
                """
                INSERT INTO businesses
                    (name, contact_name, contact_info, source, industry,
                     problem_hypothesis, status, next_step, notes, tracker_row_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    business.name,
                    business.contact_name,
                    business.contact_info,
                    business.source,
                    business.industry,
                    business.problem_hypothesis,
                    business.status,
                    business.next_step,
                    business.notes,
                    business.tracker_row_id,
                ),
            )
            self._conn.commit()
            business.id = cur.lastrowid
            return business

        self._conn.execute(
            """
            UPDATE businesses SET
                contact_name = ?, contact_info = ?, source = ?, industry = ?,
                problem_hypothesis = ?, status = ?, next_step = ?, notes = ?,
                tracker_row_id = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                business.contact_name if business.contact_name is not None else existing.contact_name,
                business.contact_info if business.contact_info is not None else existing.contact_info,
                business.source if business.source is not None else existing.source,
                business.industry if business.industry is not None else existing.industry,
                business.problem_hypothesis
                if business.problem_hypothesis is not None
                else existing.problem_hypothesis,
                business.status,
                business.next_step if business.next_step is not None else existing.next_step,
                business.notes if business.notes is not None else existing.notes,
                business.tracker_row_id
                if business.tracker_row_id is not None
                else existing.tracker_row_id,
                existing.id,
            ),
        )
        self._conn.commit()
        business.id = existing.id
        return business

    def get_business_by_name(self, name: str) -> Business | None:
        row = self._conn.execute(
            "SELECT * FROM businesses WHERE name = ?", (name,)
        ).fetchone()
        return _row_to_business(row) if row else None

    def get_business(self, business_id: int) -> Business | None:
        row = self._conn.execute(
            "SELECT * FROM businesses WHERE id = ?", (business_id,)
        ).fetchone()
        return _row_to_business(row) if row else None

    def list_businesses(self) -> list[Business]:
        rows = self._conn.execute("SELECT * FROM businesses ORDER BY name").fetchall()
        return [_row_to_business(r) for r in rows]

    def update_business_status(self, business_id: int, status: str, next_step: str | None = None) -> None:
        self._conn.execute(
            "UPDATE businesses SET status = ?, next_step = COALESCE(?, next_step), "
            "updated_at = datetime('now') WHERE id = ?",
            (status, next_step, business_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Calls
    # ------------------------------------------------------------------ #
    def start_call(self, business_id: int, audio_path: str | None = None) -> Call:
        cur = self._conn.execute(
            "INSERT INTO calls (business_id, audio_path, status) VALUES (?, ?, 'in_progress')",
            (business_id, audio_path),
        )
        self._conn.commit()
        return self.get_call(cur.lastrowid)

    def end_call(
        self,
        call_id: int,
        duration_s: float,
        outcome: str | None = None,
        temperature: str | None = None,
        talk_ratio: float | None = None,
    ) -> Call:
        self._conn.execute(
            """
            UPDATE calls SET
                ended_at = datetime('now'), duration_s = ?, outcome = ?,
                temperature = ?, talk_ratio = ?, status = 'completed'
            WHERE id = ?
            """,
            (duration_s, outcome, temperature, talk_ratio, call_id),
        )
        self._conn.commit()
        return self.get_call(call_id)

    def get_call(self, call_id: int) -> Call | None:
        row = self._conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        return _row_to_call(row) if row else None

    def list_calls_for_business(self, business_id: int) -> list[Call]:
        # started_at has only second resolution, so two calls started in the
        # same second would tie on it - `id DESC` breaks the tie using
        # insertion order, which is what "most recent first" actually means.
        rows = self._conn.execute(
            "SELECT * FROM calls WHERE business_id = ? ORDER BY started_at DESC, id DESC",
            (business_id,),
        ).fetchall()
        return [_row_to_call(r) for r in rows]

    def list_calls(self) -> list[Call]:
        rows = self._conn.execute(
            "SELECT * FROM calls ORDER BY started_at DESC, id DESC"
        ).fetchall()
        return [_row_to_call(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Transcript segments
    # ------------------------------------------------------------------ #
    def add_segment(self, segment: TranscriptSegment) -> TranscriptSegment:
        cur = self._conn.execute(
            """
            INSERT INTO transcript_segments (call_id, speaker, text, t_start, t_end)
            VALUES (?, ?, ?, ?, ?)
            """,
            (segment.call_id, segment.speaker, segment.text, segment.t_start, segment.t_end),
        )
        self._conn.commit()
        segment.id = cur.lastrowid
        return segment

    def list_segments(self, call_id: int) -> list[TranscriptSegment]:
        rows = self._conn.execute(
            "SELECT * FROM transcript_segments WHERE call_id = ? ORDER BY t_start",
            (call_id,),
        ).fetchall()
        return [_row_to_segment(r) for r in rows]

    def search_segments(self, query: str) -> list[TranscriptSegment]:
        """Simple substring search across every transcript (case-insensitive)."""
        rows = self._conn.execute(
            "SELECT * FROM transcript_segments WHERE text LIKE ? ORDER BY call_id, t_start",
            (f"%{query}%",),
        ).fetchall()
        return [_row_to_segment(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Log entries
    # ------------------------------------------------------------------ #
    def add_log_entry(self, entry: LogEntry) -> LogEntry:
        cur = self._conn.execute(
            """
            INSERT INTO log_entries (call_id, summary, next_step, confirmed)
            VALUES (?, ?, ?, ?)
            """,
            (entry.call_id, entry.summary, entry.next_step, int(entry.confirmed)),
        )
        self._conn.commit()
        entry.id = cur.lastrowid
        return entry

    def confirm_log_entry(self, entry_id: int) -> None:
        self._conn.execute(
            "UPDATE log_entries SET confirmed = 1 WHERE id = ?", (entry_id,)
        )
        self._conn.commit()

    def mark_log_entry_synced(self, entry_id: int) -> None:
        self._conn.execute(
            "UPDATE log_entries SET synced_at = datetime('now') WHERE id = ?", (entry_id,)
        )
        self._conn.commit()

    def get_log_entry_for_call(self, call_id: int) -> LogEntry | None:
        row = self._conn.execute(
            "SELECT * FROM log_entries WHERE call_id = ? ORDER BY id DESC LIMIT 1",
            (call_id,),
        ).fetchone()
        return _row_to_log_entry(row) if row else None

    def list_unsynced_log_entries(self) -> list[LogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM log_entries WHERE confirmed = 1 AND synced_at IS NULL"
        ).fetchall()
        return [_row_to_log_entry(r) for r in rows]


# ---------------------------------------------------------------------- #
# Row -> dataclass converters
# ---------------------------------------------------------------------- #
def _row_to_business(row: sqlite3.Row) -> Business:
    return Business(
        id=row["id"],
        name=row["name"],
        contact_name=row["contact_name"],
        contact_info=row["contact_info"],
        source=row["source"],
        industry=row["industry"],
        problem_hypothesis=row["problem_hypothesis"],
        status=row["status"],
        next_step=row["next_step"],
        notes=row["notes"],
        tracker_row_id=row["tracker_row_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_call(row: sqlite3.Row) -> Call:
    return Call(
        id=row["id"],
        business_id=row["business_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        duration_s=row["duration_s"],
        audio_path=row["audio_path"],
        outcome=row["outcome"],
        temperature=row["temperature"],
        talk_ratio=row["talk_ratio"],
        status=row["status"],
    )


def _row_to_segment(row: sqlite3.Row) -> TranscriptSegment:
    return TranscriptSegment(
        id=row["id"],
        call_id=row["call_id"],
        speaker=row["speaker"],
        text=row["text"],
        t_start=row["t_start"],
        t_end=row["t_end"],
        created_at=row["created_at"],
    )


def _row_to_log_entry(row: sqlite3.Row) -> LogEntry:
    return LogEntry(
        id=row["id"],
        call_id=row["call_id"],
        summary=row["summary"],
        next_step=row["next_step"],
        confirmed=bool(row["confirmed"]),
        synced_at=row["synced_at"],
        created_at=row["created_at"],
    )