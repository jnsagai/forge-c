"""EASA-T066/T068 — the independent deterministic verifier: one executable check per ENHANCED requirement, run by
the observe-only hook (never by an agent). Each run writes a report under .forge-run/assurance/reports/<phase>/ with
its sha256; that report is the evidence the assurance gate accepts. A requirement without an executable verifier
returns NOT_SUPPORTED (it is never satisfied by default); AI inspection text is never a verifier.

Feature 009 (PG-T018): the verifiers take the work order's peripheral profile (LL header, compile unit, unit test,
API/register prefixes, register block, simulator model). Remaining peripheral limits, stated not hidden:
  * negative/boundary cases and the timeout/invalid oracle cases are derived for the RCC HAL timeout contract only
    (another peripheral: NOT_SUPPORTED with the reason);
  * the simulator-vs-RM comparison and the set/clear (non-atomic RMW) alias rules exist for RCC only (another model:
    SIMULATOR_MODEL_NOT_COMPARABLE, no alias findings);
  * the mutation operators written for RCC fields/registers apply to RCC only; no key-value operator exists;
  * the seeded-defect corpus and pilot validation are RCC campaigns (another package: NOT_APPLICABLE).
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
    from ..layer import ll_header

    p = ws / ll_header(ws)  # feature 009: the work order's LL header (RCC: stm32n6xx_ll_rcc.h)
    return p.read_text(errors="replace") if p.is_file() else ""


def _api_rx(ws: Path) -> str:
    """Feature 009: the LL/HAL function-name pattern of the work order's peripheral ((?:HAL|LL)_RCC_ for RCC)."""
    from ..layer import api_prefix

    return "(?:" + "|".join(re.escape(api_prefix(x, ws)) for x in ("HAL", "LL")) + ")"


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
    from ..layer import ll_header, register_block

    if not _hdr(ws):  # feature 009: never a PASS from an empty (wrong-peripheral) header
        return {"status": "NOT_SUPPORTED", "findings": [f"no LL header {ll_header(ws)} in the workspace"]}
    f = hardware.check_defines(_hdr(ws), idx)
    for text in _code(ws).values():
        f += [x for x in hardware.check_writes(text, _hdr(ws), idx, register_block(ws))
              if not x.startswith("NON_ATOMIC_RMW")]
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
    from ..layer import register_block

    rcc = register_block(ws) == "ll_rcc_regs"  # feature 009: other peripherals also poll IsActive/IsActiveFlag_*
    f = swe3.invariant_findings(_code(ws), _hdr(ws), _idx(ws), stated, register_block(ws),
                                "IsReady|IsEnabled" if rcc else "IsReady|IsEnabled|IsActive")
    return {"status": _ok(f), "findings": f, "mitigation_stated": stated}


def v_oracle(ws: Path) -> dict:
    from ..layer import api_header

    layer = layer_of(ws)
    hdr = Path(api_header("LL" if layer == "LL" else "HAL", ws)).name  # feature 009: the work order's API header
    srcs = [] if layer == "LL" else sorted((ws / "software/hal").glob("*.c"))
    r = oracle_gen.run(ws, [ws / "software/hal", ws / "software/ll"], srcs, hdr)
    f = [f"ORACLE_FAIL:{x[1]}:{x[2]}" for x in r.get("results", []) if x[3] == "FAIL"]
    if r["status"] in ("PASS", "FAIL") and r["provenance"]["independence_status"] != "INDEPENDENT":
        f.append("ORACLE_NOT_INDEPENDENT:" + str(r["provenance"]["contamination_reason"]))
    if r["status"] == "BUILD_FAILED" and r.get("contract"):  # the code does not follow the SWE.2 interface contract
        f.append("ORACLE_BUILD_FAILED:" + " ".join(str(r.get("reason", "")).split())[-160:])
    limits = [f"LIMITATION:{n}" for n in r.get("notes", [])]  # not derivable from requirements: stated, not a failure
    st = r["status"] if r["status"] in ("PASS", "FAIL") else "NOT_SUPPORTED"
    return {"status": "FAIL" if f else st, "findings": f + limits, "cases": r.get("cases", 0)}


def _unit_test(ws: Path) -> Path | None:
    from ..workflow.scaffold import unit_test

    p = ws / unit_test(ws)  # feature 009: test_<peripheral>.c (RCC: test_rcc.c)
    return p if p.is_file() else None


