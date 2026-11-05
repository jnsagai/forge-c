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

from ..assurance import register_contract as RC
from ..common import sha256_bytes, utc_now
from . import structured as S
from . import visit as V

PHASE = "SWE.4"
KINDS = ("positive", "negative", "boundary", "error")
UPSTREAM_ITEMS = ("SWE4-04:",)  # findings on the SWE.3 code's static analysis: no SWE.4 test can address them
DEVIATIONS = "workproducts/SWE.3/misra_deviations.md"
# CAPA-092 (run WO-F014-SWE4-IWDG-20261101-L1, SWE4-02): the test author declares the kinds of check its test holds;
# the report shows them instead of labelling every structured test 'positive'.
TEST_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["code", "kinds"],
               "properties": {"code": {"type": "string", "minLength": 60},
                              "kinds": {"type": "array", "minItems": 1, "maxItems": 4, "uniqueItems": True,
                                        "items": {"type": "string", "enum": list(KINDS)}}}}
REPAIR_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "reason", "code"],
                 "properties": {"verdict": {"type": "string", "enum": ["test_wrong", "code_defect"]},
                                "reason": {"type": "string", "minLength": 20},
                                "code": {"type": "string"}}}


def _harness(ws: Path) -> Path:
    from ..workflow.scaffold import unit_test

    return Path(ws) / unit_test(ws)


def uspec_mode(ws: Path) -> bool:
    from ..layer import uspec_gtest

    return uspec_gtest(ws)


def plan_cases(ws: Path, write: bool = True) -> list[dict]:
    """Owner 2026-11-03 (V-model): one test task per USPEC item of the frozen SWE.3 units, UT ids assigned by SWE.4
    (inspection/uspec_plan). The oracle is the requirement side the USPEC traces to (SWR text and register-effect
    cases) and the USPEC behaviour; component constraints are verified at SWE.6."""
    from ..assurance.register_contract import _requirements
    from ..inspection import uspec_plan as P
    from .swe3 import units

    ws = Path(ws)
    plan = P.current(ws)
    if write:
        V.write_scoped(ws, P.files(plan), "swe4_test_author")
    us = {u["id"]: u for u in units(ws)}
    reqs = _requirements(ws)
    eff = json.loads((ws / "workproducts/SWE.1/register_effects.json").read_text())["effects"]
    out = []
    for t in plan["tasks"]:
        u = us.get(t["unit"])
        out.append({"ut": t["ut"], "uspec": t["uspec"], "behaviour": t["behaviour"], "plan": t, "swrs": t["swrs"],
                    "swr": ", ".join(t["swrs"]) or "-", "statement": " ".join(reqs.get(r, "") for r in t["swrs"]),
                    "statements": {r: reqs.get(r, "") for r in t["swrs"]},
                    "effects": [e for e in eff if e["swr"] in t["swrs"]], "unit": u})
    for t in plan.get("closure", []):  # owner 2026-11-03 (D): closure tests of an earlier round of this visit
        out.append({**_closure_case(ws, t["gap"], t["ut"]), "uspec": t["uspec"], "verifies": t["verifies"]})
    return out


def cases(ws: Path) -> list[dict]:
    """One test task per (SWR, UT id) row of the SWE.1 trace that names the host unit-test file (work orders before
    2026-11-03); with unit_verification, one task per USPEC item (plan_cases)."""
    from ..assurance.register_contract import _requirements
    from .swe3 import units

    ws = Path(ws)
    if uspec_mode(ws):
        return plan_cases(ws, write=False)
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
    if c.get("uspec"):  # owner 2026-11-03: the USPEC item under test, its requirements and their cases
        u = c["unit"]
        oracle = (f"{c['uspec']} (unit {u['id']}, {u['function']['name']}) - the specification item this test "
                  f"verifies: {c['behaviour']}\n" + "".join(f"{r}: {t}\n" for r, t in c["statements"].items()) +
                  "".join(f"case {e['case']} ({e['swr']}): {e.get('register', '')}.{e.get('field', '')} op {e['op']}"
                          + RC.value_text(e) + "\n" for e in c["effects"]) +
                  ("Constraints verified at SWE.6, not by this unit test: " +
                   ", ".join(c["plan"]["constraints_verified_at_swe6"]) + "\n"
                   if c["plan"].get("constraints_verified_at_swe6") else "") +
                  "Other specification items of this unit (each verified by its own test): " +
                  ("; ".join(f"{s['id']}: {s['behaviour']}" for s in specs if s["id"] != c["uspec"]) or "none"))
        defs = _defines(ws, u["function"]["fields"])
        return [{"path": "oracle", "text": oracle, "sha256": sha256_bytes(oracle.encode())},
                {"path": "generated-defines", "text": defs, "sha256": sha256_bytes(defs.encode())}]
    oracle = (f"{c['swr']}: {c['statement']}\n" + "\n".join(
        f"case {e['case']}: {e.get('register', '')}.{e.get('field', '')} op {e['op']}" +
        RC.value_text(e) for e in c["effects"]) + "\n" +
              "\n".join(f"{s['id']}: {s['behaviour']} (traces {', '.join(s['traces'])})" for s in specs))
    defs = _defines(ws, c["unit"]["function"]["fields"])
    return [{"path": "oracle", "text": oracle, "sha256": sha256_bytes(oracle.encode())},
            {"path": "generated-defines", "text": defs, "sha256": sha256_bytes(defs.encode())}]


def _preset_rule(ws: Path, fields: list[str]) -> str:
    """Where a test presets and reads registers: the register-block array, or (instance mode) the instance macro."""
    from ..layer import ll_instance
    from .swe3 import _ident

    i, inst = _ident(ws), ll_instance(ws)
    if inst is None:
        return f"directly in {i['block']}[LL_{i['pfx']}_<REG>_OFFSET / 4U], call the function"
    regs = dict.fromkeys(f.split(".")[0] for f in fields)
    members = ", ".join(f"{inst['macro']}->{inst['members'][r]} for {r}" for r in regs if r in inst["members"])
    return (f"directly through the instance macro {inst['macro']} ({members or inst['macro'] + '-><MEMBER>'}; in the "
            f"host build {inst['macro']} is the RAM instance {inst['host_object']}), call the function with "
            f"{inst['macro']} as its instance argument")


def gtest_mode(ws: Path) -> bool:
    """Owner 2026-11-03: the requirement-based unit tests are GoogleTest TESTs (the harness is test_<id>.cpp)."""
    return _harness(ws).suffix == ".cpp"


ORACLE_RULES = (
    "The expected register values and return values come ONLY from the specification item, the requirements and their "
    "cases below (the oracle), never from guessing an implementation: a write case checks the field equals the case "
    "value (mask with the _MSK define), set/clear cases check the bit, query cases check the return value for the flag "
    "set AND clear, and a field update also checks that bits outside the field are preserved (preset them to 1 first). "
    "Design the test beyond the single case value: when the function takes a value argument, also check the boundaries "
    "of the field - the minimum (0) and the maximum (every field bit set, the _MSK value shifted down) - each with its "
    "own call after ut_reset_regs() or a fresh preset; check that what must NOT change does not change (bits outside "
    "the field, the other register words, a flag that is clear reads 0).")


