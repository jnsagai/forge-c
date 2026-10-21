"""LRTX-T023 (LRTX-FR-016): compare a smaller model with the 30B model per structured author task.

    python -m forge_factory.lrtx.modelcmp --workspace <frozen start ws> --model qwen3:8b --model qwen3-coder:30b \
        --repeat 3 --out <report.json> [--phase SWE.2]

SWE.1 (default) or SWE.2. For SWE.2 the start workspace needs a frozen, inspected SWE.1 baseline, e.g. a copy of a
READY work order; the SWE.2 author is then measured on its own, independently of any local SWE.1 inspection (T016).

Runs inside the profile namespace. Each attempt:
1. copies one frozen start workspace and removes the phase's authorship from the copy; the original is never written;
2. runs the real structured visit of the phase with the role's call budget, i.e. the same tasks, validators, localized
   repair and consistency checks as a work order;
3. freezes the result through the unchanged author gate.

Measured per model and per task:
- validity at the first call and after repair;
- calls (retries included), prompt and output tokens, call wall time;
- the model load time observed by the admission gateway. Loading a different model is the switching cost.

A mixed-routing estimate (smaller model for some tasks) is derived from these measurements and labelled DERIVED,
never MEASURED. Authors only: qualifying a model as inspector stays a separate decision (LRTX-FR-016).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import time
from pathlib import Path

from ..common import pretty_json, utc_now


def _fresh_copy(src: Path, dst: Path, phase: str = "SWE.1") -> Path:
    """Copy of the start workspace without earlier authorship of `phase` (checkpoints, work products, gate records)."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns("build"))
    for rel in (f".forge-run/lrtx/{phase}", f".forge-run/lrtx/{phase}-inspect", f"workproducts/{phase}",
                f"inspection/{phase}", f"configuration/baselines/{phase}"):
        p = dst / rel
        if p.is_dir():
            shutil.rmtree(p)
    log = dst / ".forge-run/gates/gate-log.jsonl"
    if log.is_file():
        log.write_text("".join(x + "\n" for x in log.read_text().splitlines() if f'"{phase}"' not in x))
    return dst


def _loads(meter: Path, t0: str, t1: str) -> list[dict]:
    rows = []
    for line in meter.read_text().splitlines() if meter.is_file() else []:
        r = json.loads(line)
        if t0 <= r.get("ts_utc", "") <= t1 and "local" in r:
            ld = r["local"].get("load") or {}
            if r["local"].get("model_loaded_before") is False:
                rows.append({"model": r.get("model"), "load_ms": ld.get("load_ms")})
    return rows


def attempt(start: Path, scratch: Path, model: str, n: int, meter: Path, max_calls: int, phase: str = "SWE.1") -> dict:
    from . import swe1, swe2
    from .seeded import _refreeze

    ws = _fresh_copy(start, scratch / f"{model.replace(':', '_')}-{n:02d}" / "workspace", phase)
    t0, w0 = utc_now(), time.monotonic()
    rep = {"SWE.1": swe1, "SWE.2": swe2}[phase].visit(ws, model, max_calls=max_calls)
    wall = round(time.monotonic() - w0, 1)
    vs = ws / f".forge-run/lrtx/{phase}/visits.jsonl"
    vrec = json.loads(vs.read_text().splitlines()[-1]) if vs.is_file() else {}
    tasks: dict[str, dict] = {}
    for ck in sorted((ws / f".forge-run/lrtx/{phase}").glob("packets/*.json")):
        c = json.loads(ck.read_text())
        att = c.get("attempts") or []
        tasks[c["task"]] = {"status": c["status"], "calls": len(att), "first_call_valid": bool(att) and not att[0]
                            .get("errors"), "prompt_tokens": sum((a.get("usage") or {}).get("prompt_tokens") or 0
                                                                 for a in att),
                            "output_tokens": sum((a.get("usage") or {}).get("completion_tokens") or 0 for a in att),
                            "call_wall_ms": round(sum(a.get("wall_ms") or 0 for a in att), 1)}
    gate = _refreeze(ws, phase) if rep["status"] == "PASS" else {"result": "NOT_RUN (visit FAILED)"}
    return {"model": model, "n": n, "phase": phase, "visit": rep["status"], "issues": (rep.get("issues") or [])[:10],
            "calls": vrec.get("calls"), "wall_s": wall, "gate": gate.get("result"), "tasks": tasks,
            "model_loads": _loads(meter, t0, utc_now()), "workspace": str(ws)}


