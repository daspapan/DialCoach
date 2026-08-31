from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Business:
    id: int | None
    name: str
    contact_name: str | None = None
    contact_info: str | None = None
    source: str | None = None
    industry: str | None = None
    problem_hypothesis: str | None = None
    status: str = "New"
    next_step: str | None = None
    notes: str | None = None
    tracker_row_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Call:
    id: int | None
    business_id: int
    started_at: str | None = None
    ended_at: str | None = None
    duration_s: float | None = None
    audio_path: str | None = None
    outcome: str | None = None
    temperature: str | None = None       # 'hot' | 'warm' | 'cold' | None
    talk_ratio: float | None = None
    status: str = "in_progress"          # 'in_progress' | 'completed' | 'aborted'


@dataclass
class TranscriptSegment:
    id: int | None
    call_id: int
    speaker: str          # 'you' | 'them' | 'unknown'
    text: str
    t_start: float
    t_end: float
    created_at: str | None = None


@dataclass
class LogEntry:
    id: int | None
    call_id: int
    summary: str | None = None
    next_step: str | None = None
    confirmed: bool = False
    synced_at: str | None = None
    created_at: str | None = None