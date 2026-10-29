"""Opt-in incremental delivery policy; existing phase checkpoints and routing remain authoritative."""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

from .common import REPO_ROOT, pretty_json, sha256_file, utc_now

NAME = "incremental-delivery-v1"
HIGH = "incremental-delivery-high-allowance-v2"
DEMO = "qm-pipeline-demonstration-v1"
DECISION = "specs/014-durable-local-autonomy/IMPLEMENTATION-INCREMENTAL-E2E.md"


def binding(name, purpose):
    if name is None:
        return None
    if name not in (NAME, HIGH, DEMO) or purpose not in ("ASPICE_ONLY", "QM") or (name == DEMO and purpose != "QM"):
        raise ValueError("DEVELOPMENT_EXECUTION_POLICY_INVALID")
    result = {"schema": "forge-c/development-execution/1", "name": name, "max_phase_repair_passes": 1,
            "decision": {"path": DECISION, "sha256": sha256_file(REPO_ROOT / DECISION)},
            "validator_sha256": sha256_file(Path(__file__)),
            "product_diagnosis": "DEFERRED_BY_DEVELOPMENT_POLICY",
            "factory_maintenance": "DEFERRED_BY_DEVELOPMENT_POLICY",
            "advisory_relaunch": "DEFERRED_BY_DEVELOPMENT_POLICY"}
    if purpose == "QM":
        result["purpose"] = purpose
    if name == DEMO:
        result.update(demonstration_only=True, quality_gates_block_workflow=False,
                      max_phase_repair_passes=0, max_task_calls=1,
                      max_failed_checks_per_operation=10000, max_tool_calls_per_visit=10000,
                      max_upstream_loops=0)
    if name == HIGH:
        result.update(max_phase_repair_passes=1000, max_task_calls=1001,
                      max_failed_checks_per_operation=10000, max_tool_calls_per_visit=10000,
                      max_upstream_loops=1000)
        from .development_diagnostics import RECIPE

        result["independent_unit_recheck"] = {"recipe": RECIPE, "max_executions": 1,
            "validator_sha256": sha256_file(Path(__file__).with_name("development_diagnostics.py"))}
    return result


def selected(ws):
    path = Path(ws) / ".forge-run/manifest.json"
    m = json.loads(path.read_text()) if path.is_file() else {}
    record = m.get("development_execution")
    if record is None:
        return None
    if record != binding(record.get("name"), m.get("purpose")):
        raise ValueError("DEVELOPMENT_EXECUTION_BINDING_CHANGED")
    return record


@contextmanager
def phase_state(ws, phase):
    if phase not in {f"SWE.{i}" for i in range(1, 7)}:
        raise ValueError("DEVELOPMENT_PHASE_INVALID")
    folder = Path(ws) / ".forge-run/lrtx" / phase
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "development-execution.json"
    if (not folder.resolve().is_relative_to(Path(ws).resolve()) or path.is_symlink()
            or (folder / "development-execution.lock").is_symlink()):
        raise ValueError("DEVELOPMENT_STATE_PATH_UNSAFE")
    with (folder / "development-execution.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.is_file() else {
            "schema": "forge-c/development-phase/1", "calls": {}, "repair_tasks": [], "repair_pass": None}
        yield state
        temp = path.with_suffix(".tmp")
        with temp.open("w") as stream:
            stream.write(pretty_json(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def reserve_call(ws, packet):
    """Count before provider contact. Input changes, re-entry and technical failures do not refill a task."""
    policy = selected(ws)
    if not policy or not packet["role"].endswith("-author"):
        return True
    key = packet["role"] + ":" + packet["task"]
    repair_hint = bool(packet.get("repair_of") or packet.get("findings") or packet["task"].startswith("triage:"))
    with phase_state(ws, packet["phase"]) as state:
        n = state["calls"].get(key, 0)
        if policy["name"] == DEMO:
            if n >= policy["max_task_calls"]:
                return False
            state["calls"][key] = n + 1
            return True
        if policy["name"] == HIGH:
            if n >= policy["max_task_calls"]:
                return False
            if n or repair_hint:
                state["repair_tasks"].append(key)
                if state["repair_pass"] is None:
                    state["repair_pass"] = {"origin": "localized_repair", "at": utc_now()}
            state["calls"][key] = n + 1
            return True
        if n >= (1 if packet["task"].startswith("triage:") else 2):
            return False
        if n or repair_hint:
            if key in state["repair_tasks"]:
                return False
            state["repair_tasks"].append(key)
            if state["repair_pass"] is None:
                state["repair_pass"] = {"origin": "localized_repair", "at": utc_now()}
        state["calls"][key] = n + 1
    return True


def reserve_phase_rework(ws, phase):
    policy = selected(ws)
    if not policy:
        raise ValueError("DEVELOPMENT_POLICY_REQUIRED")
    with phase_state(ws, phase) as state:
        if policy["name"] == DEMO:
            return False
        if policy["name"] == HIGH:
            count = state.get("phase_reworks", 0)
            if count >= policy["max_phase_repair_passes"]:
                return False
            state["phase_reworks"] = count + 1
            state["repair_pass"] = {"origin": "phase_gate", "at": utc_now(), "pass": count + 1}
            return True
        if state["repair_pass"] is not None:
            return False
        state["repair_pass"] = {"origin": "phase_gate", "at": utc_now()}
    return True


def ladder(ws, phase):
    policy = selected(ws)
    with phase_state(ws, phase) as state:
        repair = state["repair_pass"]
        calls = dict(state["calls"])
    # These are admission reservations, not provider execution or engineering-success receipts.
    # A gateway refusal or crash can consume one without any Qwen inference.
    return [{"rung": "initial_engineering", "status": "RESERVED" if calls else "UNKNOWN", "calls": calls},
            {"rung": "bounded_phase_repair", "status": "RESERVED" if repair else "UNAVAILABLE",
             "reason": repair or "No phase repair was requested"},
            *[{"rung": rung, "status": "DEFERRED_BY_DEVELOPMENT_POLICY", "policy": policy["name"] if policy else NAME}
              for rung in ("general_product_diagnosis", "advisory_relaunch", "factory_maintenance")]]

def verification(ws, phase, role, key, status=None):
    """Bound repeated failed native checks; technical failures cannot refill the phase."""
    policy = selected(ws)
    if not phase or not role.endswith("-author") or not policy:
        return True
    with phase_state(ws, phase) as state:
        failed = state.setdefault("failed_checks", {})
        if status is None:
            return failed.get(key, 0) < policy.get("max_failed_checks_per_operation", 2)
        if status != "PASS":
            failed[key] = failed.get(key, 0) + 1
        if state.get("repair_mutation_started"):
            state["verification_after_repair"] = True
    return True


def mutation_allowed(ws, phase, role, relative):
    policy = selected(ws)
    if not phase or not role.endswith("-author") or not policy:
        return True
    # Closing a truthful report remains possible after a failed recheck.
    reports = {"workproducts/SWE.4/unit_verification_report.md",
               "workproducts/SWE.5/integration_verification_report.md",
               "workproducts/SWE.6/software_verification_report.md"}
    if relative in reports:
        return True
    with phase_state(ws, phase) as state:
        if not state.get("failed_checks") and state["repair_pass"] is None:
            return True
        if state.get("verification_after_repair") and policy["name"] not in (HIGH, DEMO):
            return False
        if state["repair_pass"] is None:
            state["repair_pass"] = {"origin": "native_check_failure", "at": utc_now()}
        state["repair_mutation_started"] = True
    return True