def gtest_packet(ws: Path, c: dict, model: str, findings=None, previous=None) -> dict:
    """One GoogleTest TEST(<unit>, UT_nnn) per USPEC item (owner 2026-11-03)."""
    from ..inspection.uspec_plan import suite_name, ut_name
    from .swe3 import _sig

    u = c["unit"]
    suite, name = suite_name(u["id"]), ut_name(c["ut"])
    instr = (f"Write ONE GoogleTest test for {c['ut']}, which verifies the specification item {c['uspec']} of unit "
             f"{u['id']} (requirements {c['swr']}) on `{_sig(u['function'])}`. The test is exactly "
             f"`TEST({suite}, {name})` with its body: call ut_reset_regs() first, preset any register value the case "
             f"needs {_preset_rule(ws, u['function']['fields'])}, and check every expected result with EXPECT_EQ, "
             "EXPECT_NE, EXPECT_TRUE or EXPECT_FALSE (unsigned constants with the U suffix; call the function and keep "
             "results in local uint32_t variables when several states are checked). " + ORACLE_RULES +
             " Declare in kinds the kinds of check the test really contains: positive (the case value gives the "
             "required effect), boundary (field minimum/maximum checked), negative (a state or bit that must not change "
             "or must read 0 is checked), error (ONLY if the requirement states an error behaviour - never invent one). "
             + (f"This specification item is a {c['plan']['test_kind']} behaviour: the test checks exactly that "
                f"behaviour and kinds includes {c['plan']['test_kind']}. "
                if (c.get("plan") or {}).get("test_kind", "positive") != "positive" else "") +
             "Use only the harness (ut_reset_regs), the function under test, the register block, the generated defines "
             "below and the GoogleTest EXPECT_/ASSERT_ macros - no #include, no #define, no fixture (TEST_F), no other "
             f"functions. Put exactly this block directly above the test: '/** @test {c['ut']} @verifies {c['uspec']} */' "
             "(this test verifies exactly that specification item; the other items of the unit have their own tests).")
    from .swe5 import HOST_ACCESS_RULE, has_prohibition

    if has_prohibition(c.get("statement", "")):
        instr += " " + HOST_ACCESS_RULE
    return S.packet(phase=PHASE, task=f"test:{c['ut']}", role="swe4-author", instructions=instr, sources=[],
                    artifacts=_oracle_artifacts(ws, c), criteria=[
                        "expected values come from the oracle", "compiles in the GoogleTest harness",
                        f"exactly one TEST({suite}, {name})", "kinds declares only the kinds of check the code contains"],
                    output_schema=TEST_SCHEMA, model=model, findings=findings, previous=previous, output_reserve=3072)


GTEST_MACRO = re.compile(r"^(?:EXPECT|ASSERT)_[A-Z_]+$|^SCOPED_TRACE$")


def validate_gtest(ws: Path, doc: dict, c: dict, verifies: list[str] | None = None, closure: bool = False) -> list[str]:
    from ..brownfield.scope import strip_comments
    from ..inspection.uspec_plan import suite_name, ut_name
    from ..layer import ll_instance
    from .swe3 import _header, _ident

    code, out = doc["code"], []
    suite, name = suite_name(c["unit"]["id"]), ut_name(c["ut"])
    nc = strip_comments(code)
    heads = re.findall(r"\bTEST(?:_F)?\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)", nc)
    if heads != [(suite, name)] or not re.search(rf"\bTEST\s*\(\s*{suite}\s*,\s*{name}\s*\)\s*\{{", nc):
        out.append(f"the code must be exactly one `TEST({suite}, {name}) {{ ... }}` (found {heads})")
    m = re.search(r"/\*\*.*?\*/", code, re.S)
    tags = m.group(0) if m else ""
    if f"@test {c['ut']}" not in tags:
        out.append(f"the block above the test needs '@test {c['ut']}'")
    ver = re.findall(r"\bUSPEC-[A-Z]+-\d{2,}-\d{2,}\b", " ".join(re.findall(r"@verifies([^@*]*)", tags)))
    want = verifies or [c["uspec"]]
    if ver != want:
        out.append(f"'@verifies' must name exactly {' '.join(want)} (the specification item(s) of {c['ut']})")
    if re.search(r"@verifies[^@*]*\b(SWR|SWU|IF)-", tags):
        out.append("@verifies lists USPEC ids only (never SWR-, SWU- or IF- ids)")
    body = nc.split("{", 1)[-1]
    macros = set(re.findall(r"\b((?:EXPECT|ASSERT)_[A-Z_]+)\s*\(", body))
    if not macros:
        out.append("the test checks nothing: use EXPECT_EQ/EXPECT_TRUE/... on the expected results")
    if re.search(r"^\s*#", code, re.M):
        out.append("no #include or #define in a test")
    idn = _ident(ws)
    out += V.offset_index_errors(code, idn["block"], idn["pfx"]) if idn.get("block") else []
    inst = ll_instance(ws)
    if inst is not None and re.search(rf"\b{re.escape(idn['block'])}\b", nc):
        out.append(f"{idn['block']} does not exist in instance mode: preset and read registers through "
                   f"{inst['macro']}-><MEMBER>")
    out += _kind_errors(doc, c, body) if not closure else []
    known = set(re.findall(r"#define\s+(\w+)", _header(ws).read_text()))
    fn = c["unit"]["function"]["name"]
    used = set(re.findall(rf"\bLL_{idn['pfx']}_\w+", nc)) - {fn}
    out += [f"{x} is not a generated define" for x in sorted(used - known)]
    calls = {x for x in re.findall(r"\b([A-Za-z_]\w*)\s*\(", body) if not GTEST_MACRO.match(x)} - \
        {"if", "sizeof", "ut_reset_regs", "return", fn}
    out += [f"call to {x}: a test calls only ut_reset_regs, the GoogleTest EXPECT_/ASSERT_ macros and {fn}"
            for x in sorted(calls)]
    if not out:
        out += _compile_test(ws, name, code)
    return out


def _kind_errors(doc: dict, c: dict, body: str) -> list[str]:
    kinds = list(doc.get("kinds") or [])
    fn = c["unit"]["function"]
    ncalls = len(re.findall(rf"\b{re.escape(fn['name'])}\s*\(", body))
    out = []
    want = (c.get("plan") or {}).get("test_kind")
    if want and want != "positive":  # owner 2026-11-03: the kind follows from the USPEC item
        if want not in kinds:
            out.append(f"{c['uspec']} is a {want} behaviour: the test checks it and kinds includes {want}")
    elif "positive" not in kinds:
        out.append("kinds must include positive (the case value of the oracle)")
    # CAPA-092, kept in the USPEC model: every test of a value-taking function also checks the field limits
    if _takes_value(fn) and "boundary" not in kinds:
        out.append(f"{fn['name']} takes a value: check the field minimum and maximum too and declare kind boundary")
    if "boundary" in kinds and ncalls < 2:
        out.append(f"kind boundary needs the field minimum/maximum checked with further calls of {fn['name']}")
    return out


