"""EASA-T022 — observe-only assurance gate attached to the existing SWE inspection gate.

Called after the 002 deterministic gate has decided a phase. It maps each requirement of the effective profile to
evidence ACTUALLY recorded in the workspace (MCP tool results whose raw artifact exists and hashes to its address;
deterministic inspection checks) and runs `gate.decide`. The 002 inspector verdict is passed as AI text only. The
result is appended to `.forge-run/assurance/gate-log.jsonl`. It never changes the 002 outcome; any error is
recorded and swallowed (OBSERVE_ONLY, EASA-FR-066).
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from ..common import canonical_json, sha256_bytes, sha256_file, utc_now
from . import catalog, contracts, gate, policy

# requirement -> (MCP ops whose PASS result is tool evidence)
REQ_OPS = {
    "TRACE_REQ_TO_TEST": ["validate_trace"], "SOURCE_LINKED_REQUIREMENTS": ["validate_artifact"],
    "COMPILE_WARNINGS_CLEAN": ["compile"], "STATIC_ANALYSIS": ["cppcheck", "clang_analyze", "clang_tidy"],
    "REQUIREMENTS_DERIVED_TESTS": ["run_unit"], "STATEMENT_COVERAGE": ["llvm_coverage"],
    "BRANCH_COVERAGE": ["llvm_coverage"], "REQUIREMENTS_DERIVED_INTEGRATION_TESTS": ["run_integration", "run_renode"],
    "RESOURCE_USAGE": ["measure_elf", "stack_usage"], "REQUIREMENTS_OBSERVED_TESTS": ["run_robot"],
}


def _tool_results(ws: Path, phase: str) -> list[dict]:
    p = next((c for c in (ws / "evidence" / "tool-results.jsonl", ws / "verification" / "tool-results.jsonl")
              if c.is_file()), None)  # live workspace | sealed package layout
    if p is None:
        return []
    out = []
    for line in p.read_text(errors="replace").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("phase") == phase:
            out.append(r)
    return out


def _accepted(ws: Path, r: dict) -> bool:
    refs = (r.get("result") or {}).get("artifact_refs") or []
    for ref in refs:
        h = ref.rsplit(":", 1)[-1]
        cand = sorted((ws / "evidence" / "raw").glob(f"{h}*")) + sorted((ws / "evidence-raw").glob(f"{h}*"))
        if not cand or sha256_file(cand[0]) != h:
            return False
    return bool(refs)


def evidence_map(ws: Path, phase: str) -> dict[str, list[dict]]:
    res = _tool_results(ws, phase)
    out: dict[str, list[dict]] = {}
    for req, ops in REQ_OPS.items():
        items = []
        for r in res:
            if r.get("op") in ops:
                st = (r.get("result") or {}).get("status")
                items.append({"ref": (r.get("result") or {}).get("provenance", {}).get("invocation_id") or r.get("op"),
                              "kind": "tool", "accepted": _accepted(ws, r),
                              "status": "PASS" if st == "PASS" else ("FAIL" if st == "FAIL" else "UNKNOWN")})
        if items:
            # the gate judges the latest attempt per op: earlier failures were reworked, not hidden (they stay logged)
            last = {}
            for i, r in zip(items, [r for r in res if r.get("op") in ops], strict=True):
                last[r.get("op")] = i
            out[req] = list(last.values())
    insp = ws / "inspection" / phase / "inspection_record.json"
    if insp.is_file():
        out.setdefault("INDEPENDENT_INSPECTION", []).append(
            {"ref": f"inspection:{phase}", "kind": "ai_inspection", "accepted": True,
             "status": "PASS" if json.loads(insp.read_text()).get("verdict") == "PASS" else "FAIL"})
    return out


def phase(ws: Path, phase_id: str, gate002: dict, pol: dict | None = None) -> dict | None:
    ws = Path(ws)
    try:
        pol = pol or contracts.load(policy.POLICY_PATH if policy.POLICY_PATH.is_file() else contracts.POLICY_EXAMPLE)
        reqs = policy.profile_requirements(pol["profile"]).get(phase_id, [])
        bl = sha256_bytes(canonical_json(gate002.get("baseline") or gate002.get("baseline_hash") or gate002))
        d = gate.decide(work_order_id=ws.parent.name, phase=phase_id, mode=pol["mode"], requirements=reqs,
                        evidence=evidence_map(ws, phase_id), inspector_text=str(gate002.get("decision")),
                        profile_hash=policy.policy_sha(pol), catalog_hash=catalog.digest(catalog.load()),
                        baseline_hash=bl)
        d["gate_002_decision"] = gate002.get("decision")
        d["ts_utc"] = utc_now()
    except Exception as exc:  # noqa: BLE001 - observe-only: never break the 002 workflow
        d = {"phase": phase_id, "state": "UNKNOWN", "error": f"{type(exc).__name__}: {exc}"[:300],
             "trace": traceback.format_exc()[-600:], "ts_utc": utc_now()}
    try:
        out = ws / ".forge-run" / "assurance"
        out.mkdir(parents=True, exist_ok=True)
        with (out / "gate-log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(d, sort_keys=True) + "\n")
    except OSError:
        return None
    return d
