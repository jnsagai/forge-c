"""Explicit SWE.4 CRC call measurements in the existing Renode observer.

The declaration relocates no obligation by itself. Only a current, sealed and
recomputed measurement can supply a passing UT. This measures the declared
calls in the pinned instruction/time model, never hardware WCET.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from .. import layer
from .. import simulation_performance as performance
from ..common import canonical_json, sha256_file
from ..inspection import uspec_plan

DECLARATION = "software/tests/unit/target_timing.json"
SCHEMA = "forge-c/swe4-crc-target-timing/1"
PROOF = "forge-c/swe4-target-timing-proof/1"
METRIC = "unit_target_timing_report"
CONFIG_KEYS = ("polynomial", "polynomial_size", "init_value", "input_reverse", "output_reverse")
FUNCTIONS = ("HAL_CRC_Init", "HAL_CRC_Calculate", "HAL_CRC_Accumulate")


class TimingError(ValueError):
    pass


def _read(ws, rel):
    path = _safe_path(ws, rel)
    return json.loads(path.read_text())


def _safe_path(ws, rel):
    if (not isinstance(rel, str) or not rel or "\\" in rel or PurePosixPath(rel).is_absolute()
            or ".." in PurePosixPath(rel).parts):
        raise TimingError("TARGET_TIMING_PATH_INVALID")
    root = Path(ws).resolve()
    path = root
    for part in PurePosixPath(rel).parts:
        path = path / part
        if path.is_symlink():
            raise TimingError("TARGET_TIMING_INPUT_SYMLINK:" + rel)
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise TimingError("TARGET_TIMING_INPUT_MISSING_OR_OUTSIDE:" + rel)
    return path


def _approved_inputs(ws):
    """Current bytes alone cannot replace the manifest's approved dependency identity."""
    manifest = _read(ws, ".forge-run/manifest.json")
    provided = manifest.get("provided") or []
    build = manifest.get("provided_build") or {}
    if (not isinstance(provided, list) or not isinstance(build, dict)
            or not isinstance(build.get("files", []), list)):
        raise TimingError("TARGET_TIMING_PROVIDED_INPUTS_INVALID")
    if any(not isinstance(item, dict) or item.get("role") != "provided_ll_driver"
           or item.get("path") != layer.ll_header(Path(ws)) for item in provided):
        raise TimingError("TARGET_TIMING_PROVIDED_LL_BINDING_INVALID")
    if build and (build.get("style") != "cmsis" or not build.get("files") or not provided
                  or any(not isinstance(item, dict) or not str(item.get("path", "")).startswith("inputs/vendor/include/")
                         for item in build["files"])):
        raise TimingError("TARGET_TIMING_VENDOR_BINDING_INVALID")
    items = provided + (build.get("files") or [])
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256")))
                or item.get("path") in seen):
            raise TimingError("TARGET_TIMING_PROVIDED_BINDING_INVALID")
        seen.add(item.get("path"))
        path = _safe_path(ws, item.get("path"))
        if sha256_file(path) != item["sha256"]:
            raise TimingError("TARGET_TIMING_APPROVED_INPUT_CHANGED:" + item["path"])
    # Every compiler source/header, including ancestor directories, remains in
    # the original workspace. A copied symlink target is never a new approval.
    for rel in performance.source_files(ws):
        _safe_path(ws, rel)


