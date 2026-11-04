"""One typed SWE.4 WWDG observation in the existing target peripheral model.

Plain RAM does not implement W0C/RAZ register semantics. This adapter executes
the immutable LL and actual HAL on the existing Renode model, with sealed
mailbox and register-access observations. It grants no phase pass or hardware
verification and leaves all other unit obligations unchanged.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from .. import layer, simulation_performance
from ..common import canonical_json, sha256_file
from ..inspection import swtrace, uspec_plan
from . import unit_target_timing as trusted

DECLARATION = "software/tests/unit/target_observations.json"
SCHEMA = "forge-c/swe4-wwdg-target-observation/1"
PROOF = "forge-c/swe4-target-observation-proof/1"
METRIC = "unit_target_observation_report"
FUNCTION = "HAL_WWDG_ClearEarlyWakeupFlag"
CASE = {"schema": SCHEMA, "ut": "UT-021", "uspec": "USPEC-HAL-04-03", "function": FUNCTION,
        "scenario": "wwdg-ewif-clear-v1"}
BEHAVIOUR = "Preserve other writable fields and reserved bits at reset values when clearing the flag."
SWR = "When writing a WWDG register, the WWDG driver shall preserve its reserved bits at their reset values."


class ObservationError(ValueError):
    pass


def declaration(ws):
    ws = Path(ws)
    if not (ws / DECLARATION).exists():
        return None
    value = trusted._read(ws, DECLARATION)
    if value != CASE or layer.layer_of(ws) != "HAL" or layer.profile(ws)["register_prefix"] != "WWDG":
        raise ObservationError("TARGET_OBSERVATION_SCOPE_OR_CASE_INVALID")
    trusted._approved_inputs(ws)
    manifest = trusted._read(ws, ".forge-run/manifest.json")
    if not manifest.get("provided"):
        raise ObservationError("TARGET_OBSERVATION_PROVIDED_LL_REQUIRED")
    plan = trusted._read(ws, uspec_plan.PLAN)
    if plan.get("unit_specification", {}).get("path") != swtrace.UNITS_MD:
        raise ObservationError("TARGET_OBSERVATION_PLAN_SPEC_PATH_INVALID")
    unit = trusted._safe_path(ws, swtrace.UNITS_MD)
    if sha256_file(unit) != plan["unit_specification"]["sha256"]:
        raise ObservationError("TARGET_OBSERVATION_FROZEN_UNIT_CHANGED")
    rows = [t for t in plan["tasks"] + plan.get("closure", []) if t["ut"] == CASE["ut"]]
    if (len(rows) != 1 or rows[0]["uspec"] != CASE["uspec"] or rows[0]["functions"] != [FUNCTION]
            or rows[0]["behaviour"] != BEHAVIOUR or set(rows[0]["swrs"]) != {"SWR-033", "SWR-034"}
            or swtrace.swr_texts(ws).get("SWR-034") != SWR):
        raise ObservationError("TARGET_OBSERVATION_FROZEN_PREDICATE_UNSUPPORTED")
    calls = trusted._read(ws, "workproducts/SWE.2/api_calls.json").get("calls", {})
    if not any(c.get("function") == FUNCTION and c.get("args") == [] for c in calls.values()):
        raise ObservationError("TARGET_OBSERVATION_FROZEN_CALL_MISSING")
    from ..mcp.servers import sim

    if sim.shadowed_harness(ws):
        raise ObservationError("TARGET_OBSERVATION_FACTORY_HARNESS_SHADOWED")
    return value


def harness():
    """EWIF is reached by the existing model's counter semantics, never by a fake SR write."""
    return '''#include "stm32n6xx_hal_wwdg.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void)
{
    uint32_t before, after;
    hal_status_t status;
    FORGE_TEST_BEGIN();
    FORGE_ACCESS_PHASE(1U);
    WWDG->CR = WWDG_CR_WDGA | 0x40U;
    (void)WWDG->CR; /* existing model reaches EWIF at the 0x40 counter threshold */
    before = WWDG->SR;
    TCHECK(901, before == WWDG_SR_EWIF);
    FORGE_ACCESS_PHASE(2U);
    status = HAL_WWDG_ClearEarlyWakeupFlag();
    FORGE_ACCESS_PHASE(3U);
    after = WWDG->SR;
    TCHECK(902, status == HAL_OK);
    TCHECK(21, after == 0U);
    FORGE_TEST_END();
    return 0;
}
'''


def expected_tests(ws):
    """Validated progress/identity metadata only; declaration alone is never execution evidence."""
    if declaration(ws) is None:
        return []
    return [{"id": CASE["ut"], "uspec": CASE["uspec"], "function": FUNCTION,
             "file": DECLARATION, "status": "DECLARED_NOT_EXECUTED"}]


