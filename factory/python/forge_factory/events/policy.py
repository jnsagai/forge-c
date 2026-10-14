"""T035 — trace CAPTURE policy (what may be stored), separate from dashboard DISPLAY filters.

* Per-channel capture level OFF|ERROR|WARN|INFO|DEBUG|TRACE; mandatory minimums (audit>=INFO,
  security>=WARN) can never be lowered: an invalid edit is rejected and the last good policy stays active.
* Live reload by file mtime; every accepted/rejected reload is itself an audit event.
* Raw AI prompt/response capture is OFF unless explicitly enabled; hidden reasoning capture is never allowed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ..common import CONFIG_DIR, sha256_file

LEVELS = ["OFF", "ERROR", "WARN", "INFO", "DEBUG", "TRACE"]
RANK = {lv: i for i, lv in enumerate(LEVELS)}
CHANNELS = {"human", "workflow", "tools", "ai", "supervisor", "repair", "security", "audit", "metrics", "knowledge"}
HARD_MINIMUM = {"audit": "INFO", "security": "WARN"}


class PolicyError(ValueError):
    pass


@dataclass
class CapturePolicy:
    levels: dict[str, str]
    raw_ai: bool
    retention_days: dict[str, int]
    sha256: str
    human_max_chars: int = 160

    def captures(self, channel: str, level: str) -> bool:
        cap = self.levels.get(channel, "OFF")
        floor = HARD_MINIMUM.get(channel)
        if floor and RANK[floor] > RANK[cap]:
            cap = floor
        return cap != "OFF" and RANK[level] <= RANK[cap]


def validate(doc: dict) -> list[str]:
    errs = []
    cap = doc.get("capture_levels") or {}
    if set(cap) != CHANNELS:
        errs.append(f"channels must be exactly {sorted(CHANNELS)}")
    for ch, lv in cap.items():
        if lv not in LEVELS:
            errs.append(f"{ch}: invalid level {lv}")
    for ch, floor in HARD_MINIMUM.items():
        lv = cap.get(ch, "OFF")
        if lv not in LEVELS or RANK[lv] < RANK[floor]:
            errs.append(f"{ch}: capture {lv} below mandatory minimum {floor}")
        mm = (doc.get("mandatory_minimum_levels") or {}).get(ch)
        if mm is None or RANK.get(mm, 0) < RANK[floor]:
            errs.append(f"{ch}: mandatory_minimum_levels weakened")
    if doc.get("ai_hidden_reasoning_capture") is not False:
        errs.append("ai_hidden_reasoning_capture must be false")
    if doc.get("redact_secrets_before_persist") is not True:
        errs.append("redact_secrets_before_persist must be true")
    if doc.get("viewer_filters_do_not_change_capture") is not True:
        errs.append("viewer_filters_do_not_change_capture must be true")
    ret = doc.get("per_channel_retention_days") or {}
    if set(ret) != CHANNELS or int(ret.get("audit", 0)) < 365:
        errs.append("retention must cover all channels; audit >= 365 days")
    return errs


def load(path: Path | None = None) -> CapturePolicy:
    p = path or CONFIG_DIR / "trace-policy.yaml"
    doc = yaml.safe_load(p.read_text())
    errs = validate(doc)
    if errs:
        raise PolicyError("; ".join(errs))
    return CapturePolicy(dict(doc["capture_levels"]), bool(doc["ai_raw_prompt_response_capture"]),
                         {k: int(v) for k, v in doc["per_channel_retention_days"].items()}, sha256_file(p),
                         int(doc.get("human_info_summary_max_chars", 160)))


class PolicyHolder:
    """Live-reloading holder: keeps the last valid policy if a reload is invalid."""

    def __init__(self, path: Path | None = None):
        self.path = path or CONFIG_DIR / "trace-policy.yaml"
        self.policy = load(self.path)
        self.mtime = self.path.stat().st_mtime
        self.rejections: list[str] = []

    def current(self) -> CapturePolicy:
        from .emit import emit

        m = self.path.stat().st_mtime
        if m != self.mtime:
            self.mtime = m
            try:
                new = load(self.path)
                emit("audit", "INFO", f"trace capture policy reloaded sha={new.sha256[:12]}")
                self.policy = new
            except (PolicyError, yaml.YAMLError, KeyError, TypeError) as exc:
                self.rejections.append(str(exc)[:200])
                emit("audit", "WARN", f"trace capture policy change REJECTED: {str(exc)[:100]}")
                emit("security", "WARN", "attempt to weaken mandatory trace capture rejected")
        return self.policy
