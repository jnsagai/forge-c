"""LRTX-T024 (spec acceptance 5): the frozen local-only evaluation campaign.

    python -m forge_factory.lrtx.campaign --campaign specs/010-local-rtx-optimization/campaign.yaml --out <dir>

The case mix is frozen before running: the campaign file is hashed into every record, and a changed file is refused
for an existing output directory. The runner works inside the profile's namespace (`lrtx.stack exec`) and runs one
case at a time to completion. Per case it records:
- package status and gaps;
- the run verification (`verify_run`);
- the stage/call/resource/energy metrics (`runmetrics`);
- the factory revision;
- a failure classification (first non-PASS phase and its last gate reason).

Every attempt counts, and a case that fails to launch is recorded as an INFRASTRUCTURE failure, never skipped. The
runner is resumable: completed cases are not run again. The summary reports READY counts with a Wilson interval,
and time/tokens/energy per accepted work order including the failed attempts. It is a pilot operational measurement,
not a reliability proof or a safety qualification.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, sha256_file, utc_now


def load(path: Path) -> dict:
    import yaml

    d = yaml.safe_load(path.read_text())
    if d.get("schema") != "forge-c/lrtx-campaign/1" or not d.get("cases"):
        raise ValueError(f"CAMPAIGN_INVALID:{path}")
    return d


def expand(c: dict) -> list[dict]:
    out = []
    for case in c["cases"]:
        for n in range(1, int(case.get("repeat", 1)) + 1):
            out.append({**case, "run": f"{case['id']}-{c['tag']}{n:02d}"})
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 3), round((c + h) / d, 3))


def classify(ws: Path) -> dict:
    """The first phase that did not pass and the last gate reason recorded for it."""
    from ..inspection.engine import PHASES, Store

    if not (ws / ".forge-run/manifest.json").is_file():
        return {"blocked_phase": None, "reason": "no workspace (launch failure)", "kind": "INFRASTRUCTURE"}
    st = Store(ws)
    for ph in PHASES:
        g = st.gate(ph)
        if g["decision"] != "PASS":
            log = ws / ".forge-run/gates/gate-log.jsonl"
            rows = [json.loads(x) for x in (log.read_text().splitlines() if log.is_file() else [])]
            last = next((r for r in reversed(rows) if r.get("phase") == ph and r.get("step") == "route"), {})
            reason = (last.get("gate") or {}).get("reason") or g.get("reason")
            kind = "INFRASTRUCTURE" if any(x in str(reason) for x in ("timeout", "stall", "UNREACHABLE", "OOM")) \
                else "QUALITY_OR_FACTORY (triage per case)"
            return {"blocked_phase": ph, "reason": str(reason)[:300], "kind": kind}
    return {"blocked_phase": None, "reason": "all phases passed", "kind": "NONE"}


def import_provided(wo: str, env: dict, source_state: Path) -> dict:
    """Copy a verified LL work order of the existing deployment into the profile's state (read-only reference; the
    original is never written). Returns the provided header's hash for the case record."""
    import shutil

    from ..common import sha256_file as h
    from ..layer import ll_header

    src = source_state / "workorders" / wo / "workspace"
    dst = Path(env["FORGE_STATE_DIR"]) / "workorders" / wo / "workspace"
    if not (src / ".forge-run/manifest.json").is_file():
        raise FileNotFoundError(f"PROVIDED_SOURCE_MISSING:{src}")
    if not dst.is_dir():
        shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns("build"))
    hdr = ll_header(dst)
    if h(dst / hdr) != h(src / hdr):
        raise ValueError(f"PROVIDED_COPY_DIFFERS:{wo}:{hdr}")
    return {"work_order": wo, "header": hdr, "sha256": h(dst / hdr), "source": str(src), "copy": str(dst)}


