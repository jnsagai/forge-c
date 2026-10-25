"""Feature 015 (FR-006, F015-T070): the ST-driver benchmark record, built from recorded evidence only.

Every work order of the benchmark (AFO orders BENCH-*, queue-runner work orders WO-BENCH-*) gets one entry: factory
revision, input and delivered-code hashes, native Fabro run id, model profile, phase verdicts (inspection passes,
reworks, the routing decision that ended the phase), package status and gaps, conformance and defects, duration and
the agents' token usage. Failed and blocked outcomes are kept as they are; nothing is judged here (the gates,
inspectors and release manager decided). The AFO conductor database is opened read-only.

    python -m forge_factory.benchmark.record [--out DIR]   # default: print; DIR: record.json + record.md
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from ..common import state_dir, utc_now
from .queue import PHASES, QUEUE, _elapsed_s, load, read_state

SCHEMA = "forge-c/st-driver-benchmark-record/0.1"


def _jsonl(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def afo_orders(db: Path | None = None) -> list[dict]:
    """BENCH-* orders and their attempts from the AFO conductor database (read-only)."""
    db = db or state_dir() / "conductor/conductor.sqlite3"
    if not db.is_file():
        return []
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        orders = [dict(r) for r in c.execute("SELECT * FROM afo_work_orders ORDER BY created_epoch")]
        out = []
        for o in orders:
            env = json.loads(o.get("envelope") or "{}")
            if not str(env.get("request_id", "")).startswith("BENCH-"):
                continue
            atts = [dict(r) for r in c.execute("SELECT * FROM afo_attempts WHERE order_id=? ORDER BY seq",
                                               (o["order_id"],))]
            out.append({"order_id": o["order_id"], "request_id": env["request_id"], "state": o["state"],
                        "envelope": {k: env.get(k) for k in ("driver_class", "model_profile", "git_revision",
                                                             "manifest_sha256", "input_manifest_ref",
                                                             "authorization_ref", "submitted_utc")},
                        "attempts": [{"attempt_id": a["attempt_id"], "state": a["state"]} for a in atts]})
        return out
    finally:
        c.close()


def phases(rows: list[dict]) -> dict:
    """Per phase: inspections, reworks and the verdict of the last decisive gate-log row (an inspection PASS ends a
    phase; route rows record REWORK / UPSTREAM / BLOCKED); INCOMPLETE when the phase started but nothing decided."""
    out = {}
    for p in PHASES:
        mine = [r for r in rows if r.get("phase") == p]
        if not mine:
            continue
        gates = [(r.get("step"), r["gate"]) for r in mine if r.get("step") in ("inspect", "route")
                 and isinstance(r.get("gate"), dict)]
        insp = [g for s, g in gates if s == "inspect"]
        decisive = [g for s, g in gates if s == "route" or g.get("decision") == "PASS"]
        out[p] = {"inspections_passed": sum(1 for g in insp if g.get("decision") == "PASS"),
                  "inspections_failed": sum(1 for g in insp if g.get("decision") not in (None, "PASS")),
                  "reworks": sum(1 for s, g in gates if s == "route" and g.get("decision") == "REWORK"),
                  "upstream_returns": sum(1 for s, g in gates if s == "route" and g.get("decision") == "UPSTREAM"),
                  "final": decisive[-1].get("decision") if decisive else "INCOMPLETE",
                  "final_reason": (decisive[-1].get("reason") if decisive else None)}
    return out


def usage(acp: Path) -> dict:
    """Token usage the ACP proxy recorded per node, summed per model and per role (author/inspector/other)."""
    per_model: dict[str, dict] = {}
    per_role: dict[str, dict] = {}
    for f in sorted(acp.glob("*.proxy.jsonl")) if acp.is_dir() else []:
        node = f.name.removesuffix(".proxy.jsonl")
        role = "inspector" if "inspector" in node else "author" if ("author" in node or "triage" in node) else "other"
        for e in _jsonl(f):
            if e.get("event") != "usage":
                continue
            for bucket in (per_model.setdefault(str(e.get("model")), {}), per_role.setdefault(role, {})):
                bucket["calls"] = bucket.get("calls", 0) + 1
                for k in ("input", "output", "cache_read", "cache_write"):
                    bucket[k] = bucket.get(k, 0) + int(e.get(k) or 0)
    return {"per_model": per_model, "per_role": per_role}


def work_order(ws: Path) -> dict:
    fr = ws / ".forge-run"
    m = _json(fr / "manifest.json")
    pkg = _json(fr / "package.json")
    rows = _jsonl(fr / "gates/gate-log.jsonl")
    prof = _json(fr / "model-profile.json")
    cf = (_json(fr / "delivery/conformance.json").get("findings")) or []
    defects = [_json(p) for p in sorted((fr / "defects").glob("DEF-*.json"))] if (fr / "defects").is_dir() else []
    run_id = (fr / "fabro_run_id").read_text().strip() if (fr / "fabro_run_id").is_file() else None
    started = m.get("created_at")
    return {
        "work_order": ws.parent.name, "peripheral": m.get("peripheral"), "code_mode": m.get("code_mode"),
        "driver": m.get("driver"), "fabro_run_id": run_id,
        "factory_revision": (m.get("factory_revision") or {}).get("commit"),
        "factory_revision_dirty": (m.get("factory_revision") or {}).get("dirty"),
        "peripheral_profile_sha256": m.get("peripheral_profile_sha256"),
        "inputs": [{"path": i.get("path"), "sha256": i.get("sha256")} for i in m.get("inputs") or []],
        "delivered_code": [{"path": d.get("path"), "sha256": d.get("sha256")} for d in m.get("delivered") or []
                           if d.get("role") == "delivered_code"],
        "models": {"authors": (prof.get("acp_authors") or {}).get("model"),
                   "inspectors": (prof.get("acp_inspectors") or {}).get("model"),
                   "run_model": prof.get("default"), "run_model_note": prof.get("run_model_note")},
        "phases": phases(rows),
        "package": {"status": pkg.get("package_status"), "gap_count": pkg.get("gap_count"),
                    "gaps": pkg.get("gaps") or [], "archive_sha256": pkg.get("archive_sha256"),
                    "finalized_at": pkg.get("finalized_at")} if pkg else None,
        "conformance": {"open": sum(1 for f in cf if f.get("status", "OPEN") == "OPEN"),
                        "deferred": sum(1 for f in cf if f.get("status") == "DEFERRED")},
        "defects": [{"id": d.get("id"), "kind": d.get("kind"), "status": d.get("status")} for d in defects],
        "started_at": started, "duration_s": _elapsed_s(started, pkg.get("finalized_at")) if started and pkg else None,
        "usage": usage(fr / "acp"),
    }


def collect(queue_path: Path = QUEUE) -> dict:
    q = load(queue_path)
    wdir = state_dir() / "workorders"
    entries = []
    for o in afo_orders():
        for a in o["attempts"]:
            ws = wdir / ("WO-AFO-" + a["attempt_id"].removeprefix("afo-")) / "workspace"
            entries.append({"route": "AFO", "request_id": o["request_id"], "order_id": o["order_id"],
                            "order_state": o["state"], "attempt_id": a["attempt_id"], "attempt_state": a["state"],
                            "envelope": o["envelope"], **(work_order(ws) if ws.is_dir() else {"work_order": None})})
    for item, rec in sorted(read_state(q)["items"].items()):
        for a in rec.get("attempts", []):
            ws = wdir / a["work_order"] / "workspace"
            entries.append({"route": "queue-runner", "item": item, "launch_error": a.get("launch_error"),
                            **(work_order(ws) if ws.is_dir() else {"work_order": a["work_order"]})})
    return {"schema": SCHEMA, "queue": q["id"], "recorded_at": utc_now(), "entries": entries}


def markdown(rec: dict) -> str:
    L = [f"# ST-driver benchmark record ({rec['queue']})", "",
         f"Recorded {rec['recorded_at']} from evidence only (schema {rec['schema']}). Nothing here is a READY or "
         "safety claim; BLOCKED outcomes are kept as recorded.", "",
         "| work order | route | peripheral | revision | phases (final) | package | gaps | duration | author / inspector "
         "tokens (in+out) |", "|---|---|---|---|---|---|---|---|---|"]
    for e in rec["entries"]:
        ph = " ".join(f"{p[-1]}:{(v.get('final') or '-')[:4]}" for p, v in (e.get("phases") or {}).items())
        pk = e.get("package") or {}
        u = (e.get("usage") or {}).get("per_role") or {}

        def tok(r, u=u):
            return (u.get(r) or {}).get("input", 0) + (u.get(r) or {}).get("output", 0)
        dur = f"{e['duration_s'] / 60:.0f} min" if e.get("duration_s") else "-"
        L.append(f"| {e.get('work_order') or '-'} | {e['route']} | {e.get('peripheral') or '-'} | "
                 f"{(e.get('factory_revision') or '-')[:7]} | {ph or '-'} | {pk.get('status') or 'NO_PACKAGE'} | "
                 f"{pk.get('gap_count', '-')} | {dur} | {tok('author')} / {tok('inspector')} |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queue", type=Path, default=QUEUE)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    rec = collect(a.queue)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "record.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        (a.out / "record.md").write_text(markdown(rec))
        print(json.dumps({"entries": len(rec["entries"]), "out": str(a.out)}))
    else:
        print(markdown(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
