"""CR-T007: Control Room windows - local boundaries in the configured zone, DST-safe, same-length previous window."""
from datetime import UTC, datetime

import pytest
from forge_factory.controlroom.windows import window

CFG = {"tz": "Europe/Lisbon", "shifts": [{"name": "Day", "start": "00:00", "end": "24:00"}]}


def _dt(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def test_today_starts_at_local_midnight_and_previous_covers_the_same_elapsed_span():
    w = window("today", CFG, now=_dt("2026-10-19T13:00:00Z"))         # 14:00 WEST (UTC+1)
    assert w["start_utc"] == "2026-10-18T23:00:00Z" and w["end_utc"] == "2026-10-19T13:00:00Z"
    assert w["previous"] == {"start_utc": "2026-10-17T23:00:00Z", "end_utc": "2026-10-18T13:00:00Z"}


def test_dst_end_day_is_25_hours_long():
    w = window("today", CFG, now=_dt("2026-10-25T23:30:00Z"))         # 23:30 WET, after the 02:00->01:00 change
    s, e = _dt(w["start_utc"]), _dt(w["end_utc"])
    assert w["start_utc"] == "2026-10-24T23:00:00Z" and (e - s).total_seconds() == 24.5 * 3600


def test_shift_spanning_midnight_and_previous_shift():
    cfg = {"tz": "Europe/Lisbon", "shifts": [{"name": "Day", "start": "07:00", "end": "19:00"},
                                             {"name": "Night", "start": "19:00", "end": "07:00"}]}
    w = window("shift", cfg, now=_dt("2026-10-19T01:00:00Z"))          # 02:00 local => Night shift of the 18th
    assert w["shift"] == "Night" and w["start_utc"] == "2026-10-18T18:00:00Z"
    assert w["previous"]["start_utc"] == "2026-10-17T18:00:00Z"
    d = window("shift", cfg, now=_dt("2026-10-19T09:00:00Z"))
    assert d["shift"] == "Day" and d["start_utc"] == "2026-10-19T06:00:00Z"


@pytest.mark.parametrize("kind,days", [("7d", 7), ("30d", 30)])
def test_rolling_windows_and_previous_have_equal_length(kind, days):
    w = window(kind, CFG, now=_dt("2026-10-19T12:00:00Z"))
    s, e = _dt(w["start_utc"]), _dt(w["end_utc"])
    ps, pe = _dt(w["previous"]["start_utc"]), _dt(w["previous"]["end_utc"])
    assert (e - s).days == days and pe == s and (pe - ps) == (e - s)


def test_custom_window_validation():
    w = window("custom", CFG, start="2026-10-01T00:00", end="2026-10-02T00:00")
    assert w["start_utc"] == "2026-09-30T23:00:00Z" and w["previous"]["end_utc"] == w["start_utc"]
    with pytest.raises(ValueError, match="END_BEFORE_START"):
        window("custom", CFG, start="2026-10-02T00:00", end="2026-10-01T00:00")
    with pytest.raises(ValueError, match="BAD_WINDOW"):
        window("year", CFG)
