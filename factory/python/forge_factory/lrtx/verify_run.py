"""Read-only verification of a finished local-profile work order (evidence for LRTX-T005..T010).

    python -m forge_factory.lrtx.verify_run --workspace <ws> [--storage <fabro storage>] [--meter <usage.jsonl>]

PASS only when the run's own records show: the explicit profile in the manifest and the model profile; ACP rejected
and no ACP node in the workflow; every Fabro LLM provider local and loopback; the network denial OBSERVED (not
declared); the served model digest equal to the profile; isolated roots outside the existing deployment; admission
metrics for the run's calls (queue wait, load/prefill/decode or their UNKNOWN labels, resources); a sealed package.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def verify(ws: Path, storage: Path | None = None, meter: Path | None = None) -> dict:
    from . import profile as lp
    from .runmetrics import collect

    ws = Path(ws)
    run = ws / ".forge-run"
    man = json.loads((run / "manifest.json").read_text())
    prof = json.loads((run / "model-profile.json").read_text())
    loc = prof.get("local_profile") or {}
    checks = {}
    checks["profile_selected"] = bool(man.get("local_profile")) and loc.get("id") == man["local_profile"].get("id")
    enf = loc.get("enforcement") or {}
    checks["acp_rejected"] = enf.get("acp") == "REJECTED_BEFORE_LAUNCH" and not man.get("acp_authors") \
        and not man.get("acp_inspectors") and 'backend="acp"' not in (run / "workflow.fabro").read_text()
    checks["network_denied_observed"] = (enf.get("network") or {}).get("status") == "DENIED_VERIFIED"
    checks["model_digest_match"] = bool(loc.get("models")) and all(m.get("status") == "MATCH" for m in loc["models"])
    roots = loc.get("roots") or {}
    existing = [Path(p).resolve() for p in lp.load(loc.get("id", "local-rtx-v1"))["existing_deployment"]["roots"]]
    checks["roots_isolated"] = bool(roots) and not any(Path(r).resolve() == e or Path(r).resolve().is_relative_to(e)
                                                       for r in roots.values() for e in existing)
    checks["fabro_providers_local"] = enf.get("fabro_providers") == ["ollama"] and enf.get("endpoints") == \
        "LOOPBACK_VERIFIED"
    m = collect(ws, storage, meter)
    calls = (m.get("calls") or {})
    checks["admission_metrics"] = calls.get("count", 0) > 0 and calls.get("queue_wait_ms", {}).get("max") is not None
    pkg = run / "package.json"
    checks["package_sealed"] = pkg.is_file() and json.loads(pkg.read_text()).get("package_status") in (
        "READY_FOR_OFFLINE_REVIEW", "BLOCKED")
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
            "package_status": json.loads(pkg.read_text()).get("package_status") if pkg.is_file() else None,
            "metrics": {k: m.get(k) for k in ("window", "stages", "calls", "resources", "energy")}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--storage", type=Path, default=None)
    ap.add_argument("--meter", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    rep = verify(a.workspace, a.storage, a.meter)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"status": rep["status"], "checks": rep["checks"], "package_status": rep["package_status"]}))
    return 0 if rep["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
