"""LRTX-T022 (P4, LL layer): SWE.4 unit verification as structured tasks for the local profile.

Tests ("tests" visit, replaces the unit-test author node). The work is one task per UT id that
traceability/requirements_to_tests.csv assigns to a host unit test. The packet holds:
- the requirement (SWR) and its register-effect cases (the oracle);
- the specification items of the unit that implements it;
- the function's signature;
- the generated defines and the harness API.
The implementation code is NOT shown: expected values come from the requirements and the contract, never from the
generated code (LRTX-FR-016). The answer is one self-checking test function. It is validated deterministically:
- signature `static void ut_*(void)`;
- '@test <UT id> @verifies <USPEC ids of the unit>';
- CHECK ids equal to the UT id;
- only the harness, the unit's function, generated defines and the register block are used;
- it compiles in the harness.
Assembly puts the tests before the harness markers. `run_unit` then runs through the role-granted operation and is
journaled like an agent call.

A failing test is never bent silently (ADR-0008 L4/L13). Its repair packet shows the failed check and the
requirement, and the model chooses:
- `test_wrong`: the corrected test is declared with report_defect kind TEST before it runs again;
- `code_defect`: the factory files a CODE defect against the requirement and the visit fails, so the existing
  upstream loop sends it to SWE.3.

Report ("author" visit, deterministic): run_unit, llvm_coverage and validate_trace run again, and the unit
verification report is rendered from the tool results with the sections the SWE.4 checklist names.
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import tempfile
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import structured as S
from . import visit as V

PHASE = "SWE.4"
TEST_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["code"],
               "properties": {"code": {"type": "string", "minLength": 60}}}
REPAIR_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "reason", "code"],
                 "properties": {"verdict": {"type": "string", "enum": ["test_wrong", "code_defect"]},
                                "reason": {"type": "string", "minLength": 20},
                                "code": {"type": "string"}}}


def _harness(ws: Path) -> Path:
    from ..workflow.scaffold import unit_test

    return Path(ws) / unit_test(ws)


def cases(ws: Path) -> list[dict]:
    """One test task per (SWR, UT id) row of the SWE.1 trace that names the host unit-test file."""
    from ..assurance.register_contract import _requirements
    from .swe3 import units

    ws = Path(ws)
    rel = str(_harness(ws).relative_to(ws))
    rows = list(csv.DictReader(io.StringIO((ws / "traceability/requirements_to_tests.csv").read_text())))
    reqs = _requirements(ws)
    eff = json.loads((ws / "workproducts/SWE.1/register_effects.json").read_text())["effects"]
    us = units(ws)
    out = []
    for r in rows:
        if r["test_file"] != rel or not r["test_id"].startswith("UT-"):
            continue
        u = next((u for u in us if r["requirement_id"] in u["swrs"]), None)
        out.append({"ut": r["test_id"], "swr": r["requirement_id"], "statement": reqs.get(r["requirement_id"], ""),
                    "effects": [e for e in eff if e["swr"] == r["requirement_id"]], "unit": u})
    return out


def _unit_specs(ws: Path, u: dict) -> list[dict]:
    ck = V._ckpt(ws, "SWE.3", f"code:{u['id']}")
    return json.loads(ck.read_text())["doc"]["spec_items"] if ck.is_file() else []


def _oracle_artifacts(ws: Path, c: dict) -> list[dict]:
    """The test author's evidence: the requirement, its contract cases and the unit's specification items (the
    oracle), and the generated defines - never the implementation."""
    from .swe3 import _defines

    specs = _unit_specs(ws, c["unit"])
    oracle = (f"{c['swr']}: {c['statement']}\n" + "\n".join(
        f"case {e['case']}: {e.get('register', '')}.{e.get('field', '')} op {e['op']}" +
        (f" value {e['value']}" if e.get("value") is not None else "") for e in c["effects"]) + "\n" +
              "\n".join(f"{s['id']}: {s['behaviour']} (traces {', '.join(s['traces'])})" for s in specs))
    defs = _defines(ws, c["unit"]["function"]["fields"])
    return [{"path": "oracle", "text": oracle, "sha256": sha256_bytes(oracle.encode())},
            {"path": "generated-defines", "text": defs, "sha256": sha256_bytes(defs.encode())}]


def test_packet(ws: Path, c: dict, model: str, findings=None, previous=None) -> dict:
    from .swe3 import _ident, _sig

    i = _ident(ws)
    u = c["unit"]
    specs = _unit_specs(ws, u)
    name = "ut_" + re.sub(r"[^a-z0-9]+", "_", c["ut"].lower())
    instr = (f"Write ONE self-checking host unit test for {c['ut']}, which verifies {c['swr']} on "
             f"`{_sig(u['function'])}` (unit {u['id']}). The test is `static void {name}(void)`: call ut_reset_regs() "
             f"first, preset any register value the case needs directly in {i['block']}[LL_{i['pfx']}_<REG>_OFFSET / "
             f"4U], call the function, and check the result with EXACTLY ONE CHECK(\"{c['ut']}\", <condition>) - a test id "
             "names exactly one check, so combine every expected condition with && in that one CHECK (call the "
             "function and store results in local uint32_t variables before the CHECK when several states are "
             "checked). The expected register values and return values come ONLY from the "
             "requirement and its cases below (the oracle), never from guessing an implementation: a write case checks "
             "the field equals the case value (mask with the _MSK define), set/clear cases check the bit, query cases "
             "check the return value for the flag set AND clear, and a field update also checks that bits outside the "
             "field are preserved (preset them to 1 first). Use only the harness (ut_reset_regs, CHECK), the function "
             "under test, the register block and the generated defines below - no #include, no #define, no other "
             f"functions. Put exactly this block directly above the test: '/** @test {c['ut']} @verifies <the USPEC "
             f"ids of {u['id']} this test verifies> */' (USPEC ids only: {', '.join(s['id'] for s in specs) or 'none'}).")
    art = _oracle_artifacts(ws, c)
    return S.packet(phase=PHASE, task=f"test:{c['ut']}", role="swe4-author", instructions=instr, sources=[],
                    artifacts=art, criteria=["expected values come from the oracle", "compiles in the harness",
                                             f"exactly one CHECK, id {c['ut']}"],
                    output_schema=TEST_SCHEMA, model=model, findings=findings, previous=previous, output_reserve=3072)


def _pristine(ws: Path) -> str:
    p = Path(ws) / ".forge-run/lrtx/SWE.4/generated-harness.c"
    if not p.is_file():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_harness(ws).read_text())
    return p.read_text()


def _with_tests(ws: Path, tests: list[tuple[str, str]]) -> str:
    from ..workflow.scaffold import TEST_CALLS_MARKER, TEST_CASES_MARKER

    text = _pristine(ws)
    body = "\n\n".join(code.strip() for _n, code in tests)
    calls = "\n    ".join(f"{n}();" for n, _c in tests)
    text = text.replace(TEST_CASES_MARKER, body + "\n\n" + TEST_CASES_MARKER, 1)
    return text.replace(TEST_CALLS_MARKER, calls + ("\n    " if calls else "") + TEST_CALLS_MARKER, 1)


def validate_test(ws: Path, doc: dict, c: dict) -> list[str]:
    from .swe3 import _header, _ident

    code, out = doc["code"], []
    name = "ut_" + re.sub(r"[^a-z0-9]+", "_", c["ut"].lower())
    if not re.search(rf"\bstatic\s+void\s+{re.escape(name)}\s*\(\s*void\s*\)\s*\{{", code):
        out.append(f"the test must be exactly `static void {name}(void)`")
    m = re.search(r"/\*\*.*?\*/", code, re.S)
    tags = m.group(0) if m else ""
    if f"@test {c['ut']}" not in tags:
        out.append(f"the block above the test needs '@test {c['ut']}'")
    specs = {s["id"] for s in _unit_specs(ws, c["unit"])}
    ver = re.findall(r"\bUSPEC-[A-Z]+-\d{2}-\d{2}\b", " ".join(re.findall(r"@verifies([^@*]*)", tags)))
    if not ver:
        out.append("'@verifies' must list the USPEC ids this test verifies")
    out += [f"@verifies {v} is not a specification item of {c['unit']['id']}" for v in ver if v not in specs]
    if re.search(r"@verifies[^@*]*\b(SWR|SWU|IF)-", tags):
        out.append("@verifies lists USPEC ids only (never SWR-, SWU- or IF- ids)")
    ids = re.findall(r'\bCHECK\s*\(\s*"([^"]+)"', code)
    if not ids:
        out.append(f'the test checks nothing: use CHECK("{c["ut"]}", <condition>)')
    out += [f"CHECK id {x} must be {c['ut']}" for x in sorted(set(ids)) if x != c["ut"]]
    if len(ids) > 1:
        out.append(f"use exactly one CHECK(\"{c['ut']}\", ...): combine the {len(ids)} conditions with && (a test id "
                   "names exactly one check)")
    if re.search(r"^\s*#", code, re.M):
        out.append("no #include or #define in a test")
    i = _ident(ws)
    known = set(re.findall(r"#define\s+(\w+)", _header(ws).read_text()))
    used = set(re.findall(rf"\bLL_{i['pfx']}_\w+", code)) - {c["unit"]["function"]["name"]}
    allowed_fn = {c["unit"]["function"]["name"]}
    out += [f"{x} is not a generated define" for x in sorted(used - known) if x not in allowed_fn]
    body = code.split("{", 1)[-1]
    calls = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", body)) - {"if", "sizeof", "CHECK", "ut_reset_regs", "return"}
    out += [f"call to {x}: a test calls only ut_reset_regs, CHECK and {c['unit']['function']['name']}"
            for x in sorted(calls - allowed_fn)]
    if not out:
        out += _compile_test(ws, name, code)
    return out


def _compile_test(ws: Path, name: str, code: str) -> list[str]:
    from .swe3 import _header

    text = _with_tests(ws, [(name, code)])
    with tempfile.TemporaryDirectory() as td:
        t = Path(td) / "t.c"
        t.write_text(text)
        r = subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror", "-fsyntax-only",
                            f"-I{_header(ws).parent}", str(t)], capture_output=True, text=True)
    errs = [ln.split(" error: ", 1)[1][:160] for ln in r.stderr.splitlines() if " error: " in ln]
    return [f"compile: {e}" for e in errs[:6]] or ([f"compile failed: {r.stderr[:160]}"] if r.returncode else [])


def repair_packet(ws: Path, c: dict, code: str, failure: list[str], model: str) -> dict:
    instr = (f"The test of {c['ut']} below FAILED when run against the implementation of "
             f"{c['unit']['function']['name']}. Failed checks: {'; '.join(failure)[:600]}. Decide from the requirement "
             "and its cases (the oracle) ONLY: if the test asserts something the requirement does not state, or asserts "
             "it wrongly, answer verdict test_wrong with the corrected test in code and the reason; if the test asserts "
             "exactly what the requirement and its cases state, answer verdict code_defect with code '' and a reason "
             "that quotes the requirement - the implementation is then corrected upstream. Never weaken a check only "
             "to make it pass.")
    art = [{"path": "failed-test", "text": code, "sha256": sha256_bytes(code.encode())}]
    return S.packet(phase=PHASE, task=f"triage:{c['ut']}", role="swe4-author", instructions=instr, sources=[],
                    artifacts=_oracle_artifacts(ws, c) + art, criteria=["the oracle decides, never the implementation"],
                    output_schema=REPAIR_SCHEMA, model=model, output_reserve=3072)


def _failures(res: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for i in res.get("issues") or []:
        m = re.search(r"#(UT-\d+):", i) or re.search(r"\b(UT-\d+)\b", i)
        if m:
            out.setdefault(m.group(1), []).append(i)
    return out


def visit_tests(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
                time_budget_s: float | None = None) -> dict:
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return V.reply(ws, PHASE, "FAILED", ["LRTX_SWE4_LAYER_NOT_SUPPORTED_YET (structured SWE.4 covers LL)"])
    role = {a.id: a for a in load_agents()[0]}["swe4-author"]
    since = V.last_finished(ws, PHASE)
    budget, findings = V.open_visit(ws, PHASE, resume, lambda: V.rework_findings(ws, PHASE, since) if since else [],
                                    max_calls or role.max_turns, time_budget_s)
    try:
        return _visit_tests(ws, model, budget, findings)
    except V.Continue as c:
        return V.reply(ws, PHASE, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)
    except ValueError as exc:
        return V.reply(ws, PHASE, "FAILED", [str(exc)], budget)


def _visit_tests(ws: Path, model: str, budget: dict, findings: list[str]) -> dict:
    from ..inspection import defects
    from . import tools as T

    cs = cases(ws)
    missing = [c["ut"] for c in cs if c["unit"] is None]
    if missing:
        return V.reply(ws, PHASE, "FAILED", [f"{u}: its requirement is allocated to no SWE.3 unit" for u in missing],
                       budget)
    routed: dict[str, list[str]] = {}
    for f in findings:
        for ut in re.findall(r"\bUT-\d+\b", f) or [c["ut"] for c in cs]:
            routed.setdefault(f"test:{ut}", []).append(f)
    recs = []
    for c in cs:
        name = "ut_" + re.sub(r"[^a-z0-9]+", "_", c["ut"].lower())
        rec = V.run_task(ws, PHASE, f"test:{c['ut']}", lambda fi, pr, c=c: test_packet(ws, c, model, fi, pr),
                         lambda d, c=c: validate_test(ws, d, c), budget, routed.get(f"test:{c['ut']}"))
        recs.append((c, name, rec))
    bad = [r for _c, _n, r in recs if r["status"] != "VALID"]
    if bad:
        return V.reply(ws, PHASE, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:4]], budget)
    rel = str(_harness(ws).relative_to(ws))
    V.write_scoped(ws, {rel: _with_tests(ws, [(n, r["doc"]["code"]) for _c, n, r in recs])}, "swe4_test_author")
    res = T.call(ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", PHASE)
    fails = _failures(res) if res["status"] != "PASS" else {}
    if res["status"] != "PASS" and not fails:
        return V.reply(ws, PHASE, "FAILED", [f"run_unit: {i}" for i in res["issues"][:10]], budget)
    filed = []
    for c, _name, rec in recs:
        if c["ut"] not in fails or budget["calls"] >= budget["max_calls"]:
            continue
        budget["calls"] += 1
        tri = S.call(repair_packet(ws, c, rec["doc"]["code"], fails[c["ut"]], model))
        d = tri["doc"] if not tri["errors"] else None
        if d is None:
            continue
        if d["verdict"] == "code_defect":
            try:
                filed.append(defects.report(ws, detected_phase=PHASE, reported_by="swe4-author", kind="CODE",
                                            summary=f"{c['ut']} fails: {d['reason']}"[:400], requirement_ids=[c["swr"]],
                                            test_files=[rel], evidence_refs=[f"run_unit:{res.get('summary', '')}"[:120]],
                                            requirement_quote=c["statement"][:300])["id"])
            except defects.DefectError as exc:
                filed.append(f"REFUSED:{exc}")
        elif validate_test(ws, {"code": d["code"]}, c) == []:
            try:  # a test corrected after it failed is declared, never silently bent (ADR-0008 L4)
                defects.report(ws, detected_phase=PHASE, reported_by="swe4-author", kind="TEST",
                               summary=f"{c['ut']} corrected: {d['reason']}"[:400], requirement_ids=[c["swr"]],
                               test_files=[rel], evidence_refs=[], requirement_quote=c["statement"][:300])
            except defects.DefectError as exc:
                filed.append(f"REFUSED:{exc}")
                continue
            ck = V._ckpt(ws, PHASE, f"test:{c['ut']}")
            st = json.loads(ck.read_text())
            st["doc"] = {"code": d["code"]}
            st["declared_correction"] = d["reason"][:300]
            ck.write_text(json.dumps(st, indent=1))
    if fails:
        recs = [(c, n, json.loads(V._ckpt(ws, PHASE, f"test:{c['ut']}").read_text())) for c, n, _r in recs]
        V.write_scoped(ws, {rel: _with_tests(ws, [(n, r["doc"]["code"]) for _c, n, r in recs])}, "swe4_test_author")
        res = T.call(ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", PHASE)
    S.record(ws, "SWE.4/tests-assembly.json", {"at": utc_now(), "tests": [c["ut"] for c, _n, _r in recs],
                                               "defects": filed, "run_unit": res.get("summary")})
    if res["status"] != "PASS":
        return V.reply(ws, PHASE, "FAILED", [f"run_unit: {i}" for i in res["issues"][:10]] +
                       [f"defect filed: {x}" for x in filed], budget)
    return V.reply(ws, PHASE, "PASS", [], budget, artifacts=[rel])


def visit_report(ws: Path, model: str = "", **_k) -> dict:
    """Deterministic SWE.4 report from the journaled tool results (no model call)."""
    from . import tools as T

    ws = Path(ws)
    try:
        cs = cases(ws)
    except ValueError as exc:
        return V.reply(ws, PHASE, "FAILED", [str(exc)])
    run = T.call(ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", PHASE)
    cov = T.call(ws, "forge-tests-mcp", "llvm_coverage", {}, "swe4-author", PHASE)
    tr = T.call(ws, "forge-evidence-mcp", "validate_trace", {}, "swe4-author", PHASE)
    sa = [json.loads(x) for x in (ws / "evidence/tool-results.jsonl").read_text().splitlines()
          if '"op": "cppcheck"' in x or '"op": "clang_analyze"' in x]
    kinds = {"write": "positive", "set": "positive", "clear": "positive", "no_write": "positive"}
    md = ["# Unit verification report", "",
          "## Measures, environment, entry/exit criteria and regression", "",
          "Host clang build of the self-checking unit tests against the header-only LL driver on a plain RAM register "
          "array (host evidence, not target). Entry: the SWE.3 baseline is frozen. Exit: every UT PASS and the "
          "coverage goal met or a deviation recorded. Regression: the full suite is re-run on every change.", "",
          "## Test cases", "", "| UT id | function | SWR ids | kind | result |", "| --- | --- | --- | --- | --- |"]
    md += [f"| {c['ut']} | {c['unit']['function']['name']} | {c['swr']} | "
           f"{kinds.get((c['effects'] or [{}])[0].get('op'), 'positive')} | {run['status']} (suite) |" for c in cs]
    md += ["", "## Mock fidelity", "", "Plain RAM register array: no write-1-to-clear, read-only or hardware side "
           "effects; flags are preset by the test. Limitation: hardware update latency (e.g. PVU/RVU) is not modelled.",
           "", "## Static analysis", ""]
    md += [f"- {r['op']} ({r['phase']}): status {r['result']['status']}; \"{r['result']['summary']}\"; issues "
           f"{r['result']['issues']}" for r in sa[-2:]] or ["- not run"]
    md += ["", "## Coverage", "", "Goal: 100% statement/branch of the driver code. Reported exactly as the tool reported "
           f"it: status {cov['status']}; \"{cov['summary']}\"; metrics {json.dumps(cov.get('metrics') or {}, sort_keys=True)}.",
           "", "## Results", "", f"run_unit: status {run['status']}; \"{run['summary']}\". validate_trace: status "
           f"{tr['status']}; \"{tr.get('summary', '')}\".", "", "## Findings", ""]
    findings = [*run.get("issues", [])[:10], *tr.get("issues", [])[:10]]
    md += [f"- {f}" for f in findings] or ["none"]
    V.write_scoped(ws, {"workproducts/SWE.4/unit_verification_report.md": "\n".join(md) + "\n"}, "swe4_author")
    status = "PASS" if run["status"] == "PASS" else "FAILED"
    return V.reply(ws, PHASE, status, [] if status == "PASS" else findings, None,
                   artifacts=["workproducts/SWE.4/unit_verification_report.md"])


def visit(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    """The SWE.4 author node (also the rework entry): the test visit (resumed, or a new visit that repairs from the
    findings), then the deterministic report when the tests pass."""
    rep = visit_tests(ws, model, max_calls, resume=resume, time_budget_s=time_budget_s)
    if rep["status"] != "PASS":
        return rep
    return visit_report(ws, model)
