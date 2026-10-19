"""CRE-T040 — real RCC end-to-end evidence on the local Qwen + real Fabro installation (AT-037).

Assesses real work-order attempts (never mocks): local-only model profile, real Fabro server (local :32290), a terminal
deterministic package whose archive re-verifies, gate-log phases reached, and CRE observations recorded for it. The
outcome is reported as it is (READY or BLOCKED + where); a BLOCKED package with evidence is a valid terminal state,
not a success claim. If no local attempt reached a package, the result is BLOCKED (missing capability), never PASS.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, state_dir, utc_now


def assess(ws: Path) -> dict:
    from ..release.finalize import verify_archive
    from .metrics import attempts
    from .store import CREStore

    fr = ws / ".forge-run"
    prof = json.loads((fr / "model-profile.json").read_text())
    server = json.loads((fr / "fabro_server.json").read_text()) if (fr / "fabro_server.json").is_file() else {}
    pkg = json.loads((fr / "package.json").read_text()) if (fr / "package.json").is_file() else None
    [a] = attempts([ws]) or [None]
    arch = verify_archive(Path(pkg["archive"])) if pkg and Path(pkg.get("archive", "")).is_file() else None
    obs = [o for o in CREStore().observations() if o["attempt_id"] == ws.parent.name]
    terminal = pkg is not None and pkg.get("package_status") in ("READY_FOR_OFFLINE_REVIEW", "READY", "BLOCKED")
    real = bool(prof.get("local_only")) and server.get("url", "").startswith("http://127.0.0.1:32290")
    ok = terminal and real and arch is not None and not arch.get("issues")
    blocked_at = None
    if a and not a["completed"]:
        order = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
        blocked_at = next((p for p in order if p not in a["phases_passed"]), None)
    return {"attempt": ws.parent.name, "fabro_run_id": (fr / "fabro_run_id").read_text().strip()
            if (fr / "fabro_run_id").is_file() else None, "fabro_server": server.get("url"),
            "model_profile": {k: prof.get(k) for k in ("default", "code_nodes", "provider", "local_only")},
            "package_status": pkg and pkg.get("package_status"), "gap_count": pkg and pkg.get("gap_count"),
            "archive_verification": arch, "phases_passed": a and a["phases_passed"], "blocked_at": blocked_at,
            "cre_observations": len(obs),
            "result": "PASS" if ok else "BLOCKED" if not terminal else "NOT_VERIFIABLE" if not server else "FAIL",
            "interpretation": "real end-to-end execution with a terminal deterministic package; the local model "
                              "did not complete the lifecycle" if ok and blocked_at else
                              "real end-to-end execution completed all phases" if ok else "not demonstrated"}


def latest_local_attempts(n: int = 3) -> list[Path]:
    out = []
    for ws in sorted((state_dir() / "workorders").glob("*/workspace"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            prof = json.loads((ws / ".forge-run/model-profile.json").read_text())
        except (OSError, ValueError):
            continue
        if prof.get("local_only") and (ws / ".forge-run/package.json").is_file():
            out.append(ws)
        if len(out) >= n:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    rows = [assess(ws) for ws in latest_local_attempts()]
    rec = {"schema": "forge-c/cre-e2e/1.0", "assessed_at": utc_now(), "attempts": rows,
           "result": "PASS" if rows and rows[0]["result"] == "PASS" else "BLOCKED",
           "note": "a PASS here means real terminal evidence exists; lifecycle success of the local model is reported "
                   "per attempt (blocked_at)"}
    out = REPO_ROOT / "evidence/cre/e2e"
    out.mkdir(parents=True, exist_ok=True)
    (out / "local-qwen-e2e-latest.json").write_text(pretty_json(rec))
    for r in rows:
        print(f"{r['attempt']} {r['result']} package={r['package_status']} blocked_at={r['blocked_at']} "
              f"archive_issues={(r['archive_verification'] or {}).get('issues')} cre_obs={r['cre_observations']}")
    return 0 if rec["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