def summarise(rows: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for m in sorted({r["model"] for r in rows}):
        rs = [r for r in rows if r["model"] == m]
        per: dict[str, dict] = {}
        for r in rs:
            for t, v in r["tasks"].items():
                p = per.setdefault(t, {"attempts": 0, "first_call_valid": 0, "valid": 0, "calls": [], "tokens": [],
                                       "call_wall_ms": []})
                p["attempts"] += 1
                p["first_call_valid"] += v["first_call_valid"]
                p["valid"] += v["status"] == "VALID"
                p["calls"].append(v["calls"])
                p["tokens"].append(v["prompt_tokens"] + v["output_tokens"])
                p["call_wall_ms"].append(v["call_wall_ms"])
        loads = [x["load_ms"] for r in rs for x in r["model_loads"] if x.get("model") == m and x.get("load_ms")]
        out[m] = {"attempts": len(rs), "visit_pass": sum(r["visit"] == "PASS" for r in rs),
                  "gate_frozen": sum(str(r["gate"]).startswith("FROZEN") for r in rs),
                  "wall_s_median": statistics.median([r["wall_s"] for r in rs]) if rs else None,
                  "calls_median": statistics.median([r["calls"] or 0 for r in rs]) if rs else None,
                  "load_ms_median": statistics.median(loads) if loads else "UNKNOWN (no load observed)",
                  "per_task": {t: {**{k: p[k] for k in ("attempts", "first_call_valid", "valid")},
                                   "calls_median": statistics.median(p["calls"]),
                                   "tokens_median": statistics.median(p["tokens"]),
                                   "call_wall_ms_median": statistics.median(p["call_wall_ms"])}
                               for t, p in sorted(per.items())}}
    return out


def mixed_estimate(by_model: dict, small: str, large: str) -> dict | str:
    """DERIVED: the small model for every task where it was valid in every attempt, else the large one, plus one
    model switch per switch in the task order. Never a measurement."""
    if small not in by_model or large not in by_model:
        return "NOT_AVAILABLE (both models must have been measured)"
    S, L = by_model[small]["per_task"], by_model[large]["per_task"]
    plan = {t: small if S.get(t, {}).get("valid") == S.get(t, {}).get("attempts", -1) else large for t in L}
    order = list(plan.values())
    switches = sum(1 for a, b in zip(order, order[1:], strict=False) if a != b)
    loads = [by_model[m]["load_ms_median"] for m in (small, large)]
    lms = None if any(isinstance(x, str) for x in loads) else max(loads)
    wall = sum((S if m == small else L)[t]["call_wall_ms_median"] for t, m in plan.items())
    return {"basis": "DERIVED from per-task medians; not measured", "plan": plan, "switches": switches,
            "call_wall_ms": round(wall + (lms or 0) * switches, 1),
            "switch_cost_ms": "UNKNOWN" if lms is None else lms * switches,
            "large_only_call_wall_ms": round(sum(v["call_wall_ms_median"] for v in L.values()), 1)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", type=Path, required=True, help="frozen start workspace (read-only)")
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--max-calls", type=int, default=35)
    ap.add_argument("--phase", choices=("SWE.1", "SWE.2"), default="SWE.1")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    meter = Path(os.environ.get("FORGE_STATE_DIR", "")) / "llm-gateway/usage.jsonl"
    scratch = a.out.parent / (a.out.stem + "-workspaces")
    rows = []
    for n in range(1, a.repeat + 1):  # interleaved, so load/switch costs and thermal drift hit every model
        for m in a.model:
            rows.append(attempt(a.workspace.resolve(), scratch, m, n, meter, a.max_calls, a.phase))
            by = summarise(rows)
            rep = {"schema": "forge-c/lrtx-modelcmp/1", "generated_at": utc_now(), "start_workspace":
                   str(a.workspace), "phase": a.phase, "models": a.model, "repeat": a.repeat, "by_model": by,
                   "mixed_estimate": mixed_estimate(by, a.model[0], a.model[-1]) if len(a.model) > 1 else None,
                   "rows": rows, "note": "Authors only; inspector qualification is a separate decision. Pilot "
                                         "measurement on one work order, not a model qualification."}
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(pretty_json(rep))
    print(json.dumps({m: {k: v for k, v in s.items() if k != "per_task"} for m, s in summarise(rows).items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