def test_packet(ws: Path, c: dict, model: str, findings=None, previous=None) -> dict:
    from .swe3 import _sig

    if c.get("closure"):
        return closure_packet(ws, c, model, findings, previous)
    if c.get("uspec") and gtest_mode(ws):
        return gtest_packet(ws, c, model, findings, previous)
    u = c["unit"]
    specs = _unit_specs(ws, u)
    name = "ut_" + re.sub(r"[^a-z0-9]+", "_", c["ut"].lower())
    what = (f"the specification item {c['uspec']} of unit {u['id']} (requirements {c['swr']})" if c.get("uspec")
            else c["swr"])
    instr = (f"Write ONE self-checking host unit test for {c['ut']}, which verifies {what} on "
             f"`{_sig(u['function'])}` (unit {u['id']}). The test is `static void {name}(void)`: call ut_reset_regs() "
             f"first, preset any register value the case needs {_preset_rule(ws, u['function']['fields'])}, and check "
             f"the result with EXACTLY ONE CHECK(\"{c['ut']}\", <condition>) - a test id "
             "names exactly one check, so combine every expected condition with && in that one CHECK (call the "
             "function and store results in local uint32_t variables before the CHECK when several states are "
             "checked). The expected register values and return values come ONLY from the "
             "requirement and its cases below (the oracle), never from guessing an implementation: a write case checks "
             "the field equals the case value (mask with the _MSK define), set/clear cases check the bit, query cases "
             "check the return value for the flag set AND clear, and a field update also checks that bits outside the "
             "field are preserved (preset them to 1 first). Design the test beyond the single case value: when the "
             "function takes a value argument, also check the boundaries of the field - the minimum (0) and the maximum "
             "(every field bit set, the _MSK value shifted down) - each with its own call after ut_reset_regs() or a "
             "fresh preset; check that what must NOT change does not change (bits outside the field, the other register "
             "words, a flag that is clear reads 0). Declare in kinds the kinds of check the test really contains: "
             "positive (the case value gives the required effect), boundary (field minimum/maximum checked), negative "
             "(a state or bit that must not change or must read 0 is checked), error (ONLY if the requirement states an "
             "error behaviour - never invent one). Use only the harness (ut_reset_regs, CHECK), the function "
             "under test, the register block and the generated defines below - no #include, no #define, no other "
             + (f"functions. Put exactly this block directly above the test: '/** @test {c['ut']} @verifies "
                f"{c['uspec']} */' (this test verifies exactly that specification item; the other items of the unit "
                "have their own tests)." if c.get("uspec") else
                f"functions. Put exactly this block directly above the test: '/** @test {c['ut']} @verifies <the USPEC "
                f"ids of {u['id']} this test verifies> */' (USPEC ids only: {', '.join(s['id'] for s in specs) or 'none'})."))
    from .swe5 import HOST_ACCESS_RULE, has_prohibition

    if has_prohibition(c.get("statement", "")):
        instr += " " + HOST_ACCESS_RULE
    art = _oracle_artifacts(ws, c)
    return S.packet(phase=PHASE, task=f"test:{c['ut']}", role="swe4-author", instructions=instr, sources=[],
                    artifacts=art, criteria=["expected values come from the oracle", "compiles in the harness",
                                             f"exactly one CHECK, id {c['ut']}",
                                             "kinds declares only the kinds of check the code contains"],
                    output_schema=TEST_SCHEMA, model=model, findings=findings, previous=previous, output_reserve=3072)


def _pristine(ws: Path) -> str:
    p = Path(ws) / f".forge-run/lrtx/SWE.4/generated-harness{_harness(ws).suffix}"
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

    if c.get("closure"):
        return validate_closure(ws, doc, c) if "verdict" in doc else validate_gtest(
            ws, doc, c, verifies=c.get("verifies"), closure=True)
    if c.get("uspec") and gtest_mode(ws):
        return validate_gtest(ws, doc, c)
    code, out = doc["code"], []
    name = "ut_" + re.sub(r"[^a-z0-9]+", "_", c["ut"].lower())
    if not re.search(rf"\bstatic\s+void\s+{re.escape(name)}\s*\(\s*void\s*\)\s*\{{", code):
        out.append(f"the test must be exactly `static void {name}(void)`")
    m = re.search(r"/\*\*.*?\*/", code, re.S)
    tags = m.group(0) if m else ""
    if f"@test {c['ut']}" not in tags:
        out.append(f"the block above the test needs '@test {c['ut']}'")
    specs = {s["id"] for s in _unit_specs(ws, c["unit"])}
    ver = re.findall(r"\bUSPEC-[A-Z]+-\d{2,}-\d{2,}\b", " ".join(re.findall(r"@verifies([^@*]*)", tags)))
    if not ver:
        out.append("'@verifies' must list the USPEC ids this test verifies")
    out += [f"@verifies {v} is not a specification item of {c['unit']['id']}" for v in ver if v not in specs]
    if c.get("uspec") and ver and ver != [c["uspec"]]:  # owner 2026-11-03: one test per USPEC item, by construction
        out.append(f"'@verifies' must name exactly {c['uspec']} (the specification item of {c['ut']})")
    if re.search(r"@verifies[^@*]*\b(SWR|SWU|IF)-", tags):
        out.append("@verifies lists USPEC ids only (never SWR-, SWU- or IF- ids)")
    from ..brownfield.scope import strip_comments

    # CAPA-095 (run WO-F014-SWE4-OBL-20261101-L3): the comment "read back unchanged (all bits set)" was taken for a call
    # to `unchanged`; the checks of calls and identifiers read the code without its comments
    nc = strip_comments(code)
    ids = re.findall(r'\bCHECK\s*\(\s*"([^"]+)"', code)  # string literal content is blanked in nc
    if not ids:
        out.append(f'the test checks nothing: use CHECK("{c["ut"]}", <condition>)')
    out += [f"CHECK id {x} must be {c['ut']}" for x in sorted(set(ids)) if x != c["ut"]]
    if len(ids) > 1:
        out.append(f"use exactly one CHECK(\"{c['ut']}\", ...): combine the {len(ids)} conditions with && (a test id "
                   "names exactly one check)")
    if re.search(r"^\s*#", code, re.M):
        out.append("no #include or #define in a test")
    idn = _ident(ws)
    out += V.offset_index_errors(code, idn["block"], idn["pfx"]) if idn.get("block") else []
    from ..layer import ll_instance

    inst = ll_instance(ws)
    if inst is not None and re.search(rf"\b{re.escape(idn['block'])}\b", strip_comments(code)):
        out.append(f"{idn['block']} does not exist in instance mode: preset and read registers through "
                   f"{inst['macro']}-><MEMBER>")
    kinds = list(doc.get("kinds") or [])
    fn = c["unit"]["function"]
    ncalls = len(re.findall(rf"\b{re.escape(fn['name'])}\s*\(", nc.split("{", 1)[-1]))
    if "positive" not in kinds:
        out.append("kinds must include positive (the case value of the oracle)")
    if _takes_value(fn) and "boundary" not in kinds:
        out.append(f"{fn['name']} takes a value: check the field minimum and maximum too and declare kind boundary")
    if "boundary" in kinds and ncalls < 2:
        out.append(f"kind boundary needs the field minimum/maximum checked with further calls of {fn['name']}")
    i = _ident(ws)
    known = set(re.findall(r"#define\s+(\w+)", _header(ws).read_text()))
    used = set(re.findall(rf"\bLL_{i['pfx']}_\w+", nc)) - {c["unit"]["function"]["name"]}
    allowed_fn = {c["unit"]["function"]["name"]}
    out += [f"{x} is not a generated define" for x in sorted(used - known) if x not in allowed_fn]
    body = nc.split("{", 1)[-1]
    calls = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", body)) - {"if", "sizeof", "CHECK", "ut_reset_regs", "return"}
    out += [f"call to {x}: a test calls only ut_reset_regs, CHECK and {c['unit']['function']['name']}"
            for x in sorted(calls - allowed_fn)]
    if not out:
        out += _compile_test(ws, name, code)
    return out


