from __future__ import annotations

import pytest

from dialcoach.db.repository import Database


@pytest.fixture
def db() -> Database:
    """A fresh in-memory SQLite database, isolated per test."""
    database = Database.in_memory()
    yield database
    database.close()


@pytest.fixture
def tracker_path(tmp_path):
    """Path to a (not-yet-created) tracker workbook inside pytest's tmp dir."""
    return tmp_path / "Campaign_Tracker.xlsx"