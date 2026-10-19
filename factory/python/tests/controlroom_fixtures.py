"""CR-T004: fixture work-order workspaces for the Control Room tests (real gate-log vocabulary, research R2)."""
from __future__ import annotations

import json
from pathlib import Path

CFG = {"schema": "forge-c/controlroom-config/0.1", "tz": "Europe/Lisbon",
       "shifts": [{"name": "Day", "start": "00:00", "end": "24:00"}], "staleness_s": 120, "idle_threshold_s": 600,
       "lead_time_limit_s": 21600, "rework_near_ratio": 0.67, "yield_threshold": 0.5,
       "spc": {"min_subgroups": 10, "min_n": 50, "min_points": 15, "rules": ["WE1", "WE2", "WE3"]}, "prices": {}}


def ts(minute: float, base: str = "2026-10-19T10:00:00") -> str:
    from datetime import datetime, timedelta

    return (datetime.fromisoformat(base) + timedelta(minutes=minute)).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def frozen(phase, m):
    return {"phase": phase, "step": "author", "result": "FROZEN", "baseline_id": f"BL-{phase}", "ts": ts(m)}


def rejected(phase, m, issue="CONTRACT_SWR_NOT_COVERED:SWR-005 (add its effects)"):
    return {"phase": phase, "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": [issue], "ts": ts(m)}


def inspect(phase, m, decision="PASS"):
    return {"phase": phase, "step": "inspect", "gate": {"phase": phase, "decision": decision,
                                                        "reason": f"INS-{phase}-001"}, "ts": ts(m)}


def route(phase, m, decision="REWORK", reason="NO_BASELINE"):
    return {"phase": phase, "step": "route", "gate": {"phase": phase, "decision": decision, "reason": reason}, "ts": ts(m)}


def passed(phase, m):
    return [frozen(phase, m), inspect(phase, m + 1)]


def workspace(root: Path, wo: str, rows: list[dict], created: str = "2026-10-19T09:59:00Z", package: str | None = None,
              finalized: str | None = None, run_id: str | None = "RUN-1", profile: dict | None = None,
              layer: str = "LL") -> Path:
    ws = root / wo / "workspace"
    (ws / ".forge-run/gates").mkdir(parents=True, exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({
        "work_order": wo, "created_at": created, "layer": layer, "driver": "STM32N6 RCC low-level (LL) driver",
        "target": {"part_number": "STM32N657X0"}, "budgets": {}}))
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    if run_id:
        (ws / ".forge-run/fabro_run_id").write_text(run_id)
    if package:
        (ws / ".forge-run/package.json").write_text(json.dumps({
            "package_status": package, "finalized_at": finalized or ts(120), "archive_sha256": "ab" * 32,
            "archive": f"/archives/{wo}/{wo}-review.zip", "archive_ref": "archive:sha256:" + "ab" * 32,
            "gap_count": 3, "gaps": [], "run_id": wo}))
    (ws / ".forge-run/model-profile.json").write_text(json.dumps(profile or {
        "default": "deepseek-flash", "provider": "deepseek", "nodes": [],
        "acp_authors": {"model": "gpt-6.1-sol", "provider": "openai-codex"},
        "acp_inspectors": {"model": "claude-opus-5-5", "provider": "anthropic-claude"}}))
    return ws


def append(ws: Path, *rows: dict) -> None:
    with (ws / ".forge-run/gates/gate-log.jsonl").open("a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


class FakeProbe:
    """Stands in for the Fabro run probe: lifecycle per run id (default running), current node, newest event."""

    def __init__(self, lifecycle: dict | None = None, last_ts: str | None = None):
        self.lifecycle, self.last_ts = lifecycle or {}, last_ts

    def status(self, ws, run_id):
        return {"lifecycle": self.lifecycle.get(run_id, "running"), "node": "swe2_author", "last_ts": self.last_ts,
                "error": None}
