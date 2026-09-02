"""Tests for dialcoach.pipeline.scoring (pure functions, no I/O)."""
from __future__ import annotations

import pytest

from dialcoach.db.models import TranscriptSegment
from dialcoach.pipeline.scoring import talk_ratio, transcript_to_text


# def add(a, b):
#     return a + b
#
# def test_addition_passes():
#     """This one should pass."""
#     assert add(2, 3) == 5
#
# def test_addition_fails():
#     """This one is deliberately wrong, so it should fail."""
#     assert add(2, 3) != 10


def _seg(speaker, text, t_start, t_end):
    return TranscriptSegment(id=None, call_id=1, speaker=speaker, text=text, t_start=t_start, t_end=t_end)


def test_talk_ratio_returns_none_for_empty_transcript():
    assert talk_ratio([]) is None


def test_talk_ratio_computes_fraction_of_time_not_turns():
    segments = [
        _seg("you", "short", 0, 1),        # 1s
        _seg("them", "a long answer", 1, 9),  # 8s
    ]
    # 1 "you" turn vs 1 "them" turn (50/50 by turn count) but only 1/9 by time.
    ratio = talk_ratio(segments)
    assert ratio == pytest.approx(1 / 9)


def test_talk_ratio_ignores_unknown_speaker_time_in_numerator():
    segments = [
        _seg("you", "a", 0, 2),
        _seg("unknown", "b", 2, 6),
        _seg("them", "c", 6, 8),
    ]
    # total = 8s, you = 2s
    assert talk_ratio(segments) == pytest.approx(2 / 8)


def test_talk_ratio_all_you_is_one():
    segments = [_seg("you", "a", 0, 5)]
    assert talk_ratio(segments) == pytest.approx(1.0)


def test_talk_ratio_ignores_zero_or_negative_duration_segments():
    segments = [_seg("you", "malformed", 5, 5), _seg("them", "real", 0, 4)]
    assert talk_ratio(segments) == pytest.approx(0.0)

def test_transcript_to_text_orders_by_start_time_and_labels_speakers():
    segments = [
        _seg("them", "second thing said", 3, 5),
        _seg("you", "first thing said", 0, 2),
    ]
    text = transcript_to_text(segments)
    assert text == "you: first thing said\nthem: second thing said"


def test_transcript_to_text_maps_unrecognized_speaker_to_unknown():
    segments = [_seg("narrator", "aside", 0, 1)]
    text = transcript_to_text(segments)
    assert text == "unknown: aside"


def test_transcript_to_text_empty_list_is_empty_string():
    assert transcript_to_text([]) == ""