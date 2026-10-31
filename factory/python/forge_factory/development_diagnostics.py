"""Bounded downstream unit rechecks from unchanged, previously accepted inputs.

This is diagnostic execution inside the existing Fabro/AFO job, never a phase
acceptance edge. Unknown independence refuses; the original failed gate remains.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from itertools import islice
from pathlib import Path

from .afo.durable import Refused, canonical, digest, immutable_json, strict_json
from .common import sha256_file, utc_now

RECIPE = "unchanged-accepted-unit-recheck-v1"
UNITS = "workproducts/SWE.3/unit_specifications.md"


def rows(path):
    if not path.is_file():
        raise Refused("DIAGNOSTIC_HISTORY_MISSING")
    if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
        raise Refused("DIAGNOSTIC_HISTORY_LIMIT_OR_UNSAFE")
    values = [strict_json(line, 1024 * 1024) for line in path.read_bytes().splitlines() if line.strip()]
    if len(values) > 2048:
        raise Refused("DIAGNOSTIC_HISTORY_LIMIT_OR_UNSAFE")
    return values


def proof(store):
    from .afo.diagnosis_packet import scoped_path
    from .inspection import defects

    ws = store.workspace
    # Existing baseline/inspection readers are bounded before they are used.
    for root in (store.base, store.insp):
        if sum(1 for _ in islice(root.glob("*/*.json"), 2049)) > 2048:
            raise Refused("DIAGNOSTIC_HISTORY_LIMIT_OR_UNSAFE")
    gate_rows = rows(ws / ".forge-run/gates/gate-log.jsonl")
    route = next((r for r in reversed(gate_rows)
                  if r.get("phase") == "SWE.3" and r.get("step") == "route"), {})
    if route.get("gate", {}).get("decision") != "BLOCKED":
        raise Refused("DIAGNOSTIC_ROUTE_NOT_BLOCKED")
    if any(store.gate(p)["decision"] != "PASS" for p in ("SWE.1", "SWE.2")) or defects.gaps(ws):
        raise Refused("DIAGNOSTIC_ORACLE_OR_UPSTREAM_NOT_ACCEPTED")
    bases = {p: store.latest_baseline(p) for p in ("SWE.1", "SWE.2", "SWE.3", "SWE.4")}
    if any(not b for b in bases.values()):
        raise Refused("DIAGNOSTIC_ACCEPTED_ARTIFACT_MISSING")
    current, unit = bases["SWE.3"], bases["SWE.4"]
    failed = store.inspections("SWE.3")[-1]
    accepted = store.inspections("SWE.4")[-1]
    if (failed["verdict"] != "FAIL" or not failed["findings"] or failed.get("stale_reason")
            or failed["baseline_hash"] != current["baseline_hash"]
            or failed["checklist_sha256"] != store.checklist("SWE.3")["sha256"]
            or route["ts"] < failed["recorded_at"] or store.stale_reason("SWE.3", current)):
        raise Refused("DIAGNOSTIC_FAILED_BASELINE_UNBOUND")
    if (accepted["verdict"] != "PASS" or accepted.get("stale_reason")
            or accepted["baseline_hash"] != unit["baseline_hash"]
            or accepted["checklist_sha256"] != store.checklist("SWE.4")["sha256"]
            or store.current_hash("SWE.4") != unit["baseline_hash"]
            or unit["upstream"]["SWE.1"] != bases["SWE.1"]["baseline_hash"]):
        raise Refused("DIAGNOSTIC_UNIT_ARTIFACT_CHANGED_OR_UNACCEPTED")
    previous = next((b for b in store.baselines("SWE.3")
                     if b["baseline_hash"] == unit["upstream"]["SWE.3"]), None)
    old_inspections = [i for i in store.inspections("SWE.3")
                       if previous and i["baseline_hash"] == previous["baseline_hash"]
                       and i["recorded_at"] <= unit["frozen_at"]]
    if (not previous or not old_inspections or old_inspections[-1]["verdict"] != "PASS"
            or old_inspections[-1].get("stale_reason")
            or old_inspections[-1]["checklist_sha256"] != store.checklist("SWE.3")["sha256"]
            or any(previous["upstream"][p] != bases[p]["baseline_hash"] for p in ("SWE.1", "SWE.2"))):
        raise Refused("DIAGNOSTIC_PRIOR_CODE_ACCEPTANCE_MISSING")
    for phase, baseline in [("SWE.1", bases["SWE.1"]), ("SWE.2", bases["SWE.2"]),
                            ("SWE.3", previous), ("SWE.3", current), ("SWE.4", unit)]:
        authored = next((r for r in reversed(gate_rows) if r.get("phase") == phase and r.get("step") == "author"
                         and r.get("baseline_id") == baseline["baseline_id"]), {})
        if authored.get("result") != "FROZEN" or authored.get("finding") or authored.get("errors"):
            raise Refused("DIAGNOSTIC_AUTHOR_CONTRACT_NOT_VALID")
    for b in [*bases.values(), previous]:
        if digest(b["files"]) != b["baseline_hash"]:
            raise Refused("DIAGNOSTIC_BASELINE_HISTORY_CHANGED")
    code = {p: h for p, h in previous["files"].items() if p.startswith(tuple(d + "/" for d in defects.CODE_DIRS))}
    if (not code or code != {p: h for p, h in current["files"].items()
                             if p.startswith(tuple(d + "/" for d in defects.CODE_DIRS))}
            or not previous["files"].get(UNITS)
            or previous["files"][UNITS] != current["files"].get(UNITS)):
        raise Refused("DIAGNOSTIC_CODE_OR_UNIT_ORACLE_CHANGED")
    tests = {p: h for p, h in unit["files"].items() if p.startswith("software/tests/unit/")}
    if (not 1 <= len(tests) <= 4 or any(not Path(p).name.startswith("test_") or not p.endswith(".c") for p in tests)):
        raise Refused("DIAGNOSTIC_UNIT_INPUTS_NOT_ATTESTED")
    runs = [r for r in rows(ws / defects.INTEGRITY_LOG) if r.get("phase") == "SWE.4" and r.get("op") == "run_unit"]
    run = runs[-1] if runs else {}
    if (run.get("status") != "PASS" or run.get("files") != tests or run.get("code_sha") != defects.code_hash(ws)
            or not previous["frozen_at"] <= run["ts_utc"] <= unit["frozen_at"]):
        raise Refused("DIAGNOSTIC_UNIT_RUN_NOT_CURRENT_ACCEPTED_PASS")
    if any(r.get("status") != "PASS" or r.get("files") != tests or r.get("code_sha") != run["code_sha"]
           for r in rows(ws / defects.INTEGRITY_LOG)
           if r.get("op") == "run_unit" and r["ts_utc"] > run["ts_utc"]):
        raise Refused("DIAGNOSTIC_LATER_UNIT_EVIDENCE_CONTRADICTS_ACCEPTANCE")
    manifest = strict_json((ws / ".forge-run/manifest.json").read_bytes(), 1024 * 1024)
    inputs = {i["path"]: i["sha256"] for i in manifest["inputs"]}
    inputs.update({i["path"]: i["sha256"] for i in manifest.get("delivered", [])})
    bound = {**inputs, **bases["SWE.1"]["files"], **bases["SWE.2"]["files"],
             **current["files"], **unit["files"]}
    if any(sha256_file(scoped_path(ws, p)) != h for p, h in bound.items()):
        raise Refused("DIAGNOSTIC_BOUND_INPUT_CHANGED")
    return {"recipe": RECIPE, "failed_baseline": current["baseline_hash"],
            "failed_inspection": {"id": failed["inspection_id"], "sha256": digest(failed),
                                  "unresolved_findings": failed["findings"]},
            "accepted_unit_inspection": digest(accepted), "accepted_code_inspection": digest(old_inspections[-1]),
            "unit_integrity_sha256": digest(run), "inputs": bound, "code_sha256": run["code_sha"],
            "manifest_sha256": sha256_file(ws / ".forge-run/manifest.json"),
            "scope": "Rerun unchanged accepted tests/code; failed SWE.3 findings are not an input to this executable check",
            "acceptance_effect": "NONE"}



def append_gap(ws, record):
    from .afo.diagnosis_packet import scoped_path

    path = scoped_path(ws, ".forge-run/advisory/SWE.3.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(canonical(record).decode() + "\n")
        stream.flush()
        os.fsync(stream.fileno())



def prior_result(ws, reservation):
    """Recover a stored observation, never execute again or infer input continuity across a crash."""
    path = ws / reservation["intent_ref"]
    intent = strict_json(path.read_bytes(), 4 * 1024 * 1024)
    if digest(intent) != reservation["intent_sha256"]:
        raise Refused("DIAGNOSTIC_INTENT_CHANGED")
    result_path = path.with_name(path.stem + "-result.json")
    if result_path.is_file():
        result = strict_json(result_path.read_bytes(), 4 * 1024 * 1024)
        if result.get("intent_sha256") != reservation["intent_sha256"]:
            raise Refused("DIAGNOSTIC_RECEIPT_CHANGED")
        return {"status": "ALREADY_RESERVED", **reservation, "completion_status": result["status"]}
    journal = ws / "evidence/tool-results.jsonl"
    found = ([r for r in rows(journal)
              if r["result"].get("provenance", {}).get("invocation_id") == intent["tool_event_id"]]
             if journal.is_file() else [])
    matches = [r for r in found if (r["server"], r["op"], r["role"], r["phase"]) ==
               ("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4")
               and r.get("mission_tool_charge") == intent["mission_tool_charge"]]
    if len(found) == len(matches) == 1:
        result = {"schema": "forge-c/development-diagnostic/1", "phase": "SWE.3", "at": utc_now(),
                  "status": "TOOL_RESULT_RECOVERED_INPUT_CONTINUITY_UNPROVEN",
                  "intent_ref": reservation["intent_ref"], "intent_sha256": reservation["intent_sha256"],
                  "unresolved_findings": intent["unresolved_findings"], "acceptance_effect": "NONE",
                  "tool_result": matches[0]["result"], "independent_inputs_unchanged": None}
        immutable_json(result_path, result)
        append_gap(ws, result)
        return {"status": "ALREADY_RESERVED", **reservation, "completion_status": result["status"]}
    return {"status": "ALREADY_RESERVED", **reservation, "completion_status": "UNKNOWN_NO_UNIQUE_TOOL_RECEIPT"}


def recheck(store):
    from . import development_execution as D
    from .afo.execution_lifecycle import Executions
    from .afo.mission_ledger import MissionLedger
    from .afo.operations import Intent, configured
    from .afo.queue import Store as Queue
    from .lrtx import tools

    ws = store.workspace
    policy = D.selected(ws)
    if not policy or policy.get("independent_unit_recheck", {}).get("recipe") != RECIPE:
        return {"status": "NOT_ELIGIBLE", "reason": "DIAGNOSTIC_RECIPE_NOT_SELECTED"}
    with D.phase_state(ws, "SWE.3") as state:
        if state.get("independent_unit_recheck"):
            return prior_result(ws, state["independent_unit_recheck"])
        try:
            operator = Intent().read() if configured() else None
            if operator and operator["mode"] != "RUNNING":
                raise Refused("DIAGNOSTIC_OPERATOR_INTENT_NOT_RUNNING")
            job = strict_json((ws / ".forge-run/durable-binding.json").read_bytes(), 1024 * 1024)
            queue = Queue()
            live = Executions(queue).get(job["job_id"])
            if (not live or live["task_outcome"] != "ACTIVE" or live["resource_lease"] != "HELD"
                    or live["execution_liveness"] != "LIVE" or live["identity_state"] != "CONFIRMED"):
                raise Refused("DIAGNOSTIC_ACTIVE_EXECUTION_REQUIRED")
            if live["mission_id"] != job["mission_id"]:
                raise Refused("DIAGNOSTIC_MISSION_BINDING_CHANGED")
            deadline = MissionLedger(queue).snapshot(job["mission_id"])["limits"]["deadline"]
            if time.time() >= deadline:
                raise Refused("DIAGNOSTIC_MISSION_TIME_EXHAUSTED")
            evidence = proof(store)
            images = sum(p.startswith("software/tests/unit/") for p in evidence["inputs"])
            if time.time() + images * 240 + 40 > deadline:
                raise Refused("DIAGNOSTIC_VERIFICATION_WINDOW_TOO_SMALL")
        except (OSError, ValueError, KeyError, IndexError) as exc:
            return {"status": "NOT_ELIGIBLE", "reason": getattr(exc, "code", "DIAGNOSTIC_INPUT_UNPROVEN")}
        ref = ".forge-run/lrtx/SWE.3/independent-unit-recheck.json"
        event_id = "unit-recheck-" + digest([job["mission_id"], job["job_id"], evidence])
        intent = {"schema": "forge-c/development-diagnostic/1", "phase": "SWE.3", "at": utc_now(),
                  "status": "RESERVED_UNKNOWN_COMPLETION", "proof": evidence, "acceptance_effect": "NONE",
                  "tool_event_id": event_id, "operator_epoch": operator["epoch"] if operator else None,
                  "mission_tool_charge": {"mission_id": job["mission_id"], "job_id": job["job_id"], "event_id": event_id},
                  "unresolved_findings": evidence["failed_inspection"]["unresolved_findings"]}
        immutable_json(ws / ref, intent)
        state["independent_unit_recheck"] = {"intent_ref": ref, "intent_sha256": digest(intent)}
    append_gap(ws, intent)
    # Reservation and immutable intent precede all executable work. A crash cannot refill it.
    if operator and Intent().read() != operator:
        result = {"schema": "forge-c/development-diagnostic/1", "phase": "SWE.3", "at": utc_now(),
                  "status": "OPERATOR_INTENT_CHANGED_BEFORE_RECHECK", "intent_ref": ref,
                  "intent_sha256": digest(intent), "acceptance_effect": "NONE", "handler_executed": False,
                  "unresolved_findings": intent["unresolved_findings"]}
        immutable_json(ws / ref.replace(".json", "-result.json"), result)
        append_gap(ws, result)
        return result
    observed = tools.call(ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", "SWE.4", invocation_id=event_id)
    from .afo.diagnosis_packet import scoped_path

    try:
        unchanged = all(sha256_file(scoped_path(ws, p)) == h for p, h in evidence["inputs"].items())
    except (OSError, ValueError):
        unchanged = False
    result = {"schema": "forge-c/development-diagnostic/1", "phase": "SWE.3", "at": utc_now(),
              "status": "PROVISIONAL_RECHECK_RECORDED" if unchanged else "INPUT_CHANGED_DURING_RECHECK",
              "intent_ref": ref, "intent_sha256": digest(intent), "acceptance_effect": "NONE",
              "unresolved_findings": intent["unresolved_findings"], "tool_result": observed,
              "independent_inputs_unchanged": unchanged}
    immutable_json(ws / ref.replace(".json", "-result.json"), result)
    append_gap(ws, result)
    return result


def main():
    from .inspection.engine import Store

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(recheck(Store(args.workspace.resolve()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