def _identity(ws):
    from ..mcp.servers import sim

    trusted._approved_inputs(ws)
    files = (DECLARATION, ".forge-run/manifest.json", uspec_plan.PLAN, swtrace.UNITS_MD,
             swtrace.REQS, "workproducts/SWE.2/api_calls.json")
    selected = layer.profile(ws)["sim"]
    renode = sim.renode_bin()
    compiler = shutil.which("arm-none-eabi-gcc")
    return {"files": {rel: sha256_file(trusted._safe_path(ws, rel)) for rel in files},
            "source_files": simulation_performance.source_files(ws), "case": CASE,
            "generated_test_sha256": hashlib.sha256(harness().encode()).hexdigest(),
            "adapter_sha256": sha256_file(Path(__file__)), "trusted_input_adapter_sha256": sha256_file(Path(trusted.__file__)),
            "simulator_adapter_sha256": sha256_file(Path(sim.__file__)),
            "simulation_assets": {k: sha256_file(sim.SIM_DIR / selected[k]) for k in ("platform", "model")},
            "access_observer_sha256": sha256_file(sim.ACCESS_LOG_OBSERVER),
            "target_harness_sha256": sha256_file(sim.SIM_DIR / "forge_target_test.h"),
            "renode_binary_sha256": sha256_file(Path(renode)) if renode else "UNAVAILABLE",
            "compiler_binary_sha256": sha256_file(Path(compiler)) if compiler else "UNAVAILABLE",
            "target_cflags": sim.CFLAGS}


def _shadow(ws, dest):
    ws, dest = Path(ws), Path(dest)
    (dest / ".forge-run").mkdir(parents=True)
    shutil.copyfile(ws / ".forge-run/manifest.json", dest / ".forge-run/manifest.json")
    for name in ("software/hal", "software/ll", "software/src", "software/include", "inputs/vendor/include"):
        if (ws / name).is_dir():
            shutil.copytree(ws / name, dest / name)
    test = dest / "software/tests/target/test_unit_observation.c"
    test.parent.mkdir(parents=True)
    test.write_text(harness())
    if simulation_performance.source_files(ws) != simulation_performance.source_files(dest):
        raise ObservationError("TARGET_OBSERVATION_ISOLATED_SOURCE_MISMATCH")
    return test


def _observed(mailbox, access):
    if (not mailbox["magic_ok"] or not mailbox["done"] or mailbox["passed"] + mailbox["failed"] != 3
            or len(mailbox["failed_ids"]) != mailbox["failed"] or not access):
        raise ObservationError("TARGET_OBSERVATION_INCOMPLETE")
    pre = [a["value"] for a in access if a["phase"] == 1 and a["access"] == "R" and a["offset"] == 8]
    post = [a["value"] for a in access if a["phase"] == 3 and a["access"] == "R" and a["offset"] == 8]
    writes = [a for a in access if a["phase"] == 2 and a["access"] == "W"]
    observed = {"sr_before": pre[-1] if pre else None, "sr_after": post[-1] if post else None,
                "actual_hal_status_matches_HAL_OK": 902 not in mailbox["failed_ids"],
                "call_writes": [{"offset": a["offset"], "value": a["value"]} for a in writes]}
    ok = (mailbox["failed"] == 0 and pre == [1] and post == [0]
          and bool(writes) and all(a["offset"] == 8 for a in writes))
    return {"id": CASE["ut"], "uspec": CASE["uspec"], "function": FUNCTION,
            "status": "PASS" if ok else "FAIL", "observed": observed,
            "scope": "EXPLICIT_EXISTING_RENODE_MODEL_CASE_NOT_SILICON", "silicon_verified": False}