def declaration(ws):
    """Validate exact frozen plan rows and typed arguments, without running anything."""
    ws = Path(ws)
    if not (ws / DECLARATION).exists():
        return None
    value = _read(ws, DECLARATION)
    _approved_inputs(ws)
    budget = performance.selected(ws)
    if (not isinstance(value, dict) or set(value) != {"schema", "config", "cases"}
            or value.get("schema") != SCHEMA or layer.layer_of(ws) != "HAL"
            or layer.profile(ws)["register_prefix"] != "CRC" or not budget):
        raise TimingError("TARGET_TIMING_SCOPE_UNSUPPORTED")
    config = value["config"]
    if (not isinstance(config, dict) or set(config) != set(CONFIG_KEYS)
            or any(type(config[k]) is not int or not 0 <= config[k] <= 0xffffffff for k in CONFIG_KEYS)
            or not config["polynomial"] & 1 or config["polynomial_size"] not in range(4)):
        raise TimingError("TARGET_TIMING_CONFIG_INVALID")
    contract = _read(ws, "workproducts/SWE.2/api_calls.json")
    configurations = []
    for call in (contract.get("calls") or {}).values():
        if call.get("function") != "HAL_CRC_Init" or len(call.get("args", [])) != 1:
            continue
        text = call["args"][0]
        outer = re.fullmatch(r"&\s*\(\s*const\s+hal_crc_config_t\s*\)\s*\{([^{}]*)\}", text)
        if outer is None:
            continue
        fields = {}
        for field in outer[1].split(","):
            item = re.fullmatch(r"\s*\.(\w+)\s*=\s*(0[xX][0-9a-fA-F]+|\d+)[uU]?\s*", field)
            if item is None or item[1] in fields:
                fields = {}
                break
            fields[item[1]] = int(item[2], 16 if item[2].lower().startswith("0x") else 10)
        configurations.append(fields)
    if config not in configurations:
        raise TimingError("TARGET_TIMING_CONFIG_NOT_FROZEN_CALL_ARGUMENTS")
    plan = _read(ws, uspec_plan.PLAN)
    if plan["unit_specification"]["path"] != "workproducts/SWE.3/unit_specifications.md":
        raise TimingError("TARGET_TIMING_PLAN_SPEC_PATH_INVALID")
    unit = _safe_path(ws, plan["unit_specification"]["path"])
    if (unit.is_symlink() or not unit.is_file()
            or sha256_file(unit) != plan["unit_specification"]["sha256"]):
        raise TimingError("TARGET_TIMING_FROZEN_PLAN_CHANGED")
    tasks = {t["ut"]: t for t in plan["tasks"] + plan.get("closure", [])}
    cases = value["cases"]
    if not isinstance(cases, list) or len(cases) != 3:
        raise TimingError("TARGET_TIMING_CASES_INCOMPLETE")
    seen = set()
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {"ut", "uspec", "function", "word_count", "expected_status"}
                or not re.fullmatch(r"UT-\d{3}", str(case.get("ut")))
                or case.get("ut") not in tasks or case["ut"] in seen or case.get("function") not in FUNCTIONS
                or case["expected_status"] != "HAL_OK"):
            raise TimingError("TARGET_TIMING_CASE_INVALID")
        seen.add(case["ut"])
        task = tasks[case["ut"]]
        n = 0 if case["function"] == "HAL_CRC_Init" else 64
        if (case["uspec"] != task["uspec"] or task["functions"] != [case["function"]]
                or type(case["word_count"]) is not int or case["word_count"] != n):
            raise TimingError("TARGET_TIMING_ARGUMENT_OR_UNIT_MISMATCH")
        text = " ".join(task["behaviour"].split())
        prefix = "For the specified valid configuration" if n == 0 else "For a 64-word buffer"
        expected = (f"{prefix} in the instrumented target simulation at {budget['performance_mips']} MIPS, "
                    f"execute at most {budget['instructions_per_call']} instructions and use at most "
                    f"{budget['microseconds_per_call']} microseconds per call.")
        if text != expected:
            raise TimingError("TARGET_TIMING_FROZEN_PREDICATE_UNSUPPORTED")
    if {c["function"] for c in cases} != set(FUNCTIONS):
        raise TimingError("TARGET_TIMING_FUNCTION_COVERAGE_INCOMPLETE")
    return value


