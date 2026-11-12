"""Owner decision 2026-11-03 (V-model): SWE.4 unit tests are derived from and traced to the SWE.3 unit specification.

SWE.4 creates ONE test task per USPEC item of each frozen SWE.3 unit (workproducts/SWE.3/unit_specifications.md, frozen
with the SWE.3 baseline) and assigns the UT ids itself, in unit/USPEC order. "Every USPEC has a passing test" holds by
construction: the plan names a UT id for every USPEC; Matrix 4 (`UT:SPEC_NOT_VERIFIED`) stays the safety net.

SWE.1 allocates only the SWR -> SWE.6 qualification tests. A frozen SWE.1 baseline of an older work order may still
carry SWE.1 UT rows (requirements_to_tests.csv `SWR,UT-nnn,software/tests/unit/...`): they are recorded in the plan as
SUPERSEDED (never reinterpreted as SWE.4 trace links) and SWE.4 numbers its UT ids after the highest of them, so no UT id
of the frozen SWE.1 baseline names a different SWE.4 test.

Oracle: a task's expected values come from the requirement side the USPEC traces to (the SWR text and its register-
effect cases) and the USPEC behaviour; component constraints (resource budgets, initial-state invariants, simulation
performance) are verified at SWE.6 and are not unit-test oracles. The implementation is never part of a task.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from ..common import sha256_bytes

PLAN = "workproducts/SWE.4/unit_test_plan.json"
PLAN_MD = "workproducts/SWE.4/unit_test_plan.md"
TRACE = "traceability/requirements_to_tests.csv"
SCHEMA = "forge-c/swe4-unit-test-plan/1"
MAX_UT = 999  # UT-nnn: three digits (swtrace and the result parsers read exactly three)
UT_RX = re.compile(r"^UT-(\d{3})$")


class PlanError(ValueError):
    pass


# owner 2026-11-03: the SWE.4 test kind follows from the USPEC item (nominal, negative, corner/boundary, error)
ERROR_RX = re.compile(r"\b(HAL_ERROR|HAL_TIMEOUT|HAL_BUSY|error status|returns? (?:an )?error|time-?outs?|timed out|"
                      r"rejects?|rejected|fails?)\b", re.I)
BOUNDARY_RX = re.compile(r"\b(range|width|maximum|minimum|above|exceed\w*|confin\w*|truncat\w*|out[- ]of[- ]range|"
                         r"overflow\w*|wider|beyond|upper|lower|limit|low(?:er)? \d+ bits|field bits|(?:\d+)-bit)\b", re.I)
NEGATIVE_RX = re.compile(r"\b(unchanged|preserv\w*|leav\w* .{0,40}unchanged|not (?:change|modif|writ|read|set|clear)\w*|"
                         r"never (?:chang|modif|writ|set|clear)\w*|no other|other bits|only the named|returns? 0U?|"
                         r"0U when|else 0U|"
                         r"clear(?:ed)? flag|idempot\w*|repeated|wrong (?:state|order)|NULL|invalid|ignor\w*|"
                         r"does not|is not|must not|shall not)\b", re.I)


def uspec_kind(text: str) -> str:
    """The test kind a USPEC item asks for: error > boundary > negative > positive (first match wins)."""
    for kind, rx in (("error", ERROR_RX), ("boundary", BOUNDARY_RX), ("negative", NEGATIVE_RX)):
        if rx.search(text or ""):
            return kind
    return "positive"


def legacy_unit_rows(ws: Path) -> list[dict]:
    """SWE.1 UT allocation rows of an older frozen SWE.1 baseline (none for SWE.1 baselines made after 2026-11-03)."""
    p = Path(ws) / TRACE
    if not p.is_file():
        return []
    rows = list(csv.DictReader(io.StringIO(p.read_text(errors="replace"))))
    return [{"requirement_id": (r.get("requirement_id") or "").strip(), "test_id": (r.get("test_id") or "").strip(),
             "test_file": (r.get("test_file") or "").strip()} for r in rows
            if UT_RX.match((r.get("test_id") or "").strip())
            and (r.get("test_file") or "").strip().startswith("software/tests/unit/")]


def _trace_sha(ws: Path) -> str | None:
    p = Path(ws) / TRACE
    return sha256_bytes(p.read_bytes()) if p.is_file() else None


def ut_name(ut: str) -> str:
    """GoogleTest test name of a UT id (UT-005 -> UT_005)."""
    return ut.replace("-", "_")


def suite_name(unit: str) -> str:
    """GoogleTest test-suite name of a unit (SWU-LL-05 -> SWU_LL_05)."""
    return unit.replace("-", "_")


def build(ws: Path) -> dict:
    from .swtrace import UNITS_MD, component_constraints, parse_units, swr_texts

    ws = Path(ws)
    md = ws / UNITS_MD
    if not md.is_file():
        raise PlanError(f"SWE4_NO_FROZEN_UNIT_SPECIFICATION:{UNITS_MD}")
    text = md.read_text(errors="replace")
    units = [u for u in parse_units(text) if u["specs"]]
    if not units:
        raise PlanError("SWE4_NO_USPEC_ITEMS (the frozen SWE.3 unit specification lists no USPEC item)")
    legacy = legacy_unit_rows(ws)
    first = 1 + max((int(UT_RX.match(r["test_id"]).group(1)) for r in legacy), default=0)
    constraints = component_constraints(ws)
    texts = swr_texts(ws)
    tasks, n = [], first
    for u in units:
        for s in u["specs"]:
            if n > MAX_UT:
                raise PlanError(f"SWE4_UT_ID_SPACE_EXHAUSTED (first {first}, {sum(len(x['specs']) for x in units)} "
                                "USPEC items)")
            oracle = [r for r in s["swrs"] if r not in constraints]
            tasks.append({"ut": f"UT-{n:03d}", "kind": "requirement", "test_kind": uspec_kind(s["text"]),
                          "uspec": s["id"], "unit": u["id"],
                          "functions": u["functions"], "behaviour": s["text"], "swrs": oracle,
                          "constraints_verified_at_swe6": sorted(r for r in s["swrs"] if r in constraints),
                          "unknown_swrs": sorted(r for r in oracle if r not in texts)})
            n += 1
    return {"schema": SCHEMA, "swe1_trace": "legacy_unit_allocation" if legacy else "qualification_only",
            "superseded_swe1_unit_rows": legacy, "first_ut": first, "swe1_trace_sha256": _trace_sha(ws),
            "unit_specification": {"path": UNITS_MD, "sha256": sha256_bytes(text.encode())},
            "tasks": tasks, "closure": []}


def load(ws: Path) -> dict | None:
    p = Path(ws) / PLAN
    return json.loads(p.read_text()) if p.is_file() else None


def current(ws: Path) -> dict:
    """The plan of this SWE.4 visit: the written plan while the frozen unit specification and SWE.1 trace it was made
    from are unchanged (closure tasks kept), else a new plan."""
    from .swtrace import UNITS_MD

    old = load(ws)
    md = Path(ws) / UNITS_MD
    if old and md.is_file() and old.get("unit_specification", {}).get("sha256") == sha256_bytes(md.read_bytes()) \
            and old.get("swe1_trace_sha256") == _trace_sha(ws):
        return old
    return build(ws)


def render_md(plan: dict) -> str:
    lines = ["# SWE.4 unit test plan", "",
             "Generated deterministically from the frozen SWE.3 unit specification "
             f"({plan['unit_specification']['path']}, sha256 {plan['unit_specification']['sha256'][:16]}...): one "
             "requirement-based unit test per USPEC item; UT ids are assigned by SWE.4.", "",
             f"SWE.1 trace: {plan['swe1_trace']}" + (
                 f" - {len(plan['superseded_swe1_unit_rows'])} SWE.1 UT row(s) of the frozen SWE.1 baseline are "
                 f"superseded (not SWE.4 trace links); SWE.4 UT ids start at UT-{plan['first_ut']:03d}."
                 if plan["superseded_swe1_unit_rows"] else "."), "",
             "| UT id | kind | test kind | USPEC | unit | function | oracle SWR ids | verified at SWE.6 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for t in plan["tasks"] + plan.get("closure", []):
        lines.append(f"| {t['ut']} | {t['kind']} | {t.get('test_kind', '-')} | {t['uspec']} | {t['unit']} | "
                     f"{', '.join(t['functions']) or '-'} | "
                     f"{', '.join(t['swrs']) or '-'} | {', '.join(t.get('constraints_verified_at_swe6') or []) or '-'} |")
    return "\n".join(lines) + "\n"


def files(plan: dict) -> dict[str, str]:
    return {PLAN: json.dumps(plan, indent=1, sort_keys=True) + "\n", PLAN_MD: render_md(plan)}


def write(ws: Path, plan: dict) -> None:
    for rel, text in files(plan).items():
        p = Path(ws) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def missing_tests(ws: Path, tagged: list[dict]) -> list[str]:
    """Matrix 4 safety net: a planned UT id without a tagged test, or a tagged test that does not verify its USPEC."""
    plan = load(ws)
    if not plan:
        return []
    by = {t["test"]: set(t["verifies"]) for t in tagged}
    out = []
    for t in plan["tasks"] + plan.get("closure", []):
        if t["ut"] not in by:
            out.append(f"UT:PLANNED_TEST_MISSING:{t['ut']} (plan: verifies {t['uspec']})")
        elif t["uspec"] not in by[t["ut"]]:
            out.append(f"UT:PLANNED_TRACE_MISSING:{t['ut']} (@verifies must name {t['uspec']})")
    return out