def _coverage(cov: dict) -> tuple[list[str], list[str]]:
    """CAPA-094 (run WO-F014-SWE4-OBL-20261101-L2, SWE4-05): llvm-cov reports no branch/MC/DC percentage (None) when it
    counts no branch points or decisions (mcp/servers/tests.py: count 0); the report stated a 100% branch goal next to
    'branch None%' and the inspector found the goal neither met nor deviated. Each measure is now stated as met, not met
    (recorded as a finding) or not applicable."""
    m = cov.get("metrics") or {}
    lines, gaps = [], []
    for label, key, what in (("statement/line", "line_pct", "lines"), ("branch", "branch_pct", "branch points"),
                             ("MC/DC", "mcdc_pct", "MC/DC decisions")):
        v = m.get(key)
        if v is None:
            lines.append(f"- {label}: not applicable - llvm-cov counted no {what} in the measured driver code "
                         "(no percentage is defined; nothing is left uncovered)")
        elif float(v) >= 100.0:
            lines.append(f"- {label}: {v}% - goal met")
        else:
            lines.append(f"- {label}: {v}% - goal NOT met (recorded under Findings)")
            gaps.append(f"COVERAGE_GOAL_NOT_MET: {label} {v}% (< 100%)")
    return lines, gaps


ERROR_WORDS = re.compile(r"\b(errors?|fail(s|ed|ure)?|invalid|time-?outs?|reject(s|ed)?|abort(s|ed)?|HAL_ERROR|HAL_TIMEOUT)\b",
                         re.I)


def _kind_gap(kind: str, uc: list[dict]) -> str:
    """CAPA-101 (run WO-F014-SWE4-IWDG-20261101-L4, SWE4-02): 'none declared: error' was read as missing error tests for
    LL accessors that have no error behaviour. A kind without a test is stated NOT COVERED, or not applicable with the
    deterministic reason (no cited requirement states an error behaviour and no error status is returned; no value
    is taken). The inspector judges the statement."""
    fn = uc[0]["unit"]["function"]
    swrs = ", ".join(dict.fromkeys(c["swr"] for c in uc))
    if kind == "error" and not any(ERROR_WORDS.search(c["statement"] or "") for c in uc) and \
            not re.search(r"Status|Error", str(fn.get("returns") or "")):
        return (f"error: not applicable - no requirement of this unit ({swrs}) states an error behaviour and "
                f"{fn['name']} returns {fn.get('returns') or 'void'} without an error status")
    if kind == "boundary" and not _takes_value(fn):
        return f"boundary: not applicable - {fn['name']} takes no value"
    return f"{kind}: NOT COVERED"


def _declared_kinds(ws: Path, ut: str) -> list[str]:
    ck = V._ckpt(ws, PHASE, f"test:{ut}")
    doc = json.loads(ck.read_text()).get("doc") if ck.is_file() else None
    return [k for k in KINDS if k in ((doc or {}).get("kinds") or [])]


def _takes_value(fn: dict) -> bool:
    """A parameter that is not the instance pointer: the value the function writes into a field."""
    return any("*" not in p["type"] for p in fn.get("params") or [])


def _compile_test(ws: Path, name: str, code: str) -> list[str]:
    from ..layer import instance_flags
    from .swe3 import _header

    text = _with_tests(ws, [(name, code)])
    with tempfile.TemporaryDirectory() as td:
        if gtest_mode(ws):  # the GoogleTest harness: C++17 against the pinned gtest headers
            from ..gtest_toolchain import GtestToolchainError, load

            try:
                gt = load()
            except GtestToolchainError as exc:
                return [f"compile: {exc}"]
            t = Path(td) / "t.cpp"
            t.write_text(text)
            argv = ["clang++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsyntax-only", *gt["cxx_flags"],
                    f"-I{_header(ws).parent}", "-isystem", gt["include"], *instance_flags(ws, host=True), str(t)]
        else:
            t = Path(td) / "t.c"
            t.write_text(text)
            argv = ["clang", "-std=c11", "-Wall", "-Wextra", "-Werror", "-fsyntax-only",
                    f"-I{_header(ws).parent}", *instance_flags(ws, host=True), str(t)]
        r = subprocess.run(argv, capture_output=True, text=True)
    errs = [ln.split(" error: ", 1)[1][:160] for ln in r.stderr.splitlines() if " error: " in ln]
    return [f"compile: {e}" for e in errs[:6]] or ([f"compile failed: {r.stderr[:160]}"] if r.returncode else [])


def repair_packet(ws: Path, c: dict, code: str, failure: list[str], model: str) -> dict:
    form = ("Keep the exact TEST(...) name and the @test/@verifies block. " if c.get("uspec") and gtest_mode(ws) else "")
    instr = (form + f"The test of {c['ut']} below FAILED when run against the implementation of "
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


def _req_ids(c: dict) -> list[str]:
    """The requirements a task's test verifies (per-USPEC tasks: the USPEC's oracle requirements, else the unit's)."""
    if c.get("uspec"):
        return list(c["swrs"]) or list(c["unit"]["swrs"]) or ["SWR-000"]
    return [c["swr"]]


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
                                    V.author_call_limit(ws, PHASE, role.max_turns, max_calls), time_budget_s)
    try:
        return _visit_tests(ws, model, budget, findings)
    except V.Continue as c:
        return V.reply(ws, PHASE, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)
    except ValueError as exc:
        return V.reply(ws, PHASE, "FAILED", [str(exc)], budget)


