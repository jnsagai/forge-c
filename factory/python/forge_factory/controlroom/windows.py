"""Scorecard windows (research R4): current shift, today, 7 d, 30 d, custom - each with the previous window of the
same length. Local boundaries are computed in the configured IANA zone and converted to UTC, so a DST day is 23 h or
25 h long. A current (still open) window ends now; its previous window covers the same elapsed span one period
earlier, so 'today so far' is compared with 'yesterday up to the same time'."""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

FMT = "%Y-%m-%dT%H:%M:%SZ"
KINDS = ("shift", "today", "7d", "30d", "custom")


def _utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime(FMT)


def _hm(s: str) -> tuple[int, int]:
    h, m = (int(x) for x in s.split(":"))
    return h, m


def _at(day, hm: str, tz: ZoneInfo) -> datetime:
    h, m = _hm(hm)
    if h == 24:
        return datetime.combine(day + timedelta(days=1), time(0, 0), tz)
    return datetime.combine(day, time(h, m), tz)


def _shift_bounds(now_l: datetime, shift: dict, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Bounds of the occurrence of `shift` that contains `now_l` (or the latest one that started before it)."""
    for back in (0, 1):
        day = now_l.date() - timedelta(days=back)
        s = _at(day, shift["start"], tz)
        e = _at(day, shift["end"], tz)
        if e <= s:  # spans midnight
            e = _at(day + timedelta(days=1), shift["end"], tz)
        if s <= now_l < e:
            return s, e
    return None, None


def current_shift(cfg: dict, now: datetime) -> tuple[dict, datetime, datetime]:
    tz = ZoneInfo(cfg["tz"])
    now_l = now.astimezone(tz)
    for sh in cfg["shifts"]:
        s, e = _shift_bounds(now_l, sh, tz)
        if s is not None:
            return sh, s, e
    raise ValueError("NO_SHIFT_COVERS_NOW")  # gaps between shifts: no current shift


def window(kind: str, cfg: dict, now: datetime | None = None, start: str | None = None, end: str | None = None) -> dict:
    if kind not in KINDS:
        raise ValueError(f"BAD_WINDOW:{kind}")
    tz = ZoneInfo(cfg["tz"])
    now = (now or datetime.now(UTC)).astimezone(UTC)
    shift_name = None
    if kind == "shift":
        sh, s, e = current_shift(cfg, now)
        shift_name, end_ = sh["name"], min(e, now)
        prev_s = _at(s.astimezone(tz).date() - timedelta(days=1), sh["start"], tz)  # same shift, previous day
        prev = (prev_s, prev_s + (end_ - s))
    elif kind == "today":
        s = datetime.combine(now.astimezone(tz).date(), time(0, 0), tz)
        end_ = now
        ps = datetime.combine((s - timedelta(hours=12)).date(), time(0, 0), tz)  # local midnight of the previous day
        prev = (ps, ps + (end_ - s))
    elif kind in ("7d", "30d"):
        n = timedelta(days=int(kind[:-1]))
        s, end_ = now - n, now
        prev = (s - n, s)
    else:
        if not (start and end):
            raise ValueError("CUSTOM_WINDOW_NEEDS_START_AND_END")
        s = datetime.fromisoformat(start)
        end_ = datetime.fromisoformat(end)
        s = s if s.tzinfo else s.replace(tzinfo=tz)
        end_ = end_ if end_.tzinfo else end_.replace(tzinfo=tz)
        if end_ <= s:
            raise ValueError("CUSTOM_WINDOW_END_BEFORE_START")
        prev = (s - (end_ - s), s)
    return {"kind": kind, "tz": cfg["tz"], "shift": shift_name, "start_utc": _utc(s), "end_utc": _utc(end_),
            "previous": {"start_utc": _utc(prev[0]), "end_utc": _utc(prev[1])}}
