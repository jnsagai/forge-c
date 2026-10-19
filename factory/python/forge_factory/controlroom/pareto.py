"""Quality history from the gate logs (CR-T024; research R5, R6): per-station first-pass outcomes, time to pass, and
the Pareto of loss reasons. Everything is a count of recorded gate decisions; nothing is inferred.

Loss reasons per station and window:
  BLOCKED   route BLOCKED / inspect BLOCKED / governor budget: the gate reason, digits normalised to N
            ('rework budget exhausted (3 failed cycles)' -> 'rework budget exhausted (N failed cycles)'),
            'STUCK: ...' -> 'STUCK'
  REWORK    inspection REWORK: the major/critical checklist findings of that inspection record (e.g. SWE4-02)
  REJECTED  author gate REJECTED: each issue's code ('CONTRACT_SWR_NOT_COVERED:SWR-005 (...)' -> its code)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..common import state_dir
from ..inspection.engine import PHASES
from .floor import BLOCK, PASS, GateLogReader, code, decision


def _t(s: str | None) -> float | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def block_code(row: dict) -> str:
    g = row.get("gate") or {}
    txt = str(g.get("reason") or (row.get("issues") or [row.get("result") or "BLOCKED"])[0])
    if txt.startswith("STUCK"):
        return "STUCK (identical deterministic rejection)"
    if decision(row) == ("governor", "TOKEN_BUDGET_EXHAUSTED"):
        return "TOKEN_BUDGET_EXHAUSTED"
    return re.sub(r"\d+", "N", txt)[:120]


def _inspection_findings(ws: Path, phase: str, ins_id: str | None) -> list[str]:
    if not ins_id or not re.fullmatch(r"INS-SWE\.[1-6]-\d{3}", str(ins_id)):
        return []
    try:
        rec = json.loads((ws / "inspection" / phase / f"{ins_id}.json").read_text())
    except (OSError, ValueError):
        return []
    return [str(f.get("id") or "UNSPECIFIED") for f in rec.get("findings", [])
            if f.get("severity") in ("major", "critical")] or ["NO_MAJOR_FINDING_RECORDED"]


class History:
    def __init__(self, root: Path | None = None, reader: GateLogReader | None = None) -> None:
        self.root, self.reader = root, reader or GateLogReader()

    def _workspaces(self) -> list[Path]:
        r = self.root or state_dir() / "workorders"
        return sorted(r.glob("*/workspace")) if r.is_dir() else []

    def rows(self, start: str, end: str) -> list[tuple[Path, dict]]:
        out = []
        for ws in self._workspaces():
            for r in self.reader.rows(ws / ".forge-run/gates/gate-log.jsonl"):
                if r.get("phase") in PHASES and start <= str(r.get("ts", ""))[:19] + "Z" <= end:
                    out.append((ws, r))
        return out

    def pareto(self, start: str, end: str, station: str | None = None) -> list[dict]:
        counts: dict[tuple, list] = defaultdict(list)
        for ws, r in self.rows(start, end):
            ph = r["phase"]
            if station and ph != station:
                continue
            ref = {"work_order": ws.parent.name, "line": r.get("_line")}
            d = decision(r)
            if d in BLOCK:
                counts[(ph, "BLOCKED", block_code(r))].append(ref)
            elif d == ("inspect", "REWORK"):
                for f in _inspection_findings(ws, ph, (r.get("gate") or {}).get("reason")):
                    counts[(ph, "REWORK", f)].append(ref)
            elif d == ("author", "REJECTED"):
                for c in sorted({code(i) for i in (r.get("issues") or r.get("errors") or ["UNSPECIFIED"])}):
                    counts[(ph, "REJECTED", c)].append(ref)
        items = sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        total = sum(len(v) for _, v in items) or 1
        out, cum = [], 0
        for (ph, kind, rc), refs in items:
            cum += len(refs)
            out.append({"station": ph, "kind": kind, "reason_code": rc, "count": len(refs),
                        "cumulative_share": round(cum / total, 4), "refs": refs[:30]})
        return out

    def first_pass_groups(self, start: str, end: str, station: str, tz: str) -> list[dict]:
        """Daily subgroups (local days) of first inspection outcomes per run at `station`."""
        z = ZoneInfo(tz)
        first: dict[str, dict] = {}
        for ws, r in self.rows(start, end):
            if r["phase"] == station and r.get("step") == "inspect" and ws.parent.name not in first:
                first[ws.parent.name] = r
        days: dict[str, dict] = {}
        for wo, r in sorted(first.items(), key=lambda kv: kv[1]["ts"]):
            day = datetime.fromtimestamp(_t(r["ts"]) or 0, UTC).astimezone(z).date().isoformat()
            g = days.setdefault(day, {"t": day, "passes": 0, "n": 0, "units": []})
            g["n"] += 1
            g["passes"] += decision(r)[1] == "PASS"
            g["units"].append(wo)
        return [days[k] for k in sorted(days)]

    def time_to_pass(self, start: str, end: str, station: str) -> list[dict]:
        """Per run: station dwell time to pass = from the pass of the previous station (arrival), or from the
        first record at the station for SWE.1 or a resumed run, to the pass at `station`; in completion order."""
        prev = PHASES[PHASES.index(station) - 1] if station != PHASES[0] else None
        per: dict[str, list] = defaultdict(list)
        arrive: dict[str, float] = {}
        for ws, r in self.rows(start, end):
            if r["phase"] == station:
                per[ws.parent.name].append(r)
            elif prev and r["phase"] == prev and decision(r) in PASS:
                arrive[ws.parent.name] = _t(r.get("ts")) or 0.0
        pts = []
        for wo, rs in per.items():
            p = next((r for r in rs if decision(r) in PASS), None)
            t0, t1 = arrive.get(wo) or _t(rs[0].get("ts")), _t(p.get("ts")) if p else None
            if p and t0 is not None and t1 is not None:
                pts.append({"t": p["ts"], "value": round(t1 - t0, 1), "units": [wo]})
        return sorted(pts, key=lambda x: x["t"])