def _visit_tests(ws: Path, model: str, budget: dict, findings: list[str]) -> dict:
    cs = plan_cases(ws) if uspec_mode(ws) else cases(ws)
    missing = [c["ut"] for c in cs if c["unit"] is None]
    if missing:
        return V.reply(ws, PHASE, "FAILED", [f"{u}: its requirement is allocated to no SWE.3 unit" for u in missing],
                       budget)
    routed: dict[str, list[str]] = {}
    for f in V.routable(findings):
        if f.startswith(UPSTREAM_ITEMS) and not re.search(r"\bUT-\d+\b", f):
            # CAPA-093 (run WO-F014-SWE4-IWDG-20261101-L1): a static-analysis/coding-rule gap of the frozen SWE.3 code
            # was routed to every test task, which cannot change that code; ~1.5 h of repair calls without effect.
            continue
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
    res, filed, recs = _run_and_triage(ws, model, budget, recs, rel)
    if res is None:
        return V.reply(ws, PHASE, "FAILED", filed, budget)
    open_gaps: list[str] = []
    if res["status"] == "PASS" and uspec_mode(ws) and gtest_mode(ws):
        # owner 2026-11-03 (D/E): coverage closure tasks for the gaps the blocking coverage gate names
        res, more, recs, open_gaps, closure_defects = _closure(ws, model, budget, recs, rel)
        filed += more
    else:
        closure_defects = []
    S.record(ws, "SWE.4/tests-assembly.json", {"at": utc_now(), "tests": [c["ut"] for c, _n, _r in recs],
                                               "defects": filed + closure_defects, "run_unit": res.get("summary"),
                                               "open_coverage_gaps": open_gaps})
    if res["status"] != "PASS":
        return V.reply(ws, PHASE, "FAILED", [f"run_unit: {i}" for i in res["issues"][:10]] +
                       [f"defect filed: {x}" for x in filed + closure_defects], budget)
    if filed or open_gaps:  # below the order's minimum (or a failing-test CODE defect): rework / upstream loop
        return V.reply(ws, PHASE, "FAILED", [f"defect filed: {x}" for x in filed + closure_defects] + open_gaps[:20],
                       budget)
    return V.reply(ws, PHASE, "PASS", [], budget, artifacts=[rel])