def harness(value):
    """Finite generated argument material, no arbitrary author-supplied C expressions."""
    by = {c["function"]: c for c in value["cases"]}
    cfg = ", ".join(f".{k} = {value['config'][k]}U" for k in CONFIG_KEYS)
    lines = ['#include "forge_performance_calls.h"', '#include "forge_target_test.h"',
             "FORGE_MAILBOX_DEFINE;", "int main(void)", "{", "    FORGE_TEST_BEGIN();",
             f"    const hal_crc_config_t config = {{ {cfg} }};",
             "    uint32_t words[64];", "    uint32_t result = 0U;",
             "    for (uint32_t i = 0U; i < 64U; i++) { words[i] = i; }"]
    for function in FUNCTIONS:
        case = by[function]
        args = "&config" if function == "HAL_CRC_Init" else "words, 64U, &result"
        # The status is read from the actual function return. No timing TCHECK
        # or constant status assertion is accepted from the declaration.
        lines += [f"    /* {case['ut']} {case['uspec']}; words={case['word_count']} */",
                  f"    TCHECK({int(case['ut'].split('-')[1])}, {function}({args}) == HAL_OK);"]
    return "\n".join(lines + ["    FORGE_TEST_END();", "    return 0;", "}", ""])


def _identity(ws, value):
    from ..mcp.servers import sim

    _approved_inputs(ws)
    assets = layer.profile(ws)["sim"]
    return {"declaration_sha256": sha256_file(Path(ws) / DECLARATION),
            "plan_sha256": sha256_file(Path(ws) / uspec_plan.PLAN),
            "unit_specification_sha256": sha256_file(Path(ws) / "workproducts/SWE.3/unit_specifications.md"),
            "call_contract_sha256": sha256_file(Path(ws) / "workproducts/SWE.2/api_calls.json"),
            "manifest_sha256": sha256_file(Path(ws) / ".forge-run/manifest.json"),
            "source_files": performance.source_files(ws), "arguments": value,
            "adapter_sha256": sha256_file(Path(__file__)),
            "simulation_adapter_sha256": sha256_file(Path(sim.__file__)),
            "simulation_assets": {k: sha256_file(sim.SIM_DIR / assets[k]) for k in ("model", "platform")}}


def _shadow(ws, dest, value):
    """Isolate the generated target harness; never edit frozen workspace inputs."""
    ws, dest = Path(ws), Path(dest)
    (dest / ".forge-run").mkdir(parents=True)
    shutil.copyfile(ws / ".forge-run/manifest.json", dest / ".forge-run/manifest.json")
    for name in ("software/hal", "software/ll", "software/src", "software/include", "inputs/vendor/include"):
        if (ws / name).is_dir():
            shutil.copytree(ws / name, dest / name)
    test = dest / performance.TEST
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(harness(value))
    if performance.source_files(dest) != performance.source_files(ws):
        raise TimingError("TARGET_TIMING_ISOLATED_SOURCE_MISMATCH")
    return test


def _artifact(ws, refs, reference, kind):
    if reference not in refs or not re.fullmatch(r"artifact:sha256:[a-f0-9]{64}", str(reference)):
        raise TimingError("TARGET_TIMING_ARTIFACT_UNBOUND")
    path = _safe_path(ws, "evidence/raw/" + reference.split(":")[-1] + "." + kind)
    if sha256_file(path) != reference.split(":")[-1]:
        raise TimingError("TARGET_TIMING_ARTIFACT_CHANGED")
    return path.read_bytes()


def _outcomes(value, measured, observation):
    if (observation.get("magic_ok") is not True or observation.get("done") is not True
            or observation.get("passed", 0) + observation.get("failed", 0) != 3):
        raise TimingError("TARGET_TIMING_STATUS_OBSERVATION_INCOMPLETE")
    failed = observation.get("failed_ids", [])
    tests = []
    for case in value["cases"]:
        samples = measured["samples"].get(case["function"], [])
        ok = (measured["status"] == "PASS" and len(samples) == 1
              and int(case["ut"].split("-")[1]) not in failed)
        tests.append({"id": case["ut"], "uspec": case["uspec"], "function": case["function"],
                      "word_count": case["word_count"], "config": value["config"],
                      "expected_status": case["expected_status"],
                      "observed_status_matches": int(case["ut"].split("-")[1]) not in failed,
                      "status": "PASS" if ok else "FAIL", "samples": samples})
    return tests


def _mailbox(raw):
    """Read the same RAM mailbox transcript as the existing simulator adapter."""
    from ..mcp.servers.sim import MAGIC

    values = [int(x, 16) for x in re.findall(r"^(0x[0-9A-Fa-f]{8})\s*$", raw.decode(), re.M)]
    if len(values) < 4:
        raise TimingError("TARGET_TIMING_MAILBOX_MISSING")
    return {"magic_ok": values[0] == MAGIC, "passed": values[1], "failed": values[2], "done": values[3] == 1,
            "failed_ids": values[4:4 + min(values[2], 8)]}


def run(ctx):
    """run_unit hook: None for legacy; otherwise scalar metrics + sealed artifacts + actual UT log.

    Caller merges issues/status and appends raw_log to its normal output. It
    must not print success based on declarations or omit failed timing rows.
    """
    from ..mcp.servers import sim

    ws = Path(ctx.workspace)
    if not (ws / DECLARATION).exists():
        return None
    refs, issues, tests = [], [], []
    try:
        value = declaration(ws)
        before = _identity(ws, value)
        renode = sim.renode_bin()
        if not renode or not shutil.which("arm-none-eabi-gcc"):
            raise TimingError("TARGET_TIMING_TOOLCHAIN_UNAVAILABLE")
        with tempfile.TemporaryDirectory(prefix="forge-unit-timing-") as td:
            shadow = Path(td) / "workspace"
            test = _shadow(ws, shadow, value)
            out = shadow / "build/renode"
            out.mkdir(parents=True)
            elf = out / "test_performance.elf"
            built, build_log, errors = sim.build_image(shadow, test, elf)
            if not built:
                refs.append(ctx.store(build_log))
                raise TimingError("TARGET_TIMING_BUILD_FAILED:" + "|".join(errors))
            observation, raw = sim.run_image(renode, elf, "default", out, shadow)
            if not observation or not observation.get("performance"):
                refs.append(ctx.store(raw))
                raise TimingError("TARGET_TIMING_MEASUREMENT_UNAVAILABLE")
            mailbox = _mailbox(raw)
            if any(mailbox[k] != observation[k] for k in mailbox):
                raise TimingError("TARGET_TIMING_MAILBOX_OBSERVATION_MISMATCH")
            raw_ref = ctx.store(raw)
            binary = {"schema": "forge-c/elf-evidence/1", "encoding": "base64", "sha256": sha256_file(elf),
                      "data": base64.b64encode(elf.read_bytes()).decode("ascii")}
            binary_ref = ctx.store(canonical_json(binary), "json")
            engine = {**observation["performance"], "raw_log_ref": raw_ref, "elf_artifact_ref": binary_ref}
            engine_ref = ctx.store(canonical_json(engine), "json")
            refs += [raw_ref, binary_ref, engine_ref]
            engine_result = {"artifact_refs": list(refs), "metrics": {"simulation_performance_report": engine_ref}}
            # Recompute through the existing engine against the isolated exact
            # inputs. Its raw artifacts remain in the normal evidence store.
            raw_dir = shadow / "evidence/raw"
            raw_dir.mkdir(parents=True)
            for reference, kind in ((raw_ref, "log"), (binary_ref, "json"), (engine_ref, "json")):
                (raw_dir / (reference.split(":")[-1] + "." + kind)).write_bytes(
                    _artifact(ws, refs, reference, kind))
            measured = performance.verify_result(shadow, engine_result)
            tests = _outcomes(value, measured, observation)
            if _identity(ws, value) != before:
                raise TimingError("TARGET_TIMING_INPUT_CHANGED_DURING_EXECUTION")
            proof = {"schema": PROOF, "identity": before, "invocation_id": ctx.invocation_id,
                     "engine_result": engine_result, "observation": mailbox,
                     "tests": tests, "scope": "EXPLICIT_SIMULATED_CALLS_ONLY_NOT_WCET", "silicon_verified": False}
            proof_ref = ctx.store(canonical_json(proof), "json")
            refs.append(proof_ref)
        if any(t["status"] != "PASS" for t in tests):
            issues.append("TARGET_TIMING_CALL_OR_BUDGET_FAILED")
        metrics = {METRIC: proof_ref}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        issues.append(str(exc)[:300])
        metrics = {}
        for test in tests:
            test["status"] = "FAIL"
    log = "".join(f"{t['id']} {t['status']}\n" for t in tests).encode()
    return {"status": "FAIL" if issues or not tests else "PASS", "tests": tests, "issues": issues,
            "artifact_refs": refs, "metrics": metrics, "raw_log": log,
            "environment": "Renode simulated Cortex-M55", "silicon_verified": False}


