"""Export Forge-C work orders as queue records for the external `fabro_dashboard` (Fabro Monitor) project.

The monitor reads generic queue JSON (`queue_id`, `status`, `items[{id,title,status,run_id,depends_on}]`,
`run_id`, `notes`) via a project `queue_globs` entry and links items to native Fabro runs. This module writes
`workorders/<WO>/dashboard/queue.json` from recorded, deterministic evidence only (gate log, inspections,
package record); agent claims are never shown as status. Model-free; called by the supervisor every poll.
No secrets and no workproduct content are exported, only statuses and short gate reasons.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..common import state_dir, utc_now
from ..inspection.engine import PHASES

SCOPE_NOTE = "Offline review candidate only; not a safety approval or production release."


def _gate_log(ws: Path) -> list[dict]:
    log = ws / ".forge-run" / "gates" / "gate-log.jsonl"
    out = []
    for line in log.read_text().splitlines() if log.is_file() else []:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _phase_item(phase: str, rows: list[dict], terminal: bool) -> dict:
    mine = [r for r in rows if r.get("phase") == phase]
    passed = any(r.get("step") == "inspect" and (r.get("gate") or {}).get("decision") == "PASS" for r in mine)
    blocked = any(r.get("step") == "route" and (r.get("gate") or {}).get("decision") == "BLOCKED" for r in mine)
    cancelled = any(r.get("step") == "governor" for r in rows)
    reworks = sum(1 for r in mine if r.get("step") == "route" and (r.get("gate") or {}).get("decision") == "REWORK")
    if passed:
        status, why = "succeeded", "inspection PASS"
    elif blocked:
        status = "blocked"
        why = next((r["gate"].get("reason") for r in reversed(mine) if r.get("step") == "route"), "") or "BLOCKED"
    elif mine and terminal:
        status, why = ("cancelled", "token/turn governor") if cancelled else ("failed", "run ended")
    elif mine:
        status, why = "running", f"rework cycles: {reworks}" if reworks else "in progress"
    else:
        status, why = ("not_reached" if terminal else "pending"), ""
    last_verify = next((r for r in reversed(mine) if r.get("step") == "verify"), None)
    if last_verify:
        why += f"; HAL guideline+register map verify {last_verify.get('verdict')}"
    title = f"{phase} author → deterministic gates → inspector" + (f" — {why}" if why else "")
    return {"id": phase, "title": title[:200], "status": status}


def export_workorder(ws: Path, run_status: str | None = None) -> dict:
    run_dir = ws / ".forge-run"
    rid_f, pkg_f = run_dir / "fabro_run_id", run_dir / "package.json"
    run_id = rid_f.read_text().strip() if rid_f.is_file() else None
    pkg = json.loads(pkg_f.read_text()) if pkg_f.is_file() else None
    terminal = pkg is not None or (run_status or "").upper() in ("SUCCEEDED", "FAILED", "CANCELLED", "CANCELED", "DEAD")
    rows = _gate_log(ws)
    governed = any(r.get("step") == "governor" for r in rows)
    items, prev = [], None
    for phase in PHASES:
        it = {**_phase_item(phase, rows, terminal), "run_id": run_id, "depends_on": [prev] if prev else []}
        frontier = prev is None or items[-1]["status"] == "succeeded"
        if frontier and it["status"] in ("pending", "not_reached"):  # the phase the run is in (or stopped in)
            it["status"] = ("cancelled" if governed else "failed") if terminal else "running"
            if terminal:
                it["title"] += " — " + ("cancelled by token/turn governor" if governed else "run ended in this phase")
        items.append(it)
        prev = phase
    if pkg:
        pstat = pkg.get("package_status", "UNKNOWN")
        items.append({"id": "package", "title": f"Deterministic finalizer — {pstat} ({pkg.get('gap_count', '?')} gaps)",
                      "status": "blocked" if pstat == "BLOCKED" else pstat.lower(), "run_id": run_id,
                      "depends_on": ["SWE.6"]})
        status = pstat.lower()
        note = f"{pstat}: {pkg.get('gap_count', '?')} gaps · archive sha256 {pkg.get('archive_sha256', '')[:12]} · {SCOPE_NOTE}"
    else:
        items.append({"id": "package", "title": "Deterministic finalizer (READY_FOR_OFFLINE_REVIEW | BLOCKED)",
                      "status": "pending", "run_id": run_id, "depends_on": ["SWE.6"]})
        status = "running" if not terminal else "finalizing"
        note = SCOPE_NOTE
    rec = {"schema": "forge-c/fabro-monitor-queue/0.1", "queue_id": ws.parent.name, "status": status,
           "run_id": run_id, "items": items, "notes": note, "exported_at": utc_now(),
           "source": "Forge-C deterministic gate log + package record"}
    out = ws.parent / "dashboard" / "queue.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1, sort_keys=True))
    os.replace(tmp, out)  # atomic: the monitor never reads a half-written file
    return rec


def export_all(status_of=None) -> int:
    root = state_dir() / "workorders"
    n = 0
    for ws in sorted(root.glob("*/workspace")) if root.is_dir() else []:
        rid_f = ws / ".forge-run" / "fabro_run_id"
        if not rid_f.is_file():
            continue
        out = ws.parent / "dashboard" / "queue.json"
        pkg = ws / ".forge-run" / "package.json"
        if out.is_file() and pkg.is_file() and out.stat().st_mtime >= pkg.stat().st_mtime:
            continue  # finished and already exported
        st = None
        if status_of is not None and not pkg.is_file():
            try:
                st = status_of(rid_f.read_text().strip())
            except Exception:  # noqa: BLE001 - status is optional; the gate log alone is still exported
                st = None
        export_workorder(ws, st)
        n += 1
    return n


def main() -> int:
    print(json.dumps({"exported": export_all()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
