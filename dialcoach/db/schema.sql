-- DialCoach database schema
--
-- Four tables, matching docs/ARCHITECTURE.md:
--   businesses           one row per contact/company (mirrors Campaign_Tracker.xlsx)
--   calls                one row per phone call
--   transcript_segments  one row per spoken utterance within a call
--   log_entries          one row per post-call log/summary, synced to the Log tab

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS businesses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL UNIQUE,
    contact_name        TEXT,
    contact_info        TEXT,
    source              TEXT,
    industry            TEXT,
    problem_hypothesis  TEXT,
    status              TEXT NOT NULL DEFAULT 'New',
    next_step           TEXT,
    notes               TEXT,
    tracker_row_id      INTEGER,          -- Excel row number this business maps to, if known
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id     INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at        TEXT,
    duration_s      REAL,
    audio_path      TEXT,
    outcome         TEXT,
    temperature     TEXT CHECK (temperature IN ('hot', 'warm', 'cold') OR temperature IS NULL),
    talk_ratio      REAL,             -- fraction of speaking time that was "you" (0.0-1.0)
    status          TEXT NOT NULL DEFAULT 'in_progress'
                        CHECK (status IN ('in_progress', 'completed', 'aborted'))
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id     INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    speaker     TEXT NOT NULL CHECK (speaker IN ('you', 'them', 'unknown')),
    text        TEXT NOT NULL,
    t_start     REAL NOT NULL,
    t_end       REAL NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS log_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id         INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    summary         TEXT,
    next_step       TEXT,
    confirmed       INTEGER NOT NULL DEFAULT 0,   -- 0/1 boolean: has the user reviewed & confirmed it
    synced_at       TEXT,                         -- set once written to Campaign_Tracker.xlsx
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_calls_business_id ON calls(business_id);
CREATE INDEX IF NOT EXISTS idx_segments_call_id ON transcript_segments(call_id);
CREATE INDEX IF NOT EXISTS idx_log_entries_call_id ON log_entries(call_id);