def verify(ws, result):
    """Repeat all source/argument/ELF/raw-log checks; no status assertion is trusted."""
    ws = Path(ws)
    value = declaration(ws)
    if value is None:
        raise TimingError("TARGET_TIMING_DECLARATION_MISSING")
    reference = result.get("metrics", {}).get(METRIC)
    refs = result.get("artifact_refs", [])
    proof = json.loads(_artifact(ws, refs, reference, "json"))
    if (proof.get("schema") != PROOF or proof.get("identity") != _identity(ws, value)
            or proof.get("invocation_id") != result.get("provenance", {}).get("invocation_id")):
        raise TimingError("TARGET_TIMING_PROOF_BINDING_CHANGED")
    with tempfile.TemporaryDirectory(prefix="forge-unit-timing-verify-") as td:
        shadow = Path(td) / "workspace"
        _shadow(ws, shadow, value)
        raw_dir = shadow / "evidence/raw"
        raw_dir.mkdir(parents=True)
        engine = json.loads(_artifact(ws, refs, proof["engine_result"]["metrics"]["simulation_performance_report"], "json"))
        for ref in proof["engine_result"]["artifact_refs"]:
            kind = "log" if ref == engine["raw_log_ref"] else "json"
            raw = _artifact(ws, refs, ref, kind)
            (raw_dir / (ref.split(":")[-1] + "." + kind)).write_bytes(raw)
        measured = performance.verify_result(shadow, proof["engine_result"])
        mailbox = _mailbox(_artifact(ws, refs, engine["raw_log_ref"], "log"))
        if mailbox != proof["observation"]:
            raise TimingError("TARGET_TIMING_STATUS_OBSERVATION_CHANGED")
        tests = _outcomes(value, measured, mailbox)
    if tests != proof["tests"]:
        raise TimingError("TARGET_TIMING_OUTCOME_CHANGED")
    return tests


def trace(ws):
    """Matrix/planned-unit adapter; only the latest recorded run_unit can verify a relocated UT."""
    from ..inspection.swtrace import _tool_records

    if not (Path(ws) / DECLARATION).exists():
        return [], {}, []
    try:
        value = declaration(ws)
        tagged = [{"test": c["ut"], "file": DECLARATION, "file_level": False, "verifies": [c["uspec"]]}
                  for c in value["cases"]]
        records = [r for r in _tool_records(Path(ws)) if r.get("op") == "run_unit"]
        if not records:
            raise TimingError("TARGET_TIMING_NO_EXECUTED_UNIT_RUN")
        tested = verify(ws, records[-1]["result"])
        return tagged, {t["id"]: t["status"] for t in tested}, []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [], {}, ["UT:TARGET_TIMING_UNVERIFIED:" + str(exc)[:200]]