def v_mutation(ws: Path) -> dict:
    from . import mutation

    ut = _unit_test(ws)
    if ut is None:
        return {"status": "NOT_RUN", "findings": ["no unit test"]}
    from ..layer import hal_c, ll_header, ll_tu, register_prefix

    layer = layer_of(ws)
    target = (ll_header(ws) if layer == "LL" else hal_c(ws)).removeprefix("software/")
    used = set(re.findall(rf"\b({_api_rx(ws)}\w+)\s*\(", "\n".join(_code(ws).values()) + ut.read_text()))
    c = mutation.run_campaign(ws / "software", target, [ut], used_symbols=used,
                              extra_sources=[] if layer == "LL" else [], prefix=register_prefix(ws),
                              ll_unit=Path(ll_tu(ws)).name, extra_ops=mutation.register_ops(ws))
    surv = [f"SURVIVOR:{m['op']}@{m['line']}:{m['original'][:50]}" for m in c["mutants"] if m["outcome"] == "SURVIVED"]
    r = c["record"]
    return {"status": "FAIL" if surv else "PASS", "findings": surv,
            "campaign": {k: r[k] for k in ("campaign_id", "eligible", "killed", "survived", "equivalent", "invalid")}}


def v_api_execution(ws: Path) -> dict:
    """The unit test must execute every function of the code under test (static inline LL functions included)."""
    ut = _unit_test(ws)
    if ut is None:
        return {"status": "NOT_RUN", "findings": ["no unit test"]}
    from ..layer import ll_tu

    if layer_of(ws) == "LL":
        tu = ws / ll_tu(ws)
        srcs = [tu] if tu.is_file() else []
    else:
        srcs = sorted((ws / "software/hal").glob("*.c"))
    if not srcs:
        return {"status": "NOT_RUN", "findings": ["no compile unit for the code under test"]}
    fake = ws / "software/tests/unit/ll_fake"  # CAPA-038: HAL unit tests on the LL test double
    r = coverage.measure(srcs, ut, ([fake] if fake.is_dir() else []) + [ws / "software/hal", ws / "software/ll",
                                                                        ws / "software/include"])
    if r["status"] != "MEASURED":
        return {"status": "NOT_SUPPORTED", "findings": [str(r.get("reason", ""))[:160]]}
    counts: dict[str, int] = {}
    for name, n in r["function_counts"].items():  # static (inline) functions are exported as "<file>:<name>"
        key = name.split(":")[-1]
        counts[key] = max(counts.get(key, 0), n)
    defined = sorted(set(re.findall(rf"^[\w\s\*]*?\b({_api_rx(ws)}\w+)\s*\([^;{{)]*\)\s*\{{",
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
    f += _target_oracle_findings(ws)
    return {"status": _ok(f), "findings": f}


def _target_oracle_findings(ws: Path) -> list[str]:
    """F011-T034 (SWE.5/SWE.6): the frozen SafeC register oracle on the Renode target, for work orders that carry one
    (local-rtx-v2 LL); other work orders are unchanged. A case the model cannot hold is a stated limitation."""
    from ..layer import api_header
    from . import safec_oracle as SO
    from . import target_oracle

    if layer_of(ws) != "LL" or not SO.present(ws):
        return []
    hdr = Path(api_header("LL", ws)).name
    r = target_oracle.run(ws, [ws / "software/ll", ws / "software/include"], hdr)
    if r["status"] in ("UNSUPPORTED", "NOT_APPLICABLE"):
        return [f"LIMITATION:TARGET_ORACLE_{r['status']}:{r.get('reason', '')}"[:200]]
    if r["status"] == "BLOCKED":
        return [f"TARGET_ORACLE_BLOCKED:{r.get('reason', '')}"[:200]]
    out = [f"TARGET_ORACLE_{c['status']}:{c['swr']}:{c['case']}" for c in r["cases"]
           if c["status"] in ("FAIL", "BUILD_FAILED", "NO_RESULT")]
    out += [f"LIMITATION:TARGET_ORACLE_NOT_SETTABLE:{c['case']}" for c in r["cases"] if c["status"] == "NOT_SETTABLE"]
    return out + [f"LIMITATION:TARGET_ORACLE:{x}" for x in r["limits"][:1]]


def v_integration(ws: Path) -> dict:
    ops = {r.get("op") for r in swtrace._tool_records(ws) if (r.get("result") or {}).get("status") == "PASS"}
    tt = {str(p): p.read_text(errors="replace") for d in ("target", "integration")
          for p in (ws / "software/tests" / d).glob("*.c")}
    from ..layer import register_prefix

    c = T.integration_categories(tt, ops, register_prefix(ws))
    return {"status": "FAIL" if c["missing"] else "PASS",
            "findings": [f"INTEGRATION_CATEGORY_MISSING:{m}" for m in c["missing"]]}


def v_fault_injection(ws: Path) -> dict:
    st = T.fault_injection_status(ws, list((ws / "software/tests/target").glob("*.c")))  # names the profile's model
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


def v_bounded_proof(ws: Path) -> dict:
    """CBMC over every public API function: runtime-error freedom and bounded termination (assurance/formal.py)."""
    from . import formal

    return formal.cbmc(ws)


def v_eva(ws: Path) -> dict:
    """Frama-C Eva over every public API function: possible runtime errors (alarms) for all inputs/register states."""
    from . import formal

    return formal.eva(ws)


def _latest_results(ws: Path, ops: tuple[str, ...]) -> dict[str, dict]:
    p = ws / "evidence/tool-results.jsonl"
    out: dict[str, dict] = {}
    for line in (p.read_text(errors="replace").splitlines() if p.is_file() else []):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("op") in ops:
            out[r["op"]] = r
    return out


_BUDGET_KIND = (("stack_bytes", r"\bstack\b"),
                ("flash_bytes", r"\bflash\b|\bcode\b|\bROM\b|\.text|constant data|program"),
                ("static_ram_bytes", r"\b(static )?RAM\b|(?<!constant )\bdata\b"))
_UNIT = {"byte": 1, "bytes": 1, "kib": 1024, "kb": 1000, "mib": 1024 * 1024, "mb": 1000 * 1000}


def budgets_from_requirements(ws: Path) -> tuple[dict[str, int], dict[str, str]]:
    """Resource budgets stated by the frozen SWRs (component-level, swtrace.BUDGET_RX), by measured metric."""
    out, src = {}, {}
    for sid, text in swtrace.swr_texts(ws).items():
        m = swtrace.BUDGET_RX.search(text)
        if not m:
            continue
        q = re.search(r"(\d+(?:[.,]\d+)?)\s*(bytes?|KiB|KB|kB|MiB|MB)\b", text[m.start():])
        kind = next((k for k, rx in _BUDGET_KIND if re.search(rx, text, re.I)), None)
        if q and kind:
            out[kind] = int(float(q.group(1).replace(",", ".")) * _UNIT[q.group(2).lower()])
            src[kind] = sid
    return out, src


def v_resource_budgets(ws: Path) -> dict:
    """SWE.3 RESOURCE_BUDGETS: SWR budgets against the recorded measure_elf/stack_usage results (never estimated)."""
    budgets, src = budgets_from_requirements(ws)
    if not budgets:
        return {"status": "NOT_SUPPORTED", "findings": ["no resource budget stated in the frozen SWRs"]}
    res = _latest_results(ws, ("measure_elf", "stack_usage"))
    ev = swe3.resource_evidence({k: (v.get("result") or {}) for k, v in res.items()}, budgets)
    f = []
    for e in ev:
        if e["metric"] not in budgets:
            continue
        if e["provenance"] != "MEASURED":
            f.append(f"BUDGET_NOT_MEASURED:{e['metric']}:{src[e['metric']]}")
        elif e["within_budget"] is False:
            f.append(f"BUDGET_EXCEEDED:{e['metric']}:{e['value']}>{e['budget']}:{src[e['metric']]}")
    st = "FAIL" if any(x.startswith("BUDGET_EXCEEDED") for x in f) else ("NOT_SUPPORTED" if f else "PASS")
    return {"status": st, "findings": f, "budgets": budgets, "measured": ev}


_ESCALATION = re.compile(r"[^.\n]*\b(HIL|hardware[- ]in[- ]the[- ]loop|on (?:the )?(?:real )?(?:silicon|hardware|target "
                         r"board)|physical (?:target|hardware|board))\b[^.\n]*", re.I)
_NEGATED = re.compile(r"\b(not|no|never|without|cannot|n't|outside|deferred|unavailable|NOT_AVAILABLE|limitation)\b", re.I)
# i003: "... rather than proving those effects on silicon" negates the claim; "on silicon rather than in simulation"
# does not, so only a 'rather than' BEFORE the escalation term counts
_RATHER = re.compile(r"\brather than\b", re.I)


def v_fidelity(ws: Path, phase: str) -> dict:
    """SWE.5/6 FIDELITY_LABEL: the report names the environment of its executed evidence and claims no higher
    fidelity (HIL/silicon) than the producing tools provide."""
    ops = {"SWE.5": ("run_integration", "run_renode"), "SWE.6": ("run_robot", "run_renode")}[phase]
    res = _latest_results(ws, ops)
    if not res:
        return {"status": "NOT_SUPPORTED", "findings": [f"no executed {'/'.join(ops)} result recorded"]}
    envs = sorted({T.environment_of(op) for op in res})
    text = "\n".join(p.read_text(errors="replace") for p in sorted((ws / "workproducts" / phase).glob("*.md")))
    f = []
    if not re.search(r"\b(renode|host|simulat\w*|emulat\w*)\b", text, re.I):
        f.append(f"FIDELITY_LABEL_MISSING:{phase} report does not name its execution environment ({', '.join(envs)})")
    for m in _ESCALATION.finditer(text):
        term = re.search(r"HIL|hardware[- ]in[- ]the[- ]loop|silicon|hardware|target board|physical", m.group(0), re.I)
        if not _NEGATED.search(m.group(0)) and not _RATHER.search(m.group(0)[:term.start() if term else 0]):
            f += [x for op in res for x in T.check_claim("HIL", op)][:1]
            f.append(f"CLAIM_TEXT:{m.group(0).strip()[:120]}")
            break
    return {"status": _ok(f), "findings": f, "environments": envs, "hil": "NOT_AVAILABLE"}


def v_negative_boundary(ws: Path) -> dict:
    """SWE.4 NEGATIVE_BOUNDARY_CASES: requirement-derived invalid and boundary arguments of every parameterised API
    call are exercised by the unit tests (static search for the literal arguments: LIMITATION)."""
    if layer_of(ws) == "LL":
        from ..layer import profile

        if profile(ws)["ll"].get("void_signatures", True):
            return {"status": "NOT_APPLICABLE", "findings": ["NOT_APPLICABLE:the LL API takes no parameters"]}
        # feature 009 (IWDG): LL functions take values (prescaler, reload); no boundary rule is derived for them
        return {"status": "NOT_SUPPORTED", "findings": ["the LL API takes parameters; no requirement-derived boundary "
                                                        "case rule exists for this peripheral's LL (LIMITATION)"]}
    req = (ws / swtrace.REQS).read_text(errors="replace") if (ws / swtrace.REQS).is_file() else ""
    hdr = next((p for p in sorted((ws / "software/hal").glob("*.h"))), None)
    cases = oracle_gen.derive_timeouts(req, hdr.read_text(errors="replace") if hdr else "", _idx(ws))
    if not cases:
        return {"status": "NOT_SUPPORTED", "findings": ["no parameter boundary derivable from the requirements"]}
    tests = "\n".join(p.read_text(errors="replace") for p in sorted((ws / "software/tests/unit").glob("*.c")))
    alts = {"0U": r"0U?", "HAL_RCC_TIMEOUT_VALUE + 1U": r"HAL_RCC_TIMEOUT_VALUE\s*\+\s*1U?|1001U?",
            "1U": r"1U?", "HAL_RCC_TIMEOUT_VALUE": r"HAL_RCC_TIMEOUT_VALUE|1000U?"}
    f = []
    for fn in sorted({c["function"] for c in cases}):
        for arg in ("0U", "HAL_RCC_TIMEOUT_VALUE + 1U", "1U", "HAL_RCC_TIMEOUT_VALUE"):
            if not re.search(rf"\b{fn}\s*\(\s*(?:{alts[arg]})\s*\)", tests):
                f.append(f"BOUNDARY_NOT_EXERCISED:{fn}({arg})")
    return {"status": _ok(f), "findings": f + ["LIMITATION:literal-argument search; a value passed through a variable "
                                                 "is not recognised"]}


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
    "BOUNDED_PROOF_WHERE_FEASIBLE": v_bounded_proof, "STATIC_ANALYSIS": v_eva,
    "RESOURCE_BUDGETS": v_resource_budgets, "NEGATIVE_BOUNDARY_CASES": v_negative_boundary,
    "FIDELITY_LABEL": v_fidelity,  # takes the phase (SWE.5/SWE.6)
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
                res = fn(ws, phase) if fn is v_fidelity else fn(ws)
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