def _run_and_triage(ws: Path, model: str, budget: dict, recs: list, rel: str):
    """Assemble, run_unit, and triage each failing test (ADR-0008 L4/L13: a correct failing test files a CODE
    defect; a wrong one is corrected and declared). Returns (run result or None when the run did not execute,
    filed defect ids or the run issues, the current records)."""
    from ..inspection import defects
    from . import tools as T

    V.write_scoped(ws, {rel: _with_tests(ws, [(n, r["doc"]["code"]) for _c, n, r in recs])}, "swe4_test_author")
    res = T.call(ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", PHASE)
    fails = _failures(res) if res["status"] != "PASS" else {}
    if res["status"] != "PASS" and not fails:
        return None, [f"run_unit: {i}" for i in res["issues"][:10]], recs
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
                                            summary=f"{c['ut']}{' (' + c['uspec'] + ')' if c.get('uspec') else ''} "
                                                    f"fails: {d['reason']}"[:400], requirement_ids=_req_ids(c),
                                            test_files=[rel], evidence_refs=[f"run_unit:{res.get('summary', '')}"[:120]],
                                            requirement_quote=c["statement"][:300])["id"])
            except defects.DefectError as exc:
                filed.append(f"REFUSED:{exc}")
        elif validate_test(ws, {"code": d["code"], "kinds": rec["doc"].get("kinds")}, c) == []:
            try:  # a test corrected after it failed is declared, never silently bent (ADR-0008 L4)
                defects.report(ws, detected_phase=PHASE, reported_by="swe4-author", kind="TEST",
                               summary=f"{c['ut']} corrected: {d['reason']}"[:400], requirement_ids=_req_ids(c),
                               test_files=[rel], evidence_refs=[], requirement_quote=c["statement"][:300])
            except defects.DefectError as exc:
                filed.append(f"REFUSED:{exc}")
                continue
            ck = V._ckpt(ws, PHASE, f"test:{c['ut']}")
            st = json.loads(ck.read_text())
            st["doc"] = {"code": d["code"], "kinds": rec["doc"].get("kinds")}
            st["declared_correction"] = d["reason"][:300]
            ck.write_text(json.dumps(st, indent=1))
    if fails:
        recs = [(c, n, json.loads(V._ckpt(ws, PHASE, f"test:{c['ut']}").read_text())) for c, n, _r in recs]
        V.write_scoped(ws, {rel: _with_tests(ws, [(n, r["doc"]["code"]) for _c, n, r in recs])}, "swe4_test_author")
        res = T.call(ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", PHASE)
    return res, filed, recs


# ---- owner 2026-11-03 (D/E): structural coverage closure ---------------------------------------------------------
CLOSURE_SCHEMA = {"type": "object", "additionalProperties": False,
                  "required": ["verdict", "reason", "code", "verifies", "kinds"],
                  "properties": {"verdict": {"type": "string", "enum": ["test", "unreachable"]},
                                 "reason": {"type": "string", "minLength": 20},
                                 "code": {"type": "string"},
                                 "verifies": {"type": "array", "maxItems": 4,
                                              "items": {"type": "string", "pattern": "^USPEC-[A-Z]+-[0-9]{2,}-[0-9]{2,}$"}},
                                 "kinds": {"type": "array", "maxItems": 4, "uniqueItems": True,
                                           "items": {"type": "string", "enum": list(KINDS)}}}}
CLOSURE_ROUNDS = 2  # a gap still uncovered after its second closure test is a CODE defect (bounded loop)


def _blocking_gaps(ws: Path, cov: dict) -> list[dict]:
    from ..inspection import coverage_gate as CG

    if cov.get("status") != "PASS":
        return []
    ev = CG.evaluate(ws, cov)
    if ev["target_met"]:
        return []
    # owner rule 2026-11-03: closure works toward the order's TARGET for every required measure not yet at it
    kinds = {r["key"] for r in ev["rows"] if r["status"] in ("BELOW_TARGET", "BELOW_MINIMUM")}
    return [g for g in coverage_gaps(ws, cov) if g["kind"] in kinds]


def _cov_point(cov: dict) -> tuple:
    m = cov.get("metrics") or {}
    return tuple(m.get(k) or 0.0 for k in ("line_pct", "branch_pct", "mcdc_pct"))


def coverage_gaps(ws: Path, cov: dict) -> list[dict]:
    """The uncovered items an llvm_coverage result names (its content-addressed gap artifact)."""
    m = cov.get("metrics") or {}
    if "uncovered" in m:  # an in-memory result
        return list(m["uncovered"])
    ref = m.get("uncovered_artifact")
    if not ref:
        return []
    from ..inspection.swtrace import _raw

    p = _raw(Path(ws), ref)
    return json.loads(p.read_text())["gaps"] if p is not None else []


def closure_targets(gaps: list[dict]) -> list[dict]:
    """One closure task per uncovered decision (branch outcome / MC/DC condition); uncovered lines join the
    decisions of their function, and a function with uncovered lines but no uncovered decision is one task."""
    by: dict[str, list[dict]] = {}
    for g in gaps:
        by.setdefault(g["function"] or f"{g['file']}:?", []).append(g)
    out = []
    for gs in by.values():
        lines = sorted({g["line"] for g in gs if g["kind"] == "line"})
        dec = [g for g in gs if g["kind"] in ("branch", "mcdc")]
        for d in dec:
            out.append({**d, "function": d["function"], "lines": lines})
        if not dec:
            g0 = gs[0]
            out.append({**g0, "kind": "line", "text": " / ".join(g["text"] for g in gs)[:160], "lines": lines,
                        "missing": f"line(s) {', '.join(map(str, lines))} never executed"})
    return out


def _closure_case(ws: Path, gap: dict, ut: str) -> dict:
    """The task of one gap: the decision, its unit (by function) and that unit's USPEC items and requirements - the
    oracle; never the code around the decision."""
    from ..assurance.register_contract import _requirements
    from ..inspection import uspec_plan as P
    from .swe3 import units

    plan = P.current(ws)
    tasks = [t for t in plan["tasks"] if gap["function"] in t["functions"]]
    unit = next((u for u in units(ws) if tasks and u["id"] == tasks[0]["unit"]), None)
    swrs = sorted({r for t in tasks for r in t["swrs"]})
    reqs = _requirements(ws)
    eff = json.loads((Path(ws) / "workproducts/SWE.1/register_effects.json").read_text())["effects"]
    return {"ut": ut, "closure": True, "gap": gap, "unit": unit, "uspec": None, "uspecs": [t["uspec"] for t in tasks],
            "uspec_behaviour": {t["uspec"]: t["behaviour"] for t in tasks}, "swrs": swrs, "swr": ", ".join(swrs) or "-",
            "statement": " ".join(reqs.get(r, "") for r in swrs), "statements": {r: reqs.get(r, "") for r in swrs},
            "effects": [e for e in eff if e["swr"] in swrs], "plan": {"constraints_verified_at_swe6": []},
            "behaviour": f"coverage closure of {gap['file']}:{gap['line']} `{gap['text']}` ({gap['missing']})"}


def closure_packet(ws: Path, c: dict, model: str, findings=None, previous=None) -> dict:
    from ..inspection.uspec_plan import suite_name, ut_name
    from .swe3 import _defines, _sig

    u, g = c["unit"], c["gap"]
    suite, name = suite_name(u["id"]), ut_name(c["ut"])
    lines = f" (lines {', '.join(map(str, g['lines']))} of {g['function']} are not executed either)" if g.get(
        "lines") and g["kind"] != "line" else ""
    instr = (f"Coverage closure for unit {u['id']} (`{_sig(u['function'])}`). The requirement-based tests leave this "
             f"part of the driver code uncovered: {g['file']}:{g['line']} in {g['function']}, decision `{g['text']}` - "
             f"{g['missing']}{lines}. You see only the decision, never the code around it. If a behaviour stated by "
             "the USPEC items or requirements below takes this outcome, answer verdict test with ONE GoogleTest test "
             f"`TEST({suite}, {name})` that drives the unit's API into that behaviour and checks the result the USPEC "
             "item and its requirements state (EXPECT_EQ/EXPECT_NE/EXPECT_TRUE/EXPECT_FALSE; expected values ONLY from "
             f"them), preceded by '/** @test {c['ut']} @verifies <the USPEC ids of {u['id']} whose behaviour it "
             "checks> */'; verifies lists the same USPEC ids. If NO requirement or USPEC item of the unit states a "
             "behaviour that reaches this outcome (code without a requirement behind it), answer verdict unreachable, "
             "code '' and verifies [] - the factory files a CODE defect against SWE.3; never invent a requirement or a "
             f"test without an oracle. Call ut_reset_regs() first; preset registers "
             f"{_preset_rule(ws, u['function']['fields'])}. Use only the harness, {u['function']['name']}, the "
             "register block, the generated defines and the GoogleTest macros - no #include, #define, fixture or "
             "other function. kinds: the kinds of check the test contains (positive/negative/boundary/error).")
    oracle = (f"Unit {u['id']} ({u['function']['name']}) - its specification items:\n" +
              "".join(f"{k}: {v}\n" for k, v in c["uspec_behaviour"].items()) +
              "".join(f"{r}: {t}\n" for r, t in c["statements"].items()) +
              "".join(f"case {e['case']} ({e['swr']}): {e.get('register', '')}.{e.get('field', '')} op {e['op']}"
                      + RC.value_text(e) + "\n" for e in c["effects"]))
    defs = _defines(ws, u["function"]["fields"])
    return S.packet(phase=PHASE, task=f"test:{c['ut']}", role="swe4-author", instructions=instr, sources=[],
                    artifacts=[{"path": "oracle", "text": oracle, "sha256": sha256_bytes(oracle.encode())},
                               {"path": "generated-defines", "text": defs, "sha256": sha256_bytes(defs.encode())}],
                    criteria=["the decision outcome is reached through the unit's API", "expected values from the oracle",
                              "unreachable only when no USPEC/requirement behaviour reaches it"],
                    output_schema=CLOSURE_SCHEMA, model=model, findings=findings, previous=previous,
                    output_reserve=3072)


def validate_closure(ws: Path, doc: dict, c: dict) -> list[str]:
    if doc["verdict"] == "unreachable":
        return [] if not doc["code"].strip() and not doc["verifies"] else [
            "verdict unreachable takes code '' and verifies []"]
    if not doc["verifies"]:
        return ["verdict test needs verifies: the USPEC ids whose behaviour the test checks"]
    bad = [v for v in doc["verifies"] if v not in c["uspecs"]]
    if bad:
        return [f"{v} is not a USPEC item of {c['unit']['id']} ({', '.join(c['uspecs'])})" for v in bad]
    return validate_gtest(ws, {"code": doc["code"], "kinds": doc["kinds"] or ["positive"]},
                          {**c, "uspec": doc["verifies"][0]}, verifies=list(doc["verifies"]), closure=True)


def _closure_defect(ws: Path, c: dict, why: str) -> str:
    from ..inspection import defects

    g, u = c["gap"], c["unit"]
    swrs = c["swrs"] or (u["swrs"] if u else [])
    try:
        return defects.report(ws, detected_phase=PHASE, reported_by="swe4-author", kind="CODE",
                              summary=(f"COVERAGE_UNREACHABLE {g['file']}:{g['line']} in {g['function']}: `{g['text']}` "
                                       f"({g['missing']}) - {why}")[:400],
                              requirement_ids=list(swrs) or sorted(_known_requirements(ws))[:1],
                              test_files=[str(_harness(ws).relative_to(ws))],
                              evidence_refs=[f"{g['file']}:{g['line']}", f"llvm_coverage:{g['id']}"],
                              requirement_quote=V.requirement_quote(ws, list(swrs)))["id"]
    except defects.DefectError as exc:
        return f"REFUSED:{exc}"


def _known_requirements(ws: Path) -> list[str]:
    from ..assurance.register_contract import _requirements

    return list(_requirements(ws))


def _closure(ws: Path, model: str, budget: dict, recs: list, rel: str):
    """Bounded closure rounds: llvm_coverage -> one task per uncovered decision -> tests (or CODE defects for gaps no
    requirement/USPEC reaches) -> run. Returns (run result, defects filed, records, open gap findings)."""
    from ..inspection import uspec_plan as P
    from . import tools as T

    res, filed, tried, hard = None, [], {}, []
    points, stopped, prev = [], "TARGET_MET", None
    for _round in range(CLOSURE_ROUNDS + 1):
        cov = T.call(ws, "forge-tests-mcp", "llvm_coverage", {}, "swe4-author", PHASE)
        point = _cov_point(cov)
        points.append(point)
        gaps = _blocking_gaps(ws, cov)
        if not gaps:
            stopped = "TARGET_MET" if cov.get("status") == "PASS" else "NOT_MEASURED"
            break
        if prev is not None and not any(a > b for a, b in zip(point, prev, strict=True)):
            # owner rule 2026-11-03: a closure round that adds no coverage ends closure
            stopped = "NO_PROGRESS"
            break
        prev = point
        stopped = "EXHAUSTED"
        plan = P.current(ws)
        used = [int(t["ut"][3:]) for t in plan["tasks"] + plan.get("closure", []) + plan.get("closure_unreachable", [])]
        nxt = max(used, default=0) + 1
        new = []
        for g in closure_targets(gaps):
            key = g["id"]
            if tried.get(key, 0) > CLOSURE_ROUNDS:
                continue
            if g["function"] is None or not any(g["function"] in t["functions"] for t in plan["tasks"]):
                filed.append(_closure_defect(ws, {"gap": g, "unit": None, "swrs": []},
                                             "the code belongs to no unit of the frozen SWE.3 unit specification"))
                tried[key] = CLOSURE_ROUNDS + 1
                continue
            if tried.get(key, 0) > CLOSURE_ROUNDS:  # already filed as a CODE defect in this visit
                continue
            if tried.get(key, 0) == CLOSURE_ROUNDS:
                filed.append(_closure_defect(ws, _closure_case(ws, g, "UT-000"), f"still uncovered after "
                                             f"{CLOSURE_ROUNDS} requirement-based closure tests"))
                tried[key] = CLOSURE_ROUNDS + 1
                continue
            tried[key] = tried.get(key, 0) + 1
            if nxt > P.MAX_UT:
                return res or cov, filed, recs, ["SWE4_UT_ID_SPACE_EXHAUSTED"]
            c = _closure_case(ws, g, f"UT-{nxt:03d}")
            nxt += 1
            rec = V.run_task(ws, PHASE, f"test:{c['ut']}", lambda fi, pr, c=c: closure_packet(ws, c, model, fi, pr),
                             lambda d, c=c: validate_closure(ws, d, c), budget)
            if rec["status"] != "VALID":  # blocked closure task: recorded, closure ends here
                hard_note = [f"{rec['task']}: {e}" for e in rec["errors"][:4]]
                plan.setdefault("closure_blocked", []).append({"ut": c["ut"], "gap": g, "errors": hard_note})
                V.write_scoped(ws, P.files(plan), "swe4_test_author")
                stopped = "BLOCKED"
                break
            d = rec["doc"]
            if d["verdict"] == "unreachable":
                fid = _closure_defect(ws, c, f"no requirement or USPEC of {c['unit']['id']} reaches it: {d['reason']}")
                filed.append(fid)
                plan.setdefault("closure_unreachable", []).append({"ut": c["ut"], "gap": g, "defect": fid,
                                                                   "reason": d["reason"][:300]})
                tried[key] = CLOSURE_ROUNDS + 1
                continue
            plan.setdefault("closure", []).append({
                "ut": c["ut"], "kind": "closure", "uspec": d["verifies"][0], "verifies": d["verifies"],
                "unit": c["unit"]["id"], "functions": [c["unit"]["function"]["name"]], "behaviour":
                f"coverage closure of {g['file']}:{g['line']} `{g['text']}` ({g['missing']})", "swrs": c["swrs"],
                "constraints_verified_at_swe6": [], "gap": g})
            name = P.ut_name(c["ut"])
            new.append(({**c, "uspec": d["verifies"][0], "verifies": d["verifies"]}, name, {**rec, "doc": {"code": d["code"],
                                                                                "kinds": d["kinds"] or ["positive"]}}))
            V.write_scoped(ws, P.files(plan), "swe4_test_author")
        V.write_scoped(ws, P.files(plan), "swe4_test_author")
        if new:
            recs = recs + new
            res, more, recs = _run_and_triage(ws, model, budget, recs, rel)
            if res is None:
                return {"status": "FAIL", "issues": more}, filed + more, recs, [], []
            if res["status"] != "PASS" or more:  # a failing closure test: the normal triage/upstream path
                return res, more, recs, [], filed
        if stopped == "BLOCKED" or not new:
            stopped = stopped if stopped == "BLOCKED" else "EXHAUSTED"
            break
    final = T.call(ws, "forge-tests-mcp", "llvm_coverage", {}, "swe4-author", PHASE)  # newest evidence for the gate
    from ..inspection import coverage_gate as CG

    ev = CG.evaluate(ws, final)
    plan = P.current(ws)
    plan["closure_status"] = {"stopped": stopped, "rounds": len(points), "coverage_by_round": [list(p) for p in points],
                              "final": list(_cov_point(final)), "target_met": ev["target_met"],
                              "shortfall": ev["shortfall"], "below_minimum": ev["findings"], "code_defects": filed}
    V.write_scoped(ws, P.files(plan), "swe4_test_author")
    # owner rule 2026-11-03: no further progress -> PASS when every measure is at or above the order's minimum; the
    # CODE defects for unreachable code stay recorded (SWE.3 / owner), the shortfall is reported, never claimed met
    return res or {"status": "PASS", "summary": "no closure test needed", "issues": []}, hard, recs, ev["findings"], \
        filed


def _missed_reasons(ws: Path, gate: dict) -> list[str]:
    """Why a target was missed (owner rule 2026-11-03): CODE defects for unreachable code, closure tasks that could not
    reach a decision, blocked closure tasks, and how closure ended - from the plan record, never invented."""
    from ..inspection import uspec_plan as P

    plan = P.load(ws) or {}
    st = plan.get("closure_status") or {}
    out = [f"{x}" for x in gate.get("shortfall") or []]
    out += [f"{u['gap']['file']}:{u['gap']['line']} `{u['gap']['text']}` ({u['gap']['missing']}): unreachable by any "
            f"requirement/USPEC - CODE defect {u['defect']}: {u['reason']}" for u in plan.get("closure_unreachable", [])]
    out += [f"{b['gap']['file']}:{b['gap']['line']} `{b['gap']['text']}`: closure task {b['ut']} blocked: "
            f"{'; '.join(b['errors'])[:200]}" for b in plan.get("closure_blocked", [])]
    if st:
        out.append(f"closure ended: {st['stopped']} after {st['rounds']} round(s); CODE defects "
                   f"{', '.join(st.get('code_defects') or []) or 'none'}")
    return out if (gate.get("shortfall") or gate.get("findings")) else []


def _per_test_results(ws: Path) -> dict[str, str]:
    """UT id -> PASS/FAIL from the content-addressed output of the latest run_unit (as Matrix 4 reads it)."""
    from ..inspection.swtrace import check_results, latest_run

    run = latest_run(ws, "run_unit")
    return check_results(run["raw"]) if run else {}


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
    kinds = {c["ut"]: _declared_kinds(ws, c["ut"]) for c in cs}
    results = _per_test_results(ws)
    from ..layer import ll_instance

    inst = ll_instance(ws)
    store = ("a plain RAM register array" if inst is None else f"the RAM {inst['type_name']} instance "
             f"{inst['host_object']} of the pinned device header {inst['device_header']}, passed as {inst['macro']}")
    from ..gtest_toolchain import VERSION as GTEST

    how = (f"Host build of the requirement-based GoogleTest/GoogleMock {GTEST} unit tests (clang++ 19, one TEST per "
           "USPEC item) against the header-only LL driver" if gtest_mode(ws) else
           "Host clang build of the self-checking unit tests against the header-only LL driver")
    md = ["# Unit verification report", "",
          "## Measures, environment, entry/exit criteria and regression", "",
          f"{how} on {store} (host evidence, not target). Entry: the SWE.3 baseline is frozen. Exit: every UT PASS and the "
          "coverage goal met or a deviation recorded. Regression: the full suite is re-run on every change.", "",
          "## Test cases", ""]
    if uspec_mode(ws):  # owner 2026-11-03: one test per USPEC item (UT ids assigned by SWE.4, unit_test_plan.md)
        md += ["One requirement-based test per USPEC item of the frozen SWE.3 unit specification "
               "(workproducts/SWE.4/unit_test_plan.md).", "",
               "| UT id | USPEC | function | SWR ids | kind | result |", "| --- | --- | --- | --- | --- | --- |"]
        md += [f"| {c['ut']} | {c['uspec']} | {c['unit']['function']['name']} | {c['swr']} | "
               f"{', '.join(kinds[c['ut']]) or 'not declared'} | {results.get(c['ut'], run['status'] + ' (suite)')} |"
               for c in cs]
    else:
        md += ["| UT id | function | SWR ids | kind | result |", "| --- | --- | --- | --- | --- |"]
        md += [f"| {c['ut']} | {c['unit']['function']['name']} | {c['swr']} | "
               f"{', '.join(kinds[c['ut']]) or 'not declared'} | {run['status']} (suite) |" for c in cs]
    md += ["", "## Test design per unit", "",
           "Kinds are declared per test by the test author and checked deterministically: positive is required, and "
           "boundary (field minimum and maximum, further calls) is required for every function that takes a value. "
           "Error tests are written only where a requirement states an error behaviour.", ""]
    for uid in dict.fromkeys(c["unit"]["id"] for c in cs):
        got = sorted({k for c in cs if c["unit"]["id"] == uid for k in kinds[c["ut"]]}, key=KINDS.index)
        none = [k for k in KINDS if k not in got]
        uc = [c for c in cs if c["unit"]["id"] == uid]
        md.append(f"- {uid}: {', '.join(got) or 'none'}" + "".join(f"; {_kind_gap(k, uc)}" for k in none))
    md += ["", "## Mock fidelity", "", ("Plain RAM register array" if inst is None else
                                         f"Plain RAM {inst['type_name']} instance") + ": no write-1-to-clear, read-only "
           "or hardware side effects; flags are preset by the test. Limitation: hardware update latency (e.g. PVU/RVU) "
           "is not modelled.",
           "", "## Static analysis", ""]
    md += [f"- {r['op']} ({r['phase']}): status {r['result']['status']}; \"{r['result']['summary']}\"; issues "
           f"{r['result']['issues']}" for r in sa[-2:]] or ["- not run"]
    dev = ws / DEVIATIONS
    md += ["", f"Coding-rule record of the frozen SWE.3 code ({DEVIATIONS}), quoted as recorded:", ""]
    md += ([f"> {ln}" for ln in dev.read_text().splitlines() if ln.strip()][:20] if dev.is_file() else ["> missing"])
    open_gaps = sa and any(r["result"]["status"] != "PASS" for r in sa[-2:])
    md += ["", "Review status: " + ("the static-analysis findings above are OPEN coding-rule gaps of the SWE.3 code; "
                                    "SWE.4 cannot change that code and approves no deviation (deviation approval is the "
                                    "owner's)." if open_gaps else "no open static-analysis finding.")]
    cov_lines, cov_gaps = _coverage(cov)
    from ..inspection import coverage_gate as CG

    gate = CG.evaluate(ws, cov) if CG.enabled(ws) else None
    if gate is not None:  # owner 2026-11-03 (C): blocking by purpose; the gate's findings replace the reported goal
        cov_lines, cov_gaps = CG.report_lines(gate), gate["findings"]
        from .. import quality as Q

        structural = {r["key"]: r["value"] for r in gate["rows"]}
        cov_lines += [""] + Q.render(ws, Q.achieved_rows(ws, structural), _missed_reasons(ws, gate))
    md += ["", "## Coverage", "", ("Structural coverage (LLVM source-based, line/branch/MC/DC) of the driver code. " if gate
           else "Goal: 100% statement (line) coverage of the driver code, and 100% branch and MC/DC "
           "coverage where the code has branch points or decisions. ") + "Reported exactly as the tool reported it: status "
           f"{cov['status']}; \"{cov['summary']}\"; metrics {json.dumps(cov.get('metrics') or {}, sort_keys=True)}.", "",
           *cov_lines, "", "## Results", "", f"run_unit: status {run['status']}; \"{run['summary']}\". validate_trace: status "
           f"{tr['status']}; \"{tr.get('summary', '')}\".", "", "## Findings", ""]
    findings = [*run.get("issues", [])[:10], *tr.get("issues", [])[:10], *cov_gaps]
    md += [f"- {f}" for f in findings] or ["none"]
    V.write_scoped(ws, {"workproducts/SWE.4/unit_verification_report.md": "\n".join(md) + "\n"}, "swe4_author")
    status = "PASS" if run["status"] == "PASS" and not (gate and gate["status"] != "PASS") else "FAILED"
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
