"""EASA-T048..T055 — SWE.5/SWE.6 target verification: environment fidelity, raw outcome validation, requirement
observation, integration case categories, fault injection and back-to-back applicability.

Environment classes are HOST, EMULATOR, RENODE, HIL, PHYSICAL. A class is derived from the TOOL that produced the
evidence, never from text: Renode/emulator output can never be labelled HIL or PHYSICAL; HIL/PHYSICAL require a
registered rig record (rig id, probe tool + version, board serial, human operator) and observations bound to it.
Renode results are re-derived from the content-addressed raw log (mailbox words); per-check pass ids are not recorded
by the platform, so requirement observation through TCHECK numbers is INFERRED_FROM_AGGREGATE (a stated limitation).
"""
from __future__ import annotations

import re
from pathlib import Path

from . import contracts, hardware
from .policy import _human

ENV_BY_TOOL = {"run_unit": "HOST", "run_integration": "HOST", "llvm_coverage": "HOST", "run_renode": "RENODE",
               "run_robot": "RENODE", "qemu": "EMULATOR"}
MAGIC = 0xF0C6E5A1


def environment_of(op: str) -> str:
    return ENV_BY_TOOL.get(op, "HOST")


def fidelity_record(env_id: str, kind: str, mcu: str, version: str | None, observations: list[str],
                    limitations: list[str], rig: dict | None = None) -> dict:
    rec = {"environment_id": env_id, "kind": kind, "mcu_target": mcu, "simulation_version": version,
           "observed_peripherals": ["RCC"], "limitations": limitations,
           "physical_hardware_verified": kind in ("HIL", "PHYSICAL") and rig_ok(rig),
           "observations_refs": observations}
    rec["schema_issues"] = contracts.errors("hardware-fidelity", {k: v for k, v in rec.items() if k != "schema_issues"})
    return rec


def rig_ok(rig: dict | None) -> bool:
    return bool(rig) and all(rig.get(k) for k in ("rig_id", "probe_tool", "probe_version", "board_serial")) and \
        _human(rig.get("operator"))


def check_claim(claimed_kind: str, evidence_op: str, rig: dict | None = None) -> list[str]:
    """AT-049/AT-054/AT-055: the claimed environment may not exceed what the producing tool can provide."""
    order = ["HOST", "EMULATOR", "RENODE", "HIL", "PHYSICAL"]
    actual = environment_of(evidence_op)
    out = []
    if order.index(claimed_kind) > order.index(actual):
        if claimed_kind in ("HIL", "PHYSICAL") and not rig_ok(rig):
            out.append(f"FIDELITY_ESCALATION:{claimed_kind} claimed for {actual} evidence ({evidence_op})")
        elif claimed_kind in ("HIL", "PHYSICAL") and actual != claimed_kind:
            out.append(f"FIDELITY_ESCALATION:{claimed_kind} claimed for {actual} evidence ({evidence_op}); rig "
                       "observations must come from the rig")
        elif claimed_kind not in ("HIL", "PHYSICAL"):
            out.append(f"FIDELITY_ESCALATION:{claimed_kind} claimed for {actual} evidence ({evidence_op})")
    return out


def renode_from_raw(raw_text: str) -> list[dict]:
    """Mailbox blocks (magic, passed, failed, done, failed ids...) printed by the run script, in image order."""
    vals = [int(x, 16) for x in re.findall(r"^(0x[0-9A-Fa-f]{8})\s*$", raw_text, re.M)]
    out = []
    for i in range(0, len(vals) - 3, 12):
        blk = vals[i:i + 12]
        if blk[0] != MAGIC:
            continue
        out.append({"passed": blk[1], "failed": blk[2], "done": blk[3] == 1,
                    "failed_ids": [v for v in blk[4:4 + min(blk[2], 8)]]})
    return out


def validate_renode(result: dict, raw_text: str) -> list[str]:
    """AT-052: the reported counts must be re-derivable from the raw log; zero checks or missing done = no evidence."""
    blocks = renode_from_raw(raw_text)
    f = []
    if not blocks:
        return ["RENODE_RAW_HAS_NO_RESULTS"]
    p, fl = sum(b["passed"] for b in blocks), sum(b["failed"] for b in blocks)
    m = result.get("metrics") or {}
    if (m.get("passed"), m.get("failed")) != (p, fl):
        f.append(f"RENODE_COUNTS_NOT_IN_RAW:claimed {m.get('passed')}/{m.get('failed')} raw {p}/{fl}")
    if not all(b["done"] for b in blocks):
        f.append("RENODE_IMAGE_NOT_COMPLETED")
    if result.get("status") == "PASS" and (fl or p == 0):
        f.append("RENODE_PASS_CONTRADICTED_BY_RAW")
    f.append("LIMITATION:PER_CHECK_PASS_IDS_NOT_RECORDED (requirement observation via TCHECK is inferred)")
    return f


VACUOUS = re.compile(r"\bTCHECK\s*\(\s*(\d+)\s*,\s*(1|1U|true|0\s*==\s*0|\(1\))\s*\)")


def vacuous_checks(test_sources: dict[str, str]) -> list[str]:
    """A check whose condition is constant observes nothing (test-output-only passing)."""
    out = []
    for path, t in test_sources.items():
        out += [f"VACUOUS_CHECK:{Path(path).name}:TCHECK {m.group(1)}" for m in VACUOUS.finditer(t)]
    return out