def run(ctx):
    """Same run_unit fragment interface as timing; caller must merge failures and integrity-record this declaration."""
    from ..mcp.sdk import run_argv
    from ..mcp.servers import sim

    ws = Path(ctx.workspace)
    if not (ws / DECLARATION).exists():
        return None
    refs, issues, tests, metrics = [], [], [], {}
    try:
        declaration(ws)
        before = _identity(ws)
        renode = sim.renode_bin()
        if not renode or not shutil.which("arm-none-eabi-gcc"):
            raise ObservationError("TARGET_OBSERVATION_TOOLCHAIN_UNAVAILABLE")
        with tempfile.TemporaryDirectory(prefix="forge-unit-observation-") as td:
            shadow = Path(td) / "workspace"
            test = _shadow(ws, shadow)
            out = shadow / "build/renode"
            out.mkdir(parents=True)
            elf = out / "test_unit_observation.elf"
            built, build_log, errors = sim.build_image(shadow, test, elf)
            if not built:
                refs.append(ctx.store(build_log))
                raise ObservationError("TARGET_OBSERVATION_BUILD_FAILED:" + "|".join(errors))
            listing = run_argv(["arm-none-eabi-objdump", "-d", str(elf)], out, 30, {"arm-none-eabi-objdump"})
            if listing.exit_code or not re.search(r"\bbl\s+[0-9a-fA-F]+ <" + FUNCTION + r">", listing.stdout.decode()):
                raise ObservationError("TARGET_OBSERVATION_DIRECT_HAL_CALL_MISSING")
            listing_ref = ctx.store(listing.stdout)
            refs.append(listing_ref)
            result, raw = sim.run_image(renode, elf, "default", out, shadow)
            raw_ref = ctx.store(raw)
            refs.append(raw_ref)
            if result is None:
                raise ObservationError("TARGET_OBSERVATION_EXECUTION_UNAVAILABLE")
            mailbox = trusted._mailbox(raw)
            if any(mailbox[k] != result[k] for k in mailbox):
                raise ObservationError("TARGET_OBSERVATION_MAILBOX_MISMATCH")
            access_path = sim.access_log_path(elf, out)
            access = sim.read_access_log(access_path)
            access_ref = ctx.store(access_path.read_bytes()) if access is not None else None
            if access_ref is None:
                raise ObservationError("TARGET_OBSERVATION_ACCESS_LOG_MISSING")
            refs.append(access_ref)
            binary = {"schema": "forge-c/elf-evidence/1", "encoding": "base64", "sha256": sha256_file(elf),
                      "data": base64.b64encode(elf.read_bytes()).decode("ascii")}
            binary_ref = ctx.store(canonical_json(binary), "json")
            refs.append(binary_ref)
            tests = [_observed(mailbox, access)]
            if _identity(ws) != before:
                raise ObservationError("TARGET_OBSERVATION_INPUT_CHANGED_DURING_EXECUTION")
            proof = {"schema": PROOF, "identity": before, "invocation_id": ctx.invocation_id,
                     "raw_log_ref": raw_ref, "access_log_ref": access_ref, "elf_artifact_ref": binary_ref,
                     "elf_sha256": binary["sha256"], "disassembly_ref": listing_ref, "mailbox": mailbox, "tests": tests}
            proof_ref = ctx.store(canonical_json(proof), "json")
            refs.append(proof_ref)
            metrics[METRIC] = proof_ref
        if tests[0]["status"] != "PASS":
            issues.append("TARGET_OBSERVATION_PREDICATE_FAILED")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        issues.append(str(exc)[:300])
        metrics = {}
        for test in tests:
            test["status"] = "FAIL"
    return {"status": "FAIL" if issues or not tests else "PASS", "tests": tests, "issues": issues,
            "artifact_refs": refs, "metrics": metrics,
            "raw_log": "".join(f"{t['id']} {t['status']}\n" for t in tests).encode(),
            "environment": "Renode simulated Cortex-M55 with existing WWDG model", "silicon_verified": False}


def verify(ws, result):
    from ..mcp.servers import sim

    ws = Path(ws)
    if declaration(ws) is None:
        raise ObservationError("TARGET_OBSERVATION_DECLARATION_MISSING")
    refs = result.get("artifact_refs", [])
    proof = json.loads(trusted._artifact(ws, refs, result.get("metrics", {}).get(METRIC), "json"))
    if (proof.get("schema") != PROOF or proof.get("identity") != _identity(ws)
            or proof.get("invocation_id") != result.get("provenance", {}).get("invocation_id")):
        raise ObservationError("TARGET_OBSERVATION_PROOF_BINDING_CHANGED")
    binary = json.loads(trusted._artifact(ws, refs, proof["elf_artifact_ref"], "json"))
    if (binary.get("schema") != "forge-c/elf-evidence/1" or binary.get("encoding") != "base64"
            or binary.get("sha256") != proof["elf_sha256"]
            or hashlib.sha256(base64.b64decode(binary["data"], validate=True)).hexdigest() != proof["elf_sha256"]):
        raise ObservationError("TARGET_OBSERVATION_ELF_CHANGED")
    listing = trusted._artifact(ws, refs, proof["disassembly_ref"], "log").decode()
    if not re.search(r"\bbl\s+[0-9a-fA-F]+ <" + FUNCTION + r">", listing):
        raise ObservationError("TARGET_OBSERVATION_DIRECT_HAL_CALL_MISSING")
    mailbox = trusted._mailbox(trusted._artifact(ws, refs, proof["raw_log_ref"], "log"))
    with tempfile.TemporaryDirectory(prefix="forge-unit-observation-verify-") as td:
        path = Path(td) / "access.log"
        path.write_bytes(trusted._artifact(ws, refs, proof["access_log_ref"], "log"))
        observed = _observed(mailbox, sim.read_access_log(path))
    if mailbox != proof["mailbox"] or [observed] != proof["tests"]:
        raise ObservationError("TARGET_OBSERVATION_RESULT_CHANGED")
    return [observed]


def trace(ws):
    """No declaration-only or stale-result acceptance; root wires this into the shared trace adapters."""
    if not (Path(ws) / DECLARATION).exists():
        return [], {}, []
    try:
        declaration(ws)
        records = [r for r in swtrace._tool_records(Path(ws)) if r.get("op") == "run_unit"]
        if not records:
            raise ObservationError("TARGET_OBSERVATION_NO_EXECUTED_UNIT_RUN")
        tests = verify(ws, records[-1]["result"])
        tagged = [{"test": CASE["ut"], "file": DECLARATION, "file_level": False, "verifies": [CASE["uspec"]]}]
        return tagged, {t["id"]: t["status"] for t in tests}, []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [], {}, ["UT:TARGET_OBSERVATION_UNVERIFIED:" + str(exc)[:200]]
