"""Explicit SWE.4 WWDG call measurements in the existing Renode observer.

The declaration relocates no obligation by itself. Only a current, sealed and
recomputed measurement can supply a passing UT. This measures the declared
calls in the pinned instruction/time model, never hardware WCET.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from .. import layer
from .. import simulation_performance as performance
from ..common import canonical_json, sha256_file
from ..inspection import uspec_plan

DECLARATION = "software/tests/unit/target_wwdg_timing.json"
SCHEMA = "forge-c/swe4-wwdg-target-timing/1"
PROOF = "forge-c/swe4-wwdg-target-timing-proof/1"
METRIC = "unit_target_wwdg_timing_report"
FUNCTIONS = ("HAL_WWDG_Init", "HAL_WWDG_Refresh", "HAL_WWDG_GetEarlyWakeupFlag", "HAL_WWDG_ClearEarlyWakeupFlag")
CONFIG_KEYS = ("prescaler", "window", "counter", "ewi_enable")
SCENARIO = "wwdg-declared-per-call-v1"
PRIVATE_CHECKS = {function: 1001 + n for n, function in enumerate(FUNCTIONS)}


class TimingError(ValueError):
    pass


def _read(ws, rel):
    path = _safe_path(ws, rel)
    return json.loads(path.read_text())


def _safe_path(ws, rel):
    if not isinstance(rel, str) or not rel or "\\" in rel or PurePosixPath(rel).is_absolute() or ".." in PurePosixPath(rel).parts:
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
    from .unit_target_timing import _approved_inputs as approved

    return approved(ws)


def _timing_specs(ws):
    from ..inspection import swtrace

    if not (Path(ws) / swtrace.UNITS_MD).is_file():
        return set()
    units = swtrace.parse_units(_safe_path(ws, swtrace.UNITS_MD).read_text())
    return {
        item["id"]
        for unit in units
        if any(fn.startswith("HAL_WWDG_") for fn in unit["functions"])
        for item in unit["specs"]
        if set(item["swrs"]) & {"SWR-027", "SWR-028"} or re.search(r"\b(instructions|virtual time)\b", item["text"])
    }


def _candidates(ws):
    if not (Path(ws) / uspec_plan.PLAN).is_file():
        return []
    plan = _read(ws, uspec_plan.PLAN)
    if not isinstance(plan, dict) or any(not isinstance(plan.get(k, []), list) for k in ("tasks", "closure")):
        raise TimingError("WWDG_TARGET_TIMING_PLAN_INVALID")
    specs = _timing_specs(ws)
    return [
        row
        for row in plan.get("tasks", []) + plan.get("closure", [])
        if isinstance(row, dict)
        and (
            row.get("uspec") in specs
            or set(row.get("swrs", [])) & {"SWR-027", "SWR-028"}
            or re.search(r"\b(instructions|virtual time)\b", row.get("behaviour", ""))
        )
    ]


def selected(ws):
    """Selection is fail-closed for frozen timing semantics, not an author-controlled opt-in."""
    if (Path(ws) / DECLARATION).exists():
        return True
    manifest = _read(ws, ".forge-run/manifest.json") if (Path(ws) / ".forge-run/manifest.json").is_file() else {}
    if manifest.get("layer") != "HAL" or manifest.get("peripheral") != "wwdg":
        return False
    try:
        return bool(_timing_specs(ws) or _candidates(ws))
    except (OSError, ValueError, KeyError, TypeError):
        return True  # run/trace report the precise malformed contract; never fall back to a host PASS.


def required_rows(ws):
    """Exact frozen semantic contract; broad candidate discovery never grants credit."""
    from ..inspection import swtrace

    ws = Path(ws)
    rows = _candidates(ws)
    if not rows:
        if _timing_specs(ws):
            raise TimingError("WWDG_TARGET_TIMING_FUNCTION_COVERAGE_INCOMPLETE")
        return []
    _approved_inputs(ws)
    budget = performance.selected(ws)
    if layer.layer_of(ws) != "HAL" or layer.profile(ws)["register_prefix"] != "WWDG" or not budget:
        raise TimingError("WWDG_TARGET_TIMING_SCOPE_OR_BUDGET_UNSUPPORTED")
    plan = _read(ws, uspec_plan.PLAN)
    if plan.get("unit_specification", {}).get("path") != swtrace.UNITS_MD:
        raise TimingError("WWDG_TARGET_TIMING_PLAN_SPEC_PATH_INVALID")
    unit = _safe_path(ws, swtrace.UNITS_MD)
    if sha256_file(unit) != plan["unit_specification"]["sha256"]:
        raise TimingError("WWDG_TARGET_TIMING_FROZEN_UNIT_CHANGED")
    _safe_path(ws, swtrace.REQS)
    texts = swtrace.swr_texts(ws)
    prefix = (
        f"When a scoped HAL_WWDG_ API is measured in the declared instrumented target scenario at "
        f"{budget['performance_mips']} MIPS, the WWDG driver shall "
    )
    if (
        texts.get("SWR-027") != prefix + f"execute at most {budget['instructions_per_call']} target instructions per call."
        or texts.get("SWR-028")
        != prefix + f"complete each call in at most {budget['microseconds_per_call']} microseconds of virtual time."
    ):
        raise TimingError("WWDG_TARGET_TIMING_FROZEN_REQUIREMENT_UNSUPPORTED")
    behaviour = (
        f"In the declared instrumented target scenario at {budget['performance_mips']} MIPS, complete within "
        f"{budget['instructions_per_call']} instructions and {budget['microseconds_per_call']} microseconds of virtual time."
    )
    specs = [(u, item) for u in swtrace.parse_units(unit.read_text()) for item in u["specs"]]
    if len(rows) != 4 or {tuple(r.get("functions", [])) for r in rows} != {(f,) for f in FUNCTIONS}:
        raise TimingError("WWDG_TARGET_TIMING_FUNCTION_COVERAGE_INCOMPLETE")
    if len({r.get("ut") for r in rows}) != 4 or len({r.get("uspec") for r in rows}) != 4:
        raise TimingError("WWDG_TARGET_TIMING_AMBIGUOUS_PLAN_ROW")
    all_rows = plan.get("tasks", []) + plan.get("closure", [])
    for row in rows:
        bound = [(u, item) for u, item in specs if item["id"] == row.get("uspec")]
        if (
            not re.fullmatch(r"UT-(?!000)\d{3}", str(row.get("ut")))
            or len(bound) != 1
            or len([r for r in all_rows if r.get("ut") == row["ut"] or r.get("uspec") == row["uspec"]]) != 1
            or row.get("behaviour") != behaviour
            or row.get("constraints_verified_at_swe6", [])
            or row.get("kind", "requirement") != "requirement"
            or row.get("test_kind", "positive") != "positive"
            or row.get("unknown_swrs", [])
            or sorted(row.get("swrs", [])) != ["SWR-027", "SWR-028"]
            or bound[0][0]["id"] != row.get("unit")
            or bound[0][0]["functions"] != row["functions"]
            or bound[0][1]["text"] != behaviour
            or bound[0][1]["swrs"] != ["SWR-027", "SWR-028"]
        ):
            raise TimingError("WWDG_TARGET_TIMING_FROZEN_PREDICATE_UNSUPPORTED")
    from ..mcp.servers import sim

    if sim.shadowed_harness(ws):
        raise TimingError("WWDG_TARGET_TIMING_FACTORY_HARNESS_SHADOWED")
    return rows


def _literal(text):
    match = re.fullmatch(r"\s*(0[xX][0-9a-fA-F]+|\d+)[uU]?\s*", text)
    if not match:
        raise TimingError("WWDG_TARGET_TIMING_ARGUMENT_NOT_LITERAL")
    return int(match[1], 16 if match[1].lower().startswith("0x") else 10)


def declaration(ws):
    ws = Path(ws)
    rows = required_rows(ws)
    if not (ws / DECLARATION).exists():
        if rows:
            raise TimingError("WWDG_TARGET_TIMING_DECLARATION_REQUIRED")
        return None
    value = _read(ws, DECLARATION)
    if (
        not rows
        or not isinstance(value, dict)
        or set(value) != {"schema", "scenario", "config", "refresh_counter", "query_initial", "cases"}
        or value.get("schema") != SCHEMA
        or value.get("scenario") != SCENARIO
    ):
        raise TimingError("WWDG_TARGET_TIMING_DECLARATION_INVALID")
    config = value["config"]
    if (
        not isinstance(config, dict)
        or set(config) != set(CONFIG_KEYS)
        or any(type(config[k]) is not int for k in CONFIG_KEYS)
        or not 0 <= config["prescaler"] <= 7
        or not 0x40 <= config["window"] <= 0x7F
        or not 0x40 <= config["counter"] <= 0x7F
        or config["ewi_enable"] not in (0, 1)
        or type(value["refresh_counter"]) is not int
        or not 0x40 <= value["refresh_counter"] <= 0x7F
        or type(value["query_initial"]) is not int
        or not 0 <= value["query_initial"] <= 0xFFFFFFFF
    ):
        raise TimingError("WWDG_TARGET_TIMING_ARGUMENT_INVALID")
    calls = _read(ws, "workproducts/SWE.2/api_calls.json").get("calls", {}).values()
    configs, counters, queries, clear = [], [], [], False
    for call in calls:
        fn, args = call.get("function"), call.get("args")
        if fn == FUNCTIONS[0] and isinstance(args, list) and len(args) == 1:
            match = re.fullmatch(r"&\s*\(\s*const\s+hal_wwdg_config_t\s*\)\s*\{([^{}]*)\}", args[0])
            if match:
                fields = {}
                for part in match[1].split(","):
                    field = re.fullmatch(r"\s*\.(\w+)\s*=\s*(0[xX][0-9a-fA-F]+|\d+)[uU]?\s*", part)
                    if not field or field[1] in fields:
                        fields = {}
                        break
                    fields[field[1]] = _literal(field[2])
                configs.append(fields)
        elif (
            fn == FUNCTIONS[1]
            and isinstance(args, list)
            and len(args) == 1
            and re.fullmatch(r"\s*(0[xX][0-9a-fA-F]+|\d+)[uU]?\s*", args[0])
        ):
            counters.append(_literal(args[0]))
        elif fn == FUNCTIONS[2] and isinstance(args, list) and len(args) == 1:
            match = re.fullmatch(r"&\s*\(\s*uint32_t\s*\)\s*\{\s*(0[xX][0-9a-fA-F]+|\d+)[uU]?\s*\}", args[0])
            if match:
                queries.append(_literal(match[1]))
        elif fn == FUNCTIONS[3] and args == []:
            clear = True
    if config not in configs or value["refresh_counter"] not in counters or value["query_initial"] not in queries or not clear:
        raise TimingError("WWDG_TARGET_TIMING_ARGUMENT_NOT_FROZEN")
    cases = value["cases"]
    if not isinstance(cases, list) or len(cases) != 4:
        raise TimingError("WWDG_TARGET_TIMING_CASES_INCOMPLETE")
    by = {r["ut"]: r for r in rows}
    if len({c.get("ut") for c in cases if isinstance(c, dict)}) != 4:
        raise TimingError("WWDG_TARGET_TIMING_CASE_INVALID")
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case) != {"ut", "uspec", "function", "expected_status"}
            or case.get("ut") not in by
            or case.get("expected_status") != "HAL_OK"
            or case["uspec"] != by[case["ut"]]["uspec"]
            or by[case["ut"]]["functions"] != [case["function"]]
        ):
            raise TimingError("WWDG_TARGET_TIMING_CASE_INVALID")
    return value


def expected_tests(ws):
    rows = required_rows(ws)
    return [
        {
            "id": row["ut"],
            "uspec": row["uspec"],
            "function": row["functions"][0],
            "file": DECLARATION,
            "status": "DECLARED_NOT_EXECUTED",
        }
        for row in rows
    ]


def harness(value):
    """Four direct frozen calls; private mailbox tags do not alias public UT IDs."""
    config = ", ".join(f".{k} = {value['config'][k]}U" for k in CONFIG_KEYS)
    return f"""#include "forge_performance_calls.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void)
{{
    const hal_wwdg_config_t config = {{ {config} }};
    uint32_t flag = {value["query_initial"]}U;
    FORGE_TEST_BEGIN();
    TCHECK(1001, HAL_WWDG_Init(&config) == HAL_OK);
    TCHECK(1002, HAL_WWDG_Refresh({value["refresh_counter"]}U) == HAL_OK);
    TCHECK(1003, HAL_WWDG_GetEarlyWakeupFlag(&flag) == HAL_OK);
    TCHECK(1004, HAL_WWDG_ClearEarlyWakeupFlag() == HAL_OK);
    FORGE_TEST_END();
    return 0;
}}
"""


def _identity(ws, value):
    from ..mcp.servers import sim

    effective = _approved_inputs(ws)
    assets = layer.profile(ws)["sim"]
    return {
        "declaration_sha256": sha256_file(Path(ws) / DECLARATION),
        "plan_sha256": sha256_file(Path(ws) / uspec_plan.PLAN),
        "requirements_sha256": sha256_file(_safe_path(ws, "workproducts/SWE.1/software_requirements.md")),
        "required_rows": required_rows(ws),
        "generated_test_sha256": hashlib.sha256(harness(value).encode()).hexdigest(),
        "performance_observer_sha256": sha256_file(Path(performance.__file__)),
        "trusted_input_adapter_sha256": sha256_file(Path(__file__).with_name("unit_target_timing.py")),
        "target_harness_sha256": sha256_file(sim.SIM_DIR / "forge_target_test.h"),
        "access_observer_sha256": sha256_file(sim.ACCESS_LOG_OBSERVER),
        "compiler_binary_sha256": sha256_file(Path(shutil.which("arm-none-eabi-gcc")))
        if shutil.which("arm-none-eabi-gcc")
        else "UNAVAILABLE",
        "renode_binary_sha256": sha256_file(Path(sim.renode_bin())) if sim.renode_bin() else "UNAVAILABLE",
        "target_cflags": sim.CFLAGS,
        "unit_specification_sha256": sha256_file(Path(ws) / "workproducts/SWE.3/unit_specifications.md"),
        "call_contract_sha256": sha256_file(Path(ws) / "workproducts/SWE.2/api_calls.json"),
        "manifest_sha256": sha256_file(Path(ws) / ".forge-run/manifest.json"),
        "source_files": performance.source_files(ws),
        "arguments": value,
        "provided_effective_identity": effective,
        "adapter_sha256": sha256_file(Path(__file__)),
        "simulation_adapter_sha256": sha256_file(Path(sim.__file__)),
        "simulation_assets": {k: sha256_file(sim.SIM_DIR / assets[k]) for k in ("model", "platform")},
    }


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
    if (
        observation.get("magic_ok") is not True
        or observation.get("done") is not True
        or observation.get("passed", 0) + observation.get("failed", 0) != 4
        or len(observation.get("failed_ids", [])) != observation.get("failed", 0)
        or not set(observation.get("failed_ids", [])).issubset(set(PRIVATE_CHECKS.values()))
        or set(measured.get("samples", {})) != set(FUNCTIONS)
    ):
        raise TimingError("WWDG_TARGET_TIMING_STATUS_OBSERVATION_INCOMPLETE")
    return [
        {
            "id": case["ut"],
            "uspec": case["uspec"],
            "function": case["function"],
            "expected_status": "HAL_OK",
            "observed_status_matches": PRIVATE_CHECKS[case["function"]] not in observation["failed_ids"],
            "status": "PASS"
            if measured["status"] == "PASS"
            and len(measured["samples"][case["function"]]) == 1
            and PRIVATE_CHECKS[case["function"]] not in observation["failed_ids"]
            else "FAIL",
            "samples": measured["samples"][case["function"]],
        }
        for case in value["cases"]
    ]


def _mailbox(raw):
    """Read the same RAM mailbox transcript as the existing simulator adapter."""
    from ..mcp.servers.sim import MAGIC

    values = [int(x, 16) for x in re.findall(r"^(0x[0-9A-Fa-f]{8})\s*$", raw.decode(), re.M)]
    if len(values) < 4:
        raise TimingError("TARGET_TIMING_MAILBOX_MISSING")
    return {
        "magic_ok": values[0] == MAGIC,
        "passed": values[1],
        "failed": values[2],
        "done": values[3] == 1,
        "failed_ids": values[4 : 4 + min(values[2], 8)],
    }


def run(ctx):
    """run_unit hook: None for legacy; otherwise scalar metrics + sealed artifacts + actual UT log.

    Caller merges issues/status and appends raw_log to its normal output. It
    must not print success based on declarations or omit failed timing rows.
    """
    from ..mcp.servers import sim

    ws = Path(ctx.workspace)
    if not selected(ws):
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
            binary = {
                "schema": "forge-c/elf-evidence/1",
                "encoding": "base64",
                "sha256": sha256_file(elf),
                "data": base64.b64encode(elf.read_bytes()).decode("ascii"),
            }
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
                (raw_dir / (reference.split(":")[-1] + "." + kind)).write_bytes(_artifact(ws, refs, reference, kind))
            measured = performance.verify_result(shadow, engine_result)
            tests = _outcomes(value, measured, observation)
            if _identity(ws, value) != before:
                raise TimingError("TARGET_TIMING_INPUT_CHANGED_DURING_EXECUTION")
            proof = {
                "schema": PROOF,
                "identity": before,
                "invocation_id": ctx.invocation_id,
                "engine_result": engine_result,
                "observation": mailbox,
                "tests": tests,
                "scope": "EXPLICIT_SIMULATED_CALLS_ONLY_NOT_WCET",
                "silicon_verified": False,
            }
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
    return {
        "status": "FAIL" if issues or not tests else "PASS",
        "tests": tests,
        "issues": issues,
        "artifact_refs": refs,
        "metrics": metrics,
        "raw_log": log,
        "environment": "Renode simulated Cortex-M55",
        "silicon_verified": False,
    }


def verify(ws, result):
    """Repeat all source/argument/ELF/raw-log checks; no status assertion is trusted."""
    ws = Path(ws)
    value = declaration(ws)
    if value is None:
        raise TimingError("TARGET_TIMING_DECLARATION_MISSING")
    reference = result.get("metrics", {}).get(METRIC)
    refs = result.get("artifact_refs", [])
    proof = json.loads(_artifact(ws, refs, reference, "json"))
    if proof.get("schema") != PROOF:
        raise TimingError("TARGET_TIMING_PROOF_VERSION_UNSUPPORTED")
    if proof.get("identity") != _identity(ws, value) or proof.get("invocation_id") != result.get("provenance", {}).get(
        "invocation_id"
    ):
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
    """No host assertion may credit a recognized target timing predicate."""
    from ..inspection.swtrace import _tool_records

    ws = Path(ws)
    if not selected(ws):
        return [], {}, []
    try:
        candidates = _candidates(ws)
        specs = _timing_specs(ws)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [], {}, ["UT:WWDG_TARGET_TIMING_NOT_VERIFIED:" + str(exc)[:220]]
    tests = [
        {"test": row["ut"], "file": DECLARATION, "verifies": [row["uspec"]]}
        for row in candidates
        if isinstance(row.get("ut"), str) and isinstance(row.get("uspec"), str)
    ]
    # Even a removed/misbound plan row cannot turn a frozen target-only USPEC
    # into host evidence. Existing IDs are read from the host tags, never invented.
    from ..inspection.swtrace import tagged_tests

    host = tagged_tests(sorted(ws.glob("software/tests/unit/test_*.c")) + sorted(ws.glob("software/tests/unit/test_*.cpp")), ws)
    for row in host:
        refs = sorted(set(row["verifies"]) & specs)
        if refs and row["test"] not in {t["test"] for t in tests}:
            tests.append({"test": row["test"], "file": DECLARATION, "verifies": refs})
    failed = {t["test"]: "FAIL" for t in tests}
    try:
        declaration(ws)
        records = [r for r in _tool_records(ws) if r.get("op") == "run_unit"]
        if not records:
            raise TimingError("WWDG_TARGET_TIMING_NO_EXECUTED_UNIT_RUN")
        measured = verify(ws, records[-1]["result"])
        statuses = {**failed, **{r["id"]: r["status"] for r in measured}}
        return tests, statuses, ["UT:WWDG_TARGET_TIMING_FAILED:" + key for key, value in statuses.items() if value != "PASS"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return tests, failed, ["UT:WWDG_TARGET_TIMING_NOT_VERIFIED:" + str(exc)[:220]]