def requirement_observation(requirements: list[str], suite_text: str, scenario_texts: dict[str, str],
                            robot_results: dict[str, dict], renode_failed_ids: set[int]) -> dict:
    """AT-053/AT-081: a requirement is VERIFIED only if its Robot test PASSED AND that test asserts a target check that
    exists in the scenario it ran and did not fail. A test that merely carries the requirement id/tag (or a file name
    match) without an observing assertion leaves the requirement UNVERIFIED."""
    out = {}
    blocks = re.split(r"(?m)^(?=SWR-\d{3}\s*$)", suite_text)
    for r in requirements:
        blk = next((b for b in blocks if b.startswith(r)), "")
        checks = [int(x) for x in re.findall(r"Target Check Should Pass\s+(\d+)", blk)]
        all_checks = "All Target Checks Should Pass" in blk
        scen = re.findall(r"Run Target Scenario\s+(\S+)", blk)
        present = [n for n in checks if any(re.search(rf"TCHECK\s*\(\s*{n}\s*,", scenario_texts.get(s, "")) for s in scen)]
        size = re.search(r"Driver (Flash Size|Static RAM|Stack) Should Be At Most", blk)
        rr = robot_results.get(r, {})
        if not blk:
            st = "UNVERIFIED:no test"
        elif rr.get("status") != "PASS":
            st = f"UNVERIFIED:test {rr.get('status', 'NOT_RUN')}"
        elif size:
            st = "VERIFIED:measured resource assertion"
        elif not checks and not all_checks:
            st = "UNVERIFIED:no observing assertion"
        elif checks and len(present) != len(checks):
            st = "UNVERIFIED:asserted check absent from scenario"
        elif set(present) & renode_failed_ids:
            st = "UNVERIFIED:asserted check failed"
        else:
            st = "VERIFIED:INFERRED_FROM_AGGREGATE" if checks else "VERIFIED:all checks of scenario"
        out[r] = st
    cov = sum(v.startswith("VERIFIED") for v in out.values())
    return {"requirements": out, "verified": cov, "total": len(requirements),
            "basis": "executed Robot assertions on Renode (simulated target), not file names or tags"}


def integration_categories(test_texts: dict[str, str], tool_ops_passed: set[str] | None = None) -> dict:
    """T048: integration evidence must include interface, boundary, negative/timeout and resource cases. Resource
    usage counts only as an executed measurement (measure_elf / stack_usage PASS), never as report text."""
    t = "\n".join(test_texts.values())
    ops = tool_ops_passed or set()
    cats = {"interface": bool(re.search(r"\bIF-\d{2}\b|\b(?:HAL|LL)_RCC_\w+\s*\(", t)),
            "boundary": bool(re.search(r"TIMEOUT_VALUE\s*\+\s*1U?|\(\s*0U?\s*\)|\b1001U?\b|\b1000U?\b", t)),
            "negative_timeout": bool(re.search(r"HAL_TIMEOUT|HAL_ERROR|never_ready|IsReady\(\)\s*==\s*0U", t)),
            "resource": {"measure_elf", "stack_usage"} <= ops}
    return {"categories": cats, "missing": [k for k, v in cats.items() if not v]}


def fault_injection_status(ws: Path, target_tests: list[Path]) -> dict:
    """T049: which fault classes are actually injected and observed; the rest are NOT_SUPPORTED by the model."""
    ws = Path(ws)
    plan = ws / "verification/integration/fault_plan.json"
    out = {"ready_flag_never_set (timeout)": "INJECTED" if any(p.stem.endswith("_timeout") for p in target_tests)
           else "NOT_RUN",
           "planned_register_faults (host model)": "PLANNED" if plan.is_file() else "NOT_RUN",
           "clock_failure / clock security": "NOT_SUPPORTED: behavioural RCC model has no clock tree",
           "interrupt / preemption during read-modify-write": "NOT_SUPPORTED: no interrupt source modelled",
           "brown-out / reset during operation": "NOT_SUPPORTED: no power model"}
    return out


MODEL_FILES = ("*.slx", "*.mdl", "*.fmu", "*.zcos", "*.scade", "*.etp")


def b2b_applicability(ws: Path, work_order_id: str) -> dict:
    """T051/AT-050: back-to-back model/code comparison applies only to model-based development."""
    models = [p for pat in MODEL_FILES for p in Path(ws).rglob(pat)]
    if models:
        return {"work_order_id": work_order_id, "method_id": "EA-B2B", "decision": "APPLICABLE",
                "rationale": f"model artefacts present: {', '.join(p.name for p in models[:3])}",
                "alternative_method_ref": None, "source_version": "enhanced-techniques 1.0.0", "reviewer_ref": None}
    return {"work_order_id": work_order_id, "method_id": "EA-B2B", "decision": "NOT_APPLICABLE_WITH_RATIONALE",
            "rationale": "hand-written C from requirements and the RM; no executable model exists to compare against "
                         "(no " + "/".join(MODEL_FILES) + " in the work order)",
            "alternative_method_ref": None, "source_version": "enhanced-techniques 1.0.0", "reviewer_ref": None}


def limitations(ws: Path, sim_model_text: str) -> list[str]:
    idx = hardware.index(Path(ws) / "inputs/sections/RM0486") if (Path(ws) / "inputs/sections/RM0486").is_dir() else {}
    out = ["Renode behavioural RCC model is not silicon, not HIL; no clock-tree timing, security filtering or "
           "interrupts", "silicon revision UNSPECIFIED"]
    out += hardware.simulator_mismatches(sim_model_text, idx) if idx else ["SIMULATOR_MODEL_NOT_COMPARABLE"]
    er = hardware.errata_status(ws)
    if er["status"] != "BASELINED":
        out.append("errata not baselined: errata-dependent behaviour UNKNOWN")
    return out
