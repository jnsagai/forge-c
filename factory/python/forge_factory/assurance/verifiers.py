"""EASA-T066/T068 — the independent deterministic verifier: one executable check per ENHANCED requirement, run by
the observe-only hook (never by an agent). Each run writes a report under .forge-run/assurance/reports/<phase>/ with
its sha256; that report is the evidence the assurance gate accepts. A requirement without an executable verifier
returns NOT_SUPPORTED (it is never satisfied by default); AI inspection text is never a verifier.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..common import pretty_json, sha256_bytes, utc_now
from ..inspection import swtrace
from ..layer import layer_of
from . import coverage, hardware, oracle_gen, swe3, swe12
from . import target as T


def _code(ws: Path) -> dict[str, str]:
    return {str(p): p.read_text(errors="replace") for p in swtrace.code_files(ws)}


def _hdr(ws: Path) -> str:
    p = ws / "software/ll/stm32n6xx_ll_rcc.h"
    return p.read_text(errors="replace") if p.is_file() else ""


def _idx(ws: Path) -> dict:
    d = ws / "inputs/sections/RM0486"
    return hardware.index(d) if d.is_dir() else {}


def _ok(findings: list[str]) -> str:
    return "FAIL" if [f for f in findings if not f.startswith(("LIMITATION", "NOT_APPLICABLE"))] else "PASS"


def v_requirements(ws: Path) -> dict:
    r = swe12.check_requirements(ws)
    return {"status": r["verdict"], "findings": r["major_findings"]}


def v_two_way(ws: Path) -> dict:
    r = swe12.trace_round_trip(ws)
    return {"status": r["verdict"], "findings": r["major_findings"]}


def v_arch(ws: Path) -> dict:
    """SWC/allocation/interface-id rules (owner addendum) apply only to work orders prepared with the trace profile."""
    from ..layer import swtrace_enabled

    if swtrace_enabled(ws):
        a = swtrace.check_architecture_model(ws) if (ws / swtrace.ARCH).is_file() else {"major_findings": ["ARCH:MISSING"]}
        notes = []
    else:
        a, notes = {"major_findings": []}, ["NOT_APPLICABLE:owner trace profile (SWC/allocation) predates this work order"]
    b = swe12.check_architecture(ws)
    f = a["major_findings"] + b["major_findings"]
    return {"status": _ok(f), "findings": f + notes}


def v_register_semantics(ws: Path) -> dict:
    idx = _idx(ws)
    if not idx:
        return {"status": "NOT_SUPPORTED", "findings": ["RM sections not in the work-order inputs"]}
    f = hardware.check_defines(_hdr(ws), idx)
    for text in _code(ws).values():
        f += [x for x in hardware.check_writes(text, _hdr(ws), idx) if not x.startswith("NON_ATOMIC_RMW")]
    return {"status": _ok(f), "findings": f}


def v_misra(ws: Path) -> dict:
    from ..mcp.servers.analysis import MISRA_RULES

    inv = swe3.misra_inventory(MISRA_RULES)
    dev = ws / "workproducts/SWE.3/misra_deviations.json"
    devs = json.loads(dev.read_text()) if dev.is_file() else []
    f = swe3.deviation_findings(_code(ws), devs)
    return {"status": "PASS" if inv["status"] == "MEASURED" and not f else ("NOT_SUPPORTED" if inv["status"] != "MEASURED"
                                                                          else "FAIL"),
            "findings": f, "inventory": {k: v for k, v in inv.items() if k != "unsupported"}}


def v_concurrency(ws: Path) -> dict:
    md = (ws / swe12.ARCH_MD).read_text(errors="replace") if (ws / swe12.ARCH_MD).is_file() else ""
    stated = bool(re.search(r"(shared[- ]resource|interrupt|IRQ|concurren|reentran|critical section)", md, re.I))
    f = swe3.invariant_findings(_code(ws), _hdr(ws), _idx(ws), stated)
    return {"status": _ok(f), "findings": f, "mitigation_stated": stated}


def v_oracle(ws: Path) -> dict:
    layer = layer_of(ws)
    hdr = "stm32n6xx_ll_rcc.h" if layer == "LL" else "stm32n6xx_hal_rcc.h"
    srcs = [] if layer == "LL" else sorted((ws / "software/hal").glob("*.c"))
    r = oracle_gen.run(ws, [ws / "software/hal", ws / "software/ll"], srcs, hdr)
    f = [f"ORACLE_FAIL:{x[1]}:{x[2]}" for x in r.get("results", []) if x[3] == "FAIL"]
    if r["status"] in ("PASS", "FAIL") and r["provenance"]["independence_status"] != "INDEPENDENT":
        f.append("ORACLE_NOT_INDEPENDENT:" + str(r["provenance"]["contamination_reason"]))
    limits = [f"LIMITATION:{n}" for n in r.get("notes", [])]  # not derivable from requirements: stated, not a failure
    st = r["status"] if r["status"] in ("PASS", "FAIL") else "NOT_SUPPORTED"
    return {"status": "FAIL" if f else st, "findings": f + limits, "cases": r.get("cases", 0)}


def _unit_test(ws: Path) -> Path | None:
    p = ws / "software/tests/unit/test_rcc.c"
    return p if p.is_file() else None


def v_mutation(ws: Path) -> dict:
    from . import mutation

    ut = _unit_test(ws)
    if ut is None:
        return {"status": "NOT_RUN", "findings": ["no unit test"]}
    layer = layer_of(ws)
    target = "ll/stm32n6xx_ll_rcc.h" if layer == "LL" else "hal/stm32n6xx_hal_rcc.c"
    used = set(re.findall(r"\b((?:LL|HAL)_RCC_\w+)\s*\(", "\n".join(_code(ws).values()) + ut.read_text()))
    c = mutation.run_campaign(ws / "software", target, [ut], used_symbols=used,
                              extra_sources=[] if layer == "LL" else [])
    surv = [f"SURVIVOR:{m['op']}@{m['line']}:{m['original'][:50]}" for m in c["mutants"] if m["outcome"] == "SURVIVED"]
    r = c["record"]
    return {"status": "FAIL" if surv else "PASS", "findings": surv,
            "campaign": {k: r[k] for k in ("campaign_id", "eligible", "killed", "survived", "equivalent", "invalid")}}


def v_api_execution(ws: Path) -> dict:
    """The unit test must execute every function of the code under test (static inline LL functions included)."""
    ut = _unit_test(ws)
    if ut is None:
        return {"status": "NOT_RUN", "findings": ["no unit test"]}
    if layer_of(ws) == "LL":
        tu = ws / "software/src/stm32n6xx_ll_rcc.c"
        srcs = [tu] if tu.is_file() else []
    else:
        srcs = sorted((ws / "software/hal").glob("*.c"))
    if not srcs:
        return {"status": "NOT_RUN", "findings": ["no compile unit for the code under test"]}
    r = coverage.measure(srcs, ut, [ws / "software/hal", ws / "software/ll", ws / "software/include"])
    if r["status"] != "MEASURED":
        return {"status": "NOT_SUPPORTED", "findings": [str(r.get("reason", ""))[:160]]}
    counts: dict[str, int] = {}
    for name, n in r["function_counts"].items():  # static (inline) functions are exported as "<file>:<name>"
        key = name.split(":")[-1]
        counts[key] = max(counts.get(key, 0), n)
    defined = sorted(set(re.findall(r"^[\w\s\*]*?\b((?:HAL|LL)_RCC_\w+)\s*\([^;{)]*\)\s*\{",
                                    "\n".join(_code(ws).values()), re.M)))
    f = coverage.api_execution(counts, defined, ut.read_text())
    return {"status": _ok(f), "findings": f,
            "coverage": [{k: x[k] for k in ("kind", "status", "covered", "total")} for x in r["records"]]}


def v_renode_raw(ws: Path) -> dict:
    rr = swtrace.latest_run(ws, "run_renode")
    if rr is None or not rr["raw"]:
        return {"status": "NOT_RUN", "findings": ["no recorded run_renode"]}
    recs = swtrace._tool_records(ws)
    res = [x for x in recs if x.get("op") == "run_renode"][-1]["result"]
    f = T.validate_renode(res, rr["raw"][0].read_text(errors="replace"))
    f += T.vacuous_checks({str(p): p.read_text(errors="replace") for p in ws.glob("software/tests/**/*.c")})
    return {"status": _ok(f), "findings": f}


def v_integration(ws: Path) -> dict:
    ops = {r.get("op") for r in swtrace._tool_records(ws) if (r.get("result") or {}).get("status") == "PASS"}
    tt = {str(p): p.read_text(errors="replace") for d in ("target", "integration")
          for p in (ws / "software/tests" / d).glob("*.c")}
    c = T.integration_categories(tt, ops)
    return {"status": "FAIL" if c["missing"] else "PASS",
            "findings": [f"INTEGRATION_CATEGORY_MISSING:{m}" for m in c["missing"]]}


def v_fault_injection(ws: Path) -> dict:
    st = T.fault_injection_status(ws, list((ws / "software/tests/target").glob("*.c")))
    injected = [k for k, v in st.items() if v == "INJECTED"]
    return {"status": "PASS" if injected else "NOT_RUN", "findings": [f"{k}: {v}" for k, v in st.items() if v != "INJECTED"],
            "classes": st}


def v_observation(ws: Path) -> dict:
    rr = swtrace.latest_run(ws, "run_robot")
    suite = next(iter(sorted((ws / "software/tests/software").glob("*.robot"))), None)
    if rr is None or suite is None:
        return {"status": "NOT_RUN", "findings": ["no recorded run_robot or suite"]}
    reqs = swtrace.requirement_ids(ws)
    sc = {p.name: p.read_text(errors="replace") for p in (ws / "software/tests/software").glob("*.c")}
    renode = swtrace.latest_run(ws, "run_renode")
    failed = {i for b in (T.renode_from_raw(renode["raw"][0].read_text()) if renode and renode["raw"] else [])
              for i in b["failed_ids"]}
    o = T.requirement_observation(reqs, suite.read_text(), sc, swtrace.robot_results(rr["raw"]), failed)
    f = [f"UNVERIFIED:{k}:{v}" for k, v in o["requirements"].items() if not v.startswith("VERIFIED")]
    return {"status": _ok(f), "findings": f, "verified": o["verified"], "total": o["total"]}


def v_not_supported(why: str):
    return lambda ws: {"status": "NOT_SUPPORTED", "findings": [why]}


VERIFIERS = {
    "SOURCE_LINKED_REQUIREMENTS": v_requirements, "SOURCE_CONTRADICTION_CHECK": v_requirements,
    "TESTABILITY_CHECK": v_requirements, "TWO_WAY_TRACE": v_two_way, "TRACE_REQ_TO_TEST": v_two_way,
    "COMPONENT_ALLOCATION": v_arch, "INTERFACE_DEFINITION": v_arch, "IRQ_RESOURCE_OWNERSHIP": v_arch,
    "PLANTUML_SEMANTIC_CONSISTENCY": v_arch,
    "FLOW_SCHEDULING_ANALYSIS": v_not_supported("no control/data-flow or scheduling analyzer installed"),
    "REGISTER_MAP_CONFORMANCE": v_register_semantics, "REGISTER_ACCESS_SEMANTICS": v_register_semantics,
    "MISRA_RULE_COVERAGE_MATRIX": v_misra, "CONCURRENCY_ANALYSIS": v_concurrency,
    "INDEPENDENT_ORACLE": v_oracle, "MUTATION_EVIDENCE": v_mutation, "API_EXECUTION_PROOF": v_api_execution,
    "RAW_OUTCOME_VALIDATION": v_renode_raw, "BOUNDARY_INTEGRATION": v_integration, "FAULT_INJECTION": v_fault_injection,
    "MEASURED_REQUIREMENT_OBSERVATION": v_observation,
    "DEGRADED_TRANSITION_SCENARIOS": v_observation,
}


def run_for_phase(ws: Path, phase: str, requirements: list[str]) -> dict[str, list[dict]]:
    """Run each verifier once per phase (shared results), write hash-recorded reports, return gate evidence items."""
    ws = Path(ws)
    out: dict[str, list[dict]] = {}
    cache: dict = {}
    d = ws / ".forge-run/assurance/reports" / phase
    d.mkdir(parents=True, exist_ok=True)
    for req in requirements:
        fn = VERIFIERS.get(req)
        if fn is None:
            continue
        if fn not in cache:
            t0 = time.monotonic()
            try:
                res = fn(ws)
            except Exception as exc:  # noqa: BLE001 - a crashing verifier is evidence of nothing, not a pass
                res = {"status": "ERROR", "findings": [f"{type(exc).__name__}: {exc}"[:200]]}
            res = {**res, "duration_s": round(time.monotonic() - t0, 2), "at": utc_now(), "verifier": fn.__name__}
            body = pretty_json(res).encode()
            h = sha256_bytes(body)
            (d / f"{fn.__name__}-{h[:12]}.json").write_bytes(body)
            cache[fn] = (res, h)
        res, h = cache[fn]
        st = res["status"]
        out[req] = [{"ref": f"easa-report:{phase}:{h[:16]}", "kind": "tool", "accepted": st in ("PASS", "FAIL"),
                     "status": st if st in ("PASS", "FAIL") else "UNKNOWN", "findings": res.get("findings", [])[:10]}]
    return out