def run_case(case: dict, model: str, env: dict) -> dict:
    from .runmetrics import collect
    from .verify_run import verify

    state = Path(env["FORGE_STATE_DIR"])
    ws = state / "workorders" / case["run"] / "workspace"
    argv = ["python", "-m", "forge_factory.workorder", "--example", str(REPO_ROOT / case["example"]), "--wo",
            case["run"], "--profile", case.get("profile", "local-rtx-v1"), "--model", model]
    provided = None
    if case.get("provided_from"):
        argv += ["--provided-from", case["provided_from"]]
        if case.get("import_from_deployment"):
            provided = import_provided(case["provided_from"], env, Path(env.get(
                "FORGE_LRTX_DEPLOYMENT_STATE", "/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/state")))
    t0 = time.monotonic()
    p = subprocess.run(argv, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=24 * 3600)
    rec = {"case": case["id"], "run": case["run"], "started_exit": p.returncode, "wall_s": round(time.monotonic() - t0, 1),
           "stdout_tail": p.stdout[-400:], "stderr_tail": p.stderr[-600:] if p.returncode else "",
           "provided": provided}
    pkg = ws / ".forge-run/package.json"
    rec["package_status"] = json.loads(pkg.read_text()).get("package_status") if pkg.is_file() else "NO_PACKAGE"
    rec["gap_count"] = json.loads(pkg.read_text()).get("gap_count") if pkg.is_file() else None
    rec["classification"] = classify(ws)
    if pkg.is_file():
        v = verify(ws, Path(env["FORGE_FABRO_STORAGE"]), state / "llm-gateway/usage.jsonl")
        rec["verification"] = {"status": v["status"], "checks": v["checks"]}
        m = collect(ws, Path(env["FORGE_FABRO_STORAGE"]), state / "llm-gateway/usage.jsonl")
        rec["metrics"] = {k: m.get(k) for k in ("window", "calls", "energy")}
        rec["factory_revision"] = json.loads((ws / ".forge-run/manifest.json").read_text()).get("factory_revision")
    return rec


def summary(c: dict, rows: list[dict], digest: str) -> dict:
    n = len(rows)
    ready = [r for r in rows if r.get("package_status") == "READY_FOR_OFFLINE_REVIEW"]
    tok = sum(((r.get("metrics") or {}).get("calls") or {}).get("prompt_tokens", {}).get("sum") or 0 for r in rows)
    wall = sum(r.get("wall_s") or 0 for r in rows)
    energy = [((r.get("metrics") or {}).get("energy") or {}).get("gpu_board_wh") for r in rows]
    e_known = [e for e in energy if isinstance(e, (int, float))]
    by_phase: dict[str, int] = {}
    for r in rows:
        ph = (r.get("classification") or {}).get("blocked_phase") or "none"
        by_phase[ph] = by_phase.get(ph, 0) + 1
    return {"schema": "forge-c/lrtx-campaign-summary/1", "campaign": c["tag"], "campaign_sha256": digest,
            "generated_at": utc_now(), "cases_planned": len(expand(c)), "cases_run": n,
            "ready": len(ready), "ready_wilson_95": wilson(len(ready), n),
            "target": c.get("target", "27/30 READY_FOR_OFFLINE_REVIEW (spec acceptance 5, proposed)"),
            "blocked_or_failed_by_phase": by_phase,
            "per_accepted_work_order": {"wall_s": round(wall / len(ready), 1) if ready else "NO_ACCEPTED_WORK_ORDER",
                                        "prompt_tokens": round(tok / len(ready)) if ready else "NO_ACCEPTED_WORK_ORDER",
                                        "gpu_wh": round(sum(e_known) / len(ready), 3) if ready and len(e_known) == n
                                        else "UNKNOWN (energy not measured for every attempt)",
                                        "basis": "all attempts, including failed ones, divided by accepted packages"},
            "rows": rows, "note": "Pilot operational criterion, not a reliability proof or safety qualification."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-cases", type=int, default=0, help="stop after this many new cases (0 = all)")
    a = ap.parse_args(argv)
    c = load(a.campaign)
    digest = sha256_file(a.campaign)
    a.out.mkdir(parents=True, exist_ok=True)
    lock = a.out / "campaign.sha256"
    if lock.is_file() and lock.read_text().strip() != digest:
        raise SystemExit(f"CAMPAIGN_CHANGED_AFTER_START: {a.campaign} differs from the frozen {lock.read_text()[:16]}")
    lock.write_text(digest)
    log = a.out / "cases.jsonl"
    done = {json.loads(x)["run"] for x in log.read_text().splitlines()} if log.is_file() else set()
    env = dict(os.environ)
    new = 0
    for case in expand(c):
        if case["run"] in done:
            continue
        rec = {**run_case(case, c["model"], env), "campaign_sha256": digest, "at": utc_now()}
        with log.open("a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
        new += 1
        rows = [json.loads(x) for x in log.read_text().splitlines()]
        (a.out / "summary.json").write_text(pretty_json(summary(c, rows, digest)))
        if a.max_cases and new >= a.max_cases:
            break
    rows = [json.loads(x) for x in log.read_text().splitlines()] if log.is_file() else []
    s = summary(c, rows, digest)
    (a.out / "summary.json").write_text(pretty_json(s))
    print(json.dumps({k: s[k] for k in ("cases_planned", "cases_run", "ready", "ready_wilson_95")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
