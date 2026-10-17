"""EASA-T056 — read-only Assurance projections for the existing 002/003/004 dashboard (no second data store):
task/FR status from evidence records, per-work-order observe-only gate decisions, the six trace matrices with their
uncovered items, and the independence attestation. Raw prompts/responses are never exposed."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from ..common import REPO_ROOT, state_dir
from . import matrix, package

STATUS = REPO_ROOT / "evidence/easa/status/easa-matrix.json"
WO_RX = re.compile(r"^WO-[A-Za-z0-9._-]{1,80}$")


def summary() -> dict:
    rep = json.loads(STATUS.read_text()) if STATUS.is_file() else matrix.build()
    return {"git_head": rep["git_head"][:12], "generated_at": rep["generated_at"], "task_counts": rep["task_counts"],
            "fr_counts": rep["fr_counts"], "statement": rep["statement"],
            "blocked_or_open": sorted(t for t, v in rep["tasks"].items() if v["status"] not in ("PASS",))[:80]}


def _ws(wo: str) -> Path:
    if not WO_RX.match(wo):
        raise ValueError("bad work order id")
    return state_dir() / "workorders" / wo / "workspace"


def workorders(limit: int = 30) -> list[dict]:
    root = state_dir() / "workorders"
    out = []
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True) if root.is_dir() else []:
        ws = d / "workspace"
        log = ws / ".forge-run/assurance/gate-log.jsonl"
        if not log.is_file():
            continue
        last = {}
        for line in log.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            last[r.get("phase")] = r.get("state")
        out.append({"work_order": d.name, "assurance_gates": last,
                    "matrices": len(list(ws.glob("workproducts/SWE.*/traceability/matrix_*.csv")))})
        if len(out) >= limit:
            break
    return out


def workorder(wo: str) -> dict:
    ws = _ws(wo)
    mats = []
    for p in sorted(ws.glob("workproducts/SWE.*/traceability/matrix_*.csv")):
        rows = list(csv.DictReader(io.StringIO(p.read_text())))
        md = p.with_suffix(".md")
        unc = re.search(r"Uncovered items: (.*)", md.read_text()).group(1) if md.is_file() else "unknown"
        mats.append({"matrix": p.name, "rows": len(rows), "uncovered": unc})
    return {"work_order": wo, "gate_log": package._gate_log(ws)[-12:], "matrices": mats,
            "independence": package.attestation(ws)}
