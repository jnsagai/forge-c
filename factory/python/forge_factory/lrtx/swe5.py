"""LRTX-T022 (P4, LL layer): SWE.5 integration verification as structured tasks for the local profile.

Tasks ("tests" visit, replaces the target-test author node):
- target:<file>: the two Renode target programs, test_<p>_target.c (scenario default) and test_<p>_target_timeout.c
  (scenario never_ready). They follow the factory's behavioural peripheral model, which is stated in the packet,
  and the interface ids of the SWE.2 static view;
- integration: the host integration program, test_<p>_integration.c. It exercises the SWE.2 sequences through the
  real LL on a RAM register array, with '@test IT-0nn @verifies IF-.. SWC_LL' blocks.

The implementation code is not shown: expected values come from the requirements, the contract and the stated
model.

Each file is validated deterministically:
- the required structure (includes, mailbox, TEST_BEGIN/END, unique TCHECK numbers);
- trace tags with known interface ids;
- only the interface functions, generated defines and the register block are used.

run_renode and run_integration then run through the role-granted operations, journaled like agent calls.
Failures go through the same triage as SWE.4 (ADR-0008): a corrected test is declared (TEST) and a correct test
files a CODE defect. The report ("author" visit) is deterministic from the tool results.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import structured as S
from . import visit as V

PHASE = "SWE.5"
FILE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["code"],
               "properties": {"code": {"type": "string", "minLength": 120}}}
TRIAGE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "reason", "code"],
                 "properties": {"verdict": {"type": "string", "enum": ["test_wrong", "code_defect"]},
                                "reason": {"type": "string", "minLength": 20}, "code": {"type": "string"}}}


def _p(ws: Path) -> dict:
    from ..layer import profile
    from .swe3 import _ident

    pr = profile(ws)
    return {**_ident(ws), "id": pr["id"], "prompt": pr.get("prompt") or {}}


def files(ws: Path) -> dict[str, str]:
    from ..simulation_performance import selected

    pid = _p(ws)["id"]
    result = {"target": f"software/tests/target/test_{pid}_target.c",
              "target_timeout": f"software/tests/target/test_{pid}_target_timeout.c",
              "integration": f"software/tests/integration/test_{pid}_integration.c"}
    performance = selected(ws)
    if performance:
        result["target_performance"] = performance["test_source"]
    return result


def interface_ids(ws: Path) -> list[str]:
    st = (Path(ws) / "workproducts/SWE.2/architecture_static.puml").read_text()
    return sorted(set(re.findall(r"\bIF-\d{2}\b", st)))


def _context(ws: Path) -> list[dict]:
    """The evidence a test author may use: interface, allocation, requirements with their contract cases, the SWE.2
    sequences - never the implementation."""
    from ..assurance.register_contract import _requirements
    from .swe3 import _defines, _sig, interfaces

    iface = interfaces(ws)
    reqs = _requirements(ws)
    eff = json.loads((Path(ws) / "workproducts/SWE.1/register_effects.json").read_text())["effects"]
    api = "\n".join(f"{_sig(f)} - {f['operation']} [{', '.join(f['fields'])}]" for f in iface["functions"])
    req = "\n".join(f"{k}: {v}" for k, v in reqs.items()) + "\n" + "\n".join(
        f"case {e['case']} ({e['swr']}): {e.get('register', '')}.{e.get('field', '')} op {e['op']}"
        + (f" value {e['value']}" if e.get("value") is not None else "") for e in eff)
    dyn = (Path(ws) / "workproducts/SWE.2/architecture_dynamic.puml").read_text()
    defs = _defines(ws, sorted({x for f in iface["functions"] for x in f["fields"]}))
    return [{"path": n, "text": t, "sha256": sha256_bytes(t.encode())} for n, t in
            (("interface", api), ("requirements+cases", req), ("SWE.2 dynamic view", dyn), ("generated defines", defs))]


def file_packet(ws: Path, kind: str, model: str, findings=None, previous=None) -> dict:
    p = _p(ws)
    rel = files(ws)[kind]
    ifs = " ".join(interface_ids(ws))
    model_txt = " ".join(str(p["prompt"].get("target_model") or "").split()) or (
        "The simulated peripheral is behavioural: every register starts at 0 and is plain read/write storage.")
    if kind.startswith("target"):
        scope = " ".join(str(p["prompt"].get("target_tests") or "").split())
        instr = (f"Write the complete Renode target test program {rel} (scenario "
                 f"{'never_ready' if kind == 'target_timeout' else 'default'}) for the {p['header']} LL. Target model: "
                 f"{model_txt} Scope of the target tests: {scope} The file is exactly: first line '/** @file "
                 f"{Path(rel).name} @verifies {ifs} */', then '#include \"{p['header']}\"', '#include "
                 "\"forge_target_test.h\"', the line 'FORGE_MAILBOX_DEFINE;', then 'int main(void) { FORGE_TEST_BEGIN(); "
                 "... FORGE_TEST_END(); return 0; }' with checks 'TCHECK(<number>, <condition>);' numbered 1, 2, 3 ... "
                 f"on LL return values and {p['block']}[LL_{p['pfx']}_<REG>_OFFSET / 4U] register bits. Expected values "
                 "follow the target model and the requirements. A poll is bounded by the caller (at most 1000 iterations). "
                 "Use only the interface functions, the generated defines and the register block.")
    else:
        scope = " ".join(str(p["prompt"].get("integration") or "the LL sequences of the SWE.2 dynamic view").split())
        instr = (f"Write the complete host integration test program {rel} for the {p['header']} LL on a plain RAM "
                 f"register array: '#include <stdio.h>', '#include <stdint.h>', '#include \"{p['header']}\"', define "
                 f"'volatile uint32_t {p['block']}[LL_{p['pfx']}_REG_COUNT];' and 'static int failures = 0;' and the "
                 "macro '#define CHECK(id, cond) do { if (cond) { printf(\"%s PASS\\n\", (id)); } else { "
                 "printf(\"%s FAIL\\n\", (id)); failures++; } } while (0)', then one static void test function per "
                 f"sequence: {scope}. Directly above each test function put '/** @test IT-0nn @verifies <interface ids "
                 f"from: {ifs}> SWC_LL */' (IT-001, IT-002 ...), and every CHECK id of that function starts with its "
                 "IT id (IT-001, IT-001-A ...; each id used once). main() clears the array, calls every test and "
                 "returns (failures == 0) ? 0 : 1. Expected values come from the requirements and their cases.")
    artifacts = _context(ws)
    if kind == "target_performance":
        from .. import simulation_performance as performance

        contract = {**performance.selected(ws), "measurement_symbols": performance.symbols(ws)}
        text = json.dumps(contract, sort_keys=True)
        artifacts.append({"path": "simulation-performance-contract", "text": text,
                          "sha256": sha256_bytes(text.encode())})
        instr += (" This is the opt-in performance stimulus program. Also include forge_performance_calls.h. "
                  "Call every listed measurement symbol at least once with valid, bounded, specification-derived "
                  "inputs and setup. A forge_measure_ wrapper has the original function's parameters and return "
                  "type. Observe a functional result with TCHECK, using the requirements/model as the oracle. "
                  "Do not estimate costs, add driver definitions, or invent timing TCHECKs. Independent Renode "
                  "hooks measure completed calls, instructions and virtual time; other functional target and "
                  "integration tests remain required. No physical hardware WCET claim.")
    return S.packet(phase=PHASE, task=f"file:{kind}", role="swe5-author", instructions=instr, sources=[],
                    artifacts=artifacts, criteria=["expected values from requirements/model, not the code",
                                                      "every interface id is verified"],
                    output_schema=FILE_SCHEMA, model=model, findings=findings, previous=previous, output_reserve=4096)


def validate_file(ws: Path, kind: str, doc: dict) -> list[str]:
    from .swe3 import _header, interfaces

    p = _p(ws)
    code, out = doc["code"], []
    if kind == "target_performance":
        from .. import simulation_performance as performance
        from ..brownfield.scope import strip_comments

        # Textual validation assists bounded repair; only compiled, completed
        # direct calls accepted by the independent observer prove coverage.
        executable = strip_comments(code)
        out += ["missing measurement call " + name for name in performance.symbols(ws)
                if not re.search(r"\b" + re.escape(name) + r"\s*\(", executable)]
        if '#include "forge_performance_calls.h"' not in code:
            out.append("missing the forge_performance_calls.h include")
    known = set(re.findall(r"#define\s+(\w+)", _header(ws).read_text()))
    api = {f["name"] for f in interfaces(ws)["functions"]}
    ifs = set(interface_ids(ws))
    used = set(re.findall(rf"\bLL_{p['pfx']}_\w+", code))
    out += [f"{x} is neither an interface function nor a generated define" for x in sorted(used - known - api)]
    if re.search(r"\(\s*(?:volatile\s+)?uint32_t\s*\*\s*\)", code):
        out.append("no integer-to-pointer casts: use the register block array")
    tags_if = set(re.findall(r"\bIF-\d{2}\b", " ".join(re.findall(r"@verifies([^*]*)", code))))
    out += [f"@verifies names {x}, which is not an interface of the SWE.2 static view" for x in sorted(tags_if - ifs)]
    if kind.startswith("target"):
        name = Path(files(ws)[kind]).name
        for need, what in ((f"@file {name}", f"first line '/** @file {name} @verifies ... */'"),
                           (f'#include "{p["header"]}"', "the LL header include"),
                           ('#include "forge_target_test.h"', "the forge_target_test.h include"),
                           ("FORGE_MAILBOX_DEFINE;", "the FORGE_MAILBOX_DEFINE; line"),
                           ("FORGE_TEST_BEGIN()", "FORGE_TEST_BEGIN()"), ("FORGE_TEST_END()", "FORGE_TEST_END()")):
            if need not in code:
                out.append(f"missing {what}")
        nums = re.findall(r"\bTCHECK\s*\(\s*(\d+)\s*,", code)
        if not nums:
            out.append("no TCHECK(<number>, <condition>) check")
        out += [f"TCHECK number {n} is used twice" for n in sorted({n for n in nums if nums.count(n) > 1})]
    else:
        tests = re.findall(r"@test\s+(IT-\d{3})", code)
        if not tests:
            out.append("no '@test IT-0nn' block")
        ids = re.findall(r'\bCHECK\s*\(\s*"([^"]+)"', code)
        out += [f"CHECK id {x} is used twice (each id names one check)" for x in sorted({x for x in ids
                                                                                       if ids.count(x) > 1})]
        out += [f"CHECK id {x} does not start with an IT id of this file" for x in sorted(set(ids))
                if not any(x == t or x.startswith(t + "-") for t in tests)]
        if "return (failures == 0) ? 0 : 1;" not in code.replace("return (failures == 0U) ? 0 : 1;",
                                                                   "return (failures == 0) ? 0 : 1;"):
            out.append("main() must return (failures == 0) ? 0 : 1")
    return out


def coverage_issues(ws: Path, recs: dict[str, dict]) -> list[str]:
    """Every interface of the static view is verified by an integration or a target test (matrix 5 rule)."""
    seen = set()
    for r in recs.values():
        seen |= set(re.findall(r"\bIF-\d{2}\b", " ".join(re.findall(r"@verifies([^*]*)", r["doc"]["code"]))))
    return [f"{x} is verified by no integration or target test" for x in interface_ids(ws) if x not in seen]


def _triage(ws: Path, kind: str, code: str, failure: list[str], model: str) -> dict:
    instr = (f"The {kind} test file below FAILED. Failed checks: {'; '.join(failure)[:700]}. Decide from the "
             "requirements, their cases and the stated target model ONLY: if the test expects something they do not "
             "state, or the wrong value, answer verdict test_wrong with the corrected complete file in code and the "
             "reason; if the test expects exactly what they state, answer verdict code_defect with code '' and a "
             "reason that quotes the requirement. Never weaken a check only to make it pass.")
    art = _context(ws) + [{"path": "failed-file", "text": code, "sha256": sha256_bytes(code.encode())}]
    return S.call(S.packet(phase=PHASE, task=f"triage:{kind}", role="swe5-author", instructions=instr, sources=[],
                           artifacts=art, criteria=["the oracle decides, never the implementation"],
                           output_schema=TRIAGE_SCHEMA, model=model, output_reserve=4096))


def visit_tests(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
                time_budget_s: float | None = None) -> dict:
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return V.reply(ws, PHASE, "FAILED", ["LRTX_SWE5_LAYER_NOT_SUPPORTED_YET (structured SWE.5 covers LL)"])
    role = {a.id: a for a in load_agents()[0]}["swe5-author"]
    since = V.last_finished(ws, PHASE)
    budget, findings = V.open_visit(ws, PHASE, resume, lambda: V.rework_findings(ws, PHASE, since) if since else [],
                                    V.author_call_limit(ws, PHASE, role.max_turns, max_calls), time_budget_s)
    try:
        return _visit_tests(ws, model, budget, findings)
    except V.Continue as c:
        return V.reply(ws, PHASE, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)
    except ValueError as exc:
        return V.reply(ws, PHASE, "FAILED", [str(exc)], budget)


def _kind_of(issue: str, ws: Path) -> str | None:
    for kind, rel in files(ws).items():
        if Path(rel).name in issue:
            return kind
    return None


def _visit_tests(ws: Path, model: str, budget: dict, findings: list[str]) -> dict:
    from ..inspection import defects
    from . import tools as T

    routed: dict[str, list[str]] = {}
    for f in findings:
        k = _kind_of(f, ws)
        for kind in [k] if k else list(files(ws)):
            routed.setdefault(f"file:{kind}", []).append(f)
    recs = {}
    for kind in files(ws):
        recs[kind] = V.run_task(ws, PHASE, f"file:{kind}", lambda fi, pr, k=kind: file_packet(ws, k, model, fi, pr),
                                lambda d, k=kind: validate_file(ws, k, d), budget, routed.get(f"file:{kind}"))
    bad = [r for r in recs.values() if r["status"] != "VALID"]
    cov = coverage_issues(ws, recs) if not bad else []
    if bad or cov:
        return V.reply(ws, PHASE, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:4]] + cov, budget)

    def write(rs):
        V.write_scoped(ws, {files(ws)[k]: r["doc"]["code"].rstrip() + "\n" for k, r in rs.items()}, "swe5_target_author")

    write(recs)
    res = {"run_renode": T.call(ws, "forge-sim-mcp", "run_renode", {}, "swe5-author", PHASE),
           "run_integration": T.call(ws, "forge-tests-mcp", "run_integration", {}, "swe5-author", PHASE)}
    failed: dict[str, list[str]] = {}
    for op, r in res.items():
        if r["status"] != "PASS":
            for i in r["issues"]:
                k = _kind_of(i, ws) or ("integration" if op == "run_integration" else "target")
                failed.setdefault(k, []).append(i)
    filed = []
    for kind, fails in failed.items():
        if budget["calls"] >= budget["max_calls"]:
            break
        budget["calls"] += 1
        t = _triage(ws, kind, recs[kind]["doc"]["code"], fails, model)
        d = t["doc"] if not t["errors"] else None
        if d is None:
            continue
        rel = files(ws)[kind]
        if d["verdict"] == "code_defect":
            try:
                filed.append(defects.report(ws, detected_phase=PHASE, reported_by="swe5-author", kind="CODE",
                                            summary=f"{Path(rel).name} fails: {d['reason']}"[:400],
                                            requirement_ids=sorted(set(re.findall(r"SWR-\d{3}", d["reason"])))[:5],
                                            test_files=[rel], evidence_refs=[f"{k}:{r['summary']}"[:120]
                                                                             for k, r in res.items()],
                                            requirement_quote=d["reason"][:300])["id"])
            except defects.DefectError as exc:
                filed.append(f"REFUSED:{exc}")
        elif validate_file(ws, kind, {"code": d["code"]}) == []:
            try:
                defects.report(ws, detected_phase=PHASE, reported_by="swe5-author", kind="TEST",
                               summary=f"{Path(rel).name} corrected: {d['reason']}"[:400],
                               requirement_ids=sorted(set(re.findall(r"SWR-\d{3}", d["reason"])))[:5],
                               test_files=[rel], evidence_refs=[], requirement_quote=d["reason"][:300])
            except defects.DefectError as exc:
                filed.append(f"REFUSED:{exc}")
                continue
            recs[kind] = {**recs[kind], "doc": {"code": d["code"]}}
            V._ckpt(ws, PHASE, f"file:{kind}").write_text(json.dumps(recs[kind], indent=1))
    if failed:
        write(recs)
        res = {"run_renode": T.call(ws, "forge-sim-mcp", "run_renode", {}, "swe5-author", PHASE),
               "run_integration": T.call(ws, "forge-tests-mcp", "run_integration", {}, "swe5-author", PHASE)}
    S.record(ws, "SWE.5/tests-assembly.json", {"at": utc_now(), "defects": filed,
                                               **{k: r.get("summary") for k, r in res.items()}})
    bad = [f"{k}: {i}" for k, r in res.items() if r["status"] != "PASS" for i in r["issues"][:6]]
    if bad:
        return V.reply(ws, PHASE, "FAILED", bad + [f"defect filed: {x}" for x in filed], budget)
    return V.reply(ws, PHASE, "PASS", [], budget, artifacts=sorted(files(ws).values()))


def visit_report(ws: Path, model: str = "", **_k) -> dict:
    """Deterministic SWE.5 report from the journaled tool results (no model call)."""
    from . import tools as T

    ws = Path(ws)
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    p = _p(ws)
    ren = T.call(ws, "forge-sim-mcp", "run_renode", {}, "swe5-author", PHASE)
    integ = T.call(ws, "forge-tests-mcp", "run_integration", {}, "swe5-author", PHASE)
    size = [json.loads(x) for x in (ws / "evidence/tool-results.jsonl").read_text().splitlines()
            if '"op": "measure_elf"' in x or '"op": "stack_usage"' in x][-2:]
    excluded = [s for s in m["scope"] if s.lower().startswith("out of scope")]
    md = ["# Integration verification report", "", "## Plan", "", "Component and integration measures: the host "
          f"integration program {files(ws)['integration']} drives the SWE.2 sequences through the real LL on a RAM "
          "register array; the Renode target programs run the LL on the simulated STM32N6 (Cortex-M55) with the "
          "behavioural peripheral model.", "", "## Integration sequence", "",
          f"The sequences of workproducts/SWE.2/architecture_dynamic.puml over the interfaces {', '.join(interface_ids(ws))} "
          "of the static view.", "", "## Clock/reset interactions tested", "",
          "Clock and reset of the peripheral are owned by the integration (SWE.2); the tests start from the model's "
          "reset values and exercise the documented key, field and flag behaviour.", "",
          "## Robustness, fault propagation, timing/resource budgets", "",
          "Polling is bounded by the caller (at most 1000 iterations; the never_ready scenario shows the bound ends "
          "the wait). Measured sizes as the tools reported them:"]
    md += [f"- {r['op']}: {r['result']['summary']} {json.dumps(r['result'].get('metrics') or {}, sort_keys=True)}"
           for r in size] or ["- not measured in SWE.5"]
    md += ["", "## Results", "", f"- run_integration (host): status {integ['status']}; \"{integ['summary']}\"",
           f"- run_renode (simulated target): status {ren['status']}; \"{ren['summary']}\"", "",
           "## Simulation vs target limitations", "", " ".join(str(p["prompt"].get("target_model") or "").split()) +
           " Simulated Cortex-M55 with a behavioural model: no clock-tree timing, no security filtering, no silicon "
           "verification.", "", "## Scope exclusions", ""]
    md += [f"- {s}" for s in excluded] or ["- none stated"]
    V.write_scoped(ws, {"workproducts/SWE.5/integration_verification_report.md": "\n".join(md) + "\n"}, "swe5_author")
    ok = ren["status"] == "PASS" and integ["status"] == "PASS"
    return V.reply(ws, PHASE, "PASS" if ok else "FAILED",
                   [] if ok else [*ren.get("issues", [])[:6], *integ.get("issues", [])[:6]], None,
                   artifacts=["workproducts/SWE.5/integration_verification_report.md"])


def visit(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    """The SWE.5 author node (also the rework entry): the test visit, then the deterministic report."""
    rep = visit_tests(ws, model, max_calls, resume=resume, time_budget_s=time_budget_s)
    return rep if rep["status"] != "PASS" else visit_report(ws, model)
