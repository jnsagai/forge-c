"""LRTX-T022 (P4, LL layer): SWE.6 software verification as structured tasks for the local profile.

The generated Robot suite (one test case per SWE.1 requirement, `robot_scaffold`) gets its bodies from two sources:
- **Budget requirements** (flash, static RAM, stack): their ForgeTarget keyword with the bytes the requirement
  states, rendered deterministically.
- **Declared simulation performance allocations**: run the bound instrumented target test and independent
  measurement keyword; never ask the model to invent an instruction/time TCHECK.
- **Every other requirement**: a TCHECK in a target scenario program written by the model. There is one task per
  register group of the structured SWE.1, plus the cross-cutting group. Each requirement's check number is its SWR
  number, so the suite line `Target Check Should Pass <n>` is fixed. A task returns a default-scenario program and,
  when some requirement needs the update flags held, a never_ready program.

The implementation code is not shown. Each program is validated deterministically:
- structure (includes, mailbox, TEST_BEGIN/END);
- exactly the assigned TCHECK numbers;
- only the interface functions, generated defines and the register block.

run_robot then runs through the role-granted operation. Failures are triaged like SWE.4/SWE.5 (ADR-0008): a
corrected scenario is declared TEST, a correct one files a CODE defect. The report ("author" visit) is
deterministic from the tool results.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import structured as S
from . import visit as V

PHASE = "SWE.6"
SCN_SCHEMA = {"type": "object", "additionalProperties": False,
              "required": ["default_code", "never_ready_code", "never_ready_swrs"],
              "properties": {"default_code": {"type": "string"}, "never_ready_code": {"type": "string"},
                             "never_ready_swrs": {"type": "array", "items": {"type": "string",
                                                                             "pattern": "^SWR-[0-9]{3}$"}}}}
TRIAGE_SCHEMA = {"type": "object", "additionalProperties": False,
                 "required": ["verdict", "reason", "default_code", "never_ready_code", "never_ready_swrs"],
                 "properties": {"verdict": {"type": "string", "enum": ["test_wrong", "code_defect"]},
                                "reason": {"type": "string", "minLength": 20}, **SCN_SCHEMA["properties"]}}
BUDGET = [(re.compile(r"\bflash\b", re.I), "Driver Flash Size Should Be At Most"),
          (re.compile(r"\bstatic RAM\b", re.I), "Driver Static RAM Should Be At Most"),
          (re.compile(r"\bstack\b", re.I), "Driver Stack Should Be At Most")]


def _suite(ws: Path) -> str:
    from ..workflow.robot_scaffold import suite

    return suite(ws)


def plan(ws: Path) -> dict:
    """Requirement -> scenario topic (register group of SWE.1) or budget keyword; check number = SWR number."""
    from ..assurance.register_contract import _requirements
    from ..inspection.swtrace import BUDGET_RX
    from ..simulation_performance import selected

    ws = Path(ws)
    reqs = _requirements(ws)
    amap = json.loads((ws / ".forge-run/lrtx/SWE.1/assembly.json").read_text())["swr"]
    topics: dict[str, list[str]] = {}
    budgets: dict[str, str] = {}
    performance = selected(ws)
    measured_statements = set()
    if performance:
        from .swe1 import budget_requirements, system_name

        measured_statements = {r["statement"] for r in budget_requirements(ws, system_name(ws))
                               if r["upstream"] == "WO-SIMULATION-PERFORMANCE"}
    for s, text in reqs.items():
        # A matching key or timing phrase is insufficient: only the exact owner-bound
        # allocation uses the deterministic measurement route (same boundary as SWE.3).
        if text in measured_statements:
            budgets[s] = (f"Run Target Scenario    {performance['test_source']}\n"
                          "    Simulation Performance Should Meet Budget")
            continue
        b = BUDGET_RX.search(text)
        kw = next((k for rx, k in BUDGET if rx.search(text)), None)
        if b and kw:
            budgets[s] = f"{kw}    {re.search(r'(\d+)', b.group(0)).group(1)}"
            continue
        task = amap.get(s, {}).get("task", "requirements:crosscutting")
        topic = "startup" if task.endswith("crosscutting") else re.sub(r"[^a-z0-9]+", "_",
                                                                         (task.partition(":")[2] or task).lower())
        topics.setdefault(topic, []).append(s)
    return {"topics": topics, "budgets": budgets}


def scn_files(topic: str) -> tuple[str, str]:
    return (f"software/tests/software/scn_{topic}.c", f"software/tests/software/scn_{topic}_pending.c")


def _context(ws: Path, swrs: list[str]) -> list[dict]:
    from ..assurance.register_contract import _requirements
    from .swe3 import _defines, _sig, interfaces

    iface = interfaces(ws)
    reqs = _requirements(ws)
    eff = json.loads((Path(ws) / "workproducts/SWE.1/register_effects.json").read_text())["effects"]
    req = "\n".join(f"{s} (TCHECK {int(s[4:])}): {reqs[s]}" for s in swrs) + "\n" + "\n".join(
        f"case {e['case']} ({e['swr']}): {e.get('register', '')}.{e.get('field', '')} op {e['op']}" +
        (f" value {e['value']}" if e.get("value") is not None else "") for e in eff if e["swr"] in swrs)
    api = "\n".join(f"{_sig(f)} - {f['operation']}" for f in iface["functions"])
    defs = _defines(ws, sorted({x for f in iface["functions"] for x in f["fields"]}))
    return [{"path": n, "text": t, "sha256": sha256_bytes(t.encode())}
            for n, t in (("requirements+cases", req), ("interface", api), ("generated defines", defs))]


def must_name(ws: Path, swrs: list[str]) -> dict[str, tuple[set[str], set[str]]]:
    """The HAL statuses and field masks run_robot's observation rule requires in each requirement's TCHECK
    (robot_policy.required_tokens, the same rule)."""
    from ..assurance.register_contract import _requirements
    from ..mcp.servers.robot_policy import required_tokens
    from .swe5 import _p

    p = _p(ws)
    reqs = _requirements(ws)
    return {s: required_tokens(reqs.get(s, ""), p["pfx"], p["fn"]) for s in swrs}


def scenario_packet(ws: Path, topic: str, swrs: list[str], model: str, findings=None, previous=None) -> dict:
    from .swe5 import _p

    p = _p(ws)
    need = must_name(ws, swrs)
    naming = "; ".join(f"TCHECK({int(s[4:])}) must name {' and '.join(sorted(h)) or ' or '.join(sorted(f))}"
                       for s, (h, f) in need.items() if h or f)
    model_txt = " ".join(str(p["prompt"].get("target_model") or "").split()) or (
        "The simulated peripheral is behavioural: every register starts at 0 and is plain read/write storage.")
    nums = ", ".join(f"{s} -> TCHECK({int(s[4:])}, ...)" for s in swrs)
    instr = (f"Write the Renode target scenario program(s) that verify these requirements of the {p['header']} LL "
             f"on the simulated target: {nums}. Target model: {model_txt} default_code is one complete program for "
             "scenario default; never_ready_code is a second complete program for scenario never_ready (only for "
             "requirements that need the update/ready flags held - list them in never_ready_swrs - otherwise \"\"). "
             f"Each program: '#include \"{p['header']}\"', '#include \"forge_target_test.h\"', the line "
             "'FORGE_MAILBOX_DEFINE;', then 'int main(void) { FORGE_TEST_BEGIN(); ... FORGE_TEST_END(); return 0; }'. "
             "Every requirement gets exactly ONE check TCHECK(<its number>, <condition>) in exactly one of the two "
             "programs, testing what the requirement states on LL return values and "
             f"{p['block']}[LL_{p['pfx']}_<REG>_OFFSET / 4U] register bits as the target model makes them observable. "
             f"Observation rule (checked by the test tool): {naming or 'none'}; a write-only field that the model "
             "reads as 0 is still named in its check (e.g. '(reg & <FIELD>_MSK) == 0U') together with the observable "
             "effect of the write. A requirement about the state after reset checks the register values BEFORE any LL "
             "call. Polls are "
             "bounded by the caller (at most 1000 iterations). Use only the interface functions, the generated "
             "defines and the register block.")
    return S.packet(phase=PHASE, task=f"scenario:{topic}", role="swe6-author", instructions=instr, sources=[],
                    artifacts=_context(ws, swrs), criteria=["one TCHECK per requirement, numbered as given",
                                                            "expected values from the requirement and the model"],
                    output_schema=SCN_SCHEMA, model=model, findings=findings, previous=previous, output_reserve=4096)


def validate_scenarios(ws: Path, doc: dict, swrs: list[str]) -> list[str]:
    from .swe3 import _header, interfaces
    from .swe5 import _p

    p = _p(ws)
    out = []
    want = {int(s[4:]) for s in swrs}
    progs = {"default_code": doc["default_code"], "never_ready_code": doc["never_ready_code"]}
    if doc["never_ready_swrs"] and not doc["never_ready_code"].strip():
        out.append("never_ready_swrs is not empty but never_ready_code is \"\"")
    out += [f"never_ready_swrs names {s}, which is not a requirement of this task" for s in doc["never_ready_swrs"]
            if s not in swrs]
    known = set(re.findall(r"#define\s+(\w+)", _header(ws).read_text()))
    api = {f["name"] for f in interfaces(ws)["functions"]}
    seen: dict[int, str] = {}
    for key, code in progs.items():
        if not code.strip():
            continue
        for need, what in ((f'#include "{p["header"]}"', "the LL header include"),
                           ('#include "forge_target_test.h"', "the forge_target_test.h include"),
                           ("FORGE_MAILBOX_DEFINE;", "FORGE_MAILBOX_DEFINE;"), ("FORGE_TEST_BEGIN()", "FORGE_TEST_BEGIN()"),
                           ("FORGE_TEST_END()", "FORGE_TEST_END()")):
            if need not in code:
                out.append(f"{key}: missing {what}")
        for n in re.findall(r"\bTCHECK\s*\(\s*(\d+)\s*,", code):
            n = int(n)
            if n not in want:
                out.append(f"{key}: TCHECK({n}) is not a requirement number of this task ({sorted(want)})")
            elif n in seen:
                out.append(f"TCHECK({n}) appears more than once ({seen[n]} and {key}): one check per requirement")
            seen[n] = key
        used = set(re.findall(rf"\bLL_{p['pfx']}_\w+", code))
        out += [f"{key}: {x} is neither an interface function nor a generated define" for x in sorted(used - known - api)]
        if re.search(r"\(\s*(?:volatile\s+)?uint32_t\s*\*\s*\)", code):
            out.append(f"{key}: no integer-to-pointer casts")
    out += [f"SWR-{n:03d} has no TCHECK({n})" for n in sorted(want - set(seen))]
    exprs = {int(m.group(1)): " ".join(m.group(2).split()) for code in progs.values()
             for m in re.finditer(r"\bTCHECK\s*\(\s*(\d+)\s*,(.*?)\)\s*;", code, re.S)}
    for s, (hal, fields) in must_name(ws, swrs).items():
        e = exprs.get(int(s[4:]), "")
        if not e:
            continue
        if hal and not all(h in e for h in hal):
            out.append(f"TCHECK({int(s[4:])}) must name {', '.join(sorted(hal))} ({s} states it)")
        elif not hal and fields and not any(f in e or f.split("_")[-2] in e for f in fields):
            out.append(f"TCHECK({int(s[4:])}) must name {' or '.join(sorted(fields))} ({s} names that field)")
    for s in doc["never_ready_swrs"]:
        if s in swrs and seen.get(int(s[4:])) == "default_code":
            out.append(f"{s} is listed in never_ready_swrs but its TCHECK is in default_code")
    return out


def render_suite(ws: Path, pl: dict, recs: dict[str, dict]) -> str:
    from ..workflow.robot_scaffold import PLACEHOLDER, build_suite

    text = build_suite((Path(ws) / "workproducts/SWE.1/software_requirements.md").read_text(), ws)
    for topic, swrs in pl["topics"].items():
        doc = recs[topic]["doc"]
        for s in swrs:
            pending = s in doc["never_ready_swrs"]
            scn = Path(scn_files(topic)[1 if pending else 0]).name
            body = (f"Run Target Scenario    {scn}" + ("    scenario=never_ready" if pending else "") +
                    f"\n    Target Check Should Pass    {int(s[4:])}")
            text = text.replace(f"{PLACEHOLDER}: {s}\n", body + "\n", 1)
    for s, kw in pl["budgets"].items():
        text = text.replace(f"{PLACEHOLDER}: {s}\n", kw + "\n", 1)
    return text


def _write(ws: Path, pl: dict, recs: dict[str, dict]) -> None:
    files = {_suite(ws): render_suite(ws, pl, recs)}
    for topic, r in recs.items():
        d, n = scn_files(topic)
        files[d] = r["doc"]["default_code"].rstrip() + "\n"
        if r["doc"]["never_ready_code"].strip():
            files[n] = r["doc"]["never_ready_code"].rstrip() + "\n"
    V.write_scoped(ws, files, "swe6_test_author")


def _topic_of(issue: str, pl: dict) -> list[str]:
    hit = [t for t, swrs in pl["topics"].items() if any(s in issue for s in swrs) or f"scn_{t}" in issue]
    m = re.search(r"#(\d+):", issue)
    if m:
        hit += [t for t, swrs in pl["topics"].items() if int(m.group(1)) in {int(s[4:]) for s in swrs}]
    return sorted(set(hit))


def visit_tests(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
                time_budget_s: float | None = None) -> dict:
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return V.reply(ws, PHASE, "FAILED", ["LRTX_SWE6_LAYER_NOT_SUPPORTED_YET (structured SWE.6 covers LL)"])
    role = {a.id: a for a in load_agents()[0]}["swe6-author"]
    since = V.last_finished(ws, PHASE)
    budget, findings = V.open_visit(ws, PHASE, resume, lambda: V.rework_findings(ws, PHASE, since) if since else [],
                                    max_calls or role.max_turns, time_budget_s)
    try:
        return _visit_tests(ws, model, budget, findings)
    except V.Continue as c:
        return V.reply(ws, PHASE, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)
    except (ValueError, FileNotFoundError) as exc:
        return V.reply(ws, PHASE, "FAILED", [str(exc)[:300]], budget)


def _visit_tests(ws: Path, model: str, budget: dict, findings: list[str]) -> dict:
    from ..inspection import defects
    from . import tools as T

    pl = plan(ws)
    routed: dict[str, list[str]] = {}
    for f in findings:
        for t in _topic_of(f, pl) or list(pl["topics"]):
            routed.setdefault(f"scenario:{t}", []).append(f)
    recs = {}
    for topic, swrs in pl["topics"].items():
        recs[topic] = V.run_task(ws, PHASE, f"scenario:{topic}",
                                 lambda fi, pr, t=topic, sw=swrs: scenario_packet(ws, t, sw, model, fi, pr),
                                 lambda d, sw=swrs: validate_scenarios(ws, d, sw), budget, routed.get(f"scenario:{topic}"))
    bad = [r for r in recs.values() if r["status"] != "VALID"]
    if bad:
        return V.reply(ws, PHASE, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:4]], budget)
    _write(ws, pl, recs)
    res = T.call(ws, "forge-tests-mcp", "run_robot", {}, "swe6-author", PHASE)
    filed = []
    if res["status"] != "PASS":
        per: dict[str, list[str]] = {}
        for i in res["issues"]:
            for t in _topic_of(i, pl):
                per.setdefault(t, []).append(i)
        for topic, fails in per.items():
            if budget["calls"] >= budget["max_calls"]:
                break
            budget["calls"] += 1
            instr = (f"The scenario programs below FAILED in run_robot: {'; '.join(fails)[:700]}. Decide from the "
                     "requirements, their cases and the target model ONLY: if a check expects something they do not "
                     "state, answer test_wrong with the corrected programs (same fields as before) and the reason; if "
                     "the checks expect exactly what they state, answer code_defect (programs unchanged) with a reason "
                     "quoting the requirement. Never weaken a check only to make it pass.")
            art = _context(ws, pl["topics"][topic]) + [{"path": "failed-programs", "text": json.dumps(
                recs[topic]["doc"], indent=1), "sha256": sha256_bytes(json.dumps(recs[topic]["doc"]).encode())}]
            t = S.call(S.packet(phase=PHASE, task=f"triage:{topic}", role="swe6-author", instructions=instr, sources=[],
                                artifacts=art, criteria=["the oracle decides, never the implementation"],
                                output_schema=TRIAGE_SCHEMA, model=model, output_reserve=4096))
            d = t["doc"] if not t["errors"] else None
            if d is None:
                continue
            swr_ids = sorted(set(re.findall(r"SWR-\d{3}", " ".join(fails) + d["reason"])))[:5]
            if d["verdict"] == "code_defect":
                try:
                    filed.append(defects.report(ws, detected_phase=PHASE, reported_by="swe6-author", kind="CODE",
                                                summary=f"scn_{topic}: {d['reason']}"[:400], requirement_ids=swr_ids,
                                                test_files=[scn_files(topic)[0]], evidence_refs=[
                                                    f"run_robot:{res['summary']}"[:120]],
                                                requirement_quote=d["reason"][:300])["id"])
                except defects.DefectError as exc:
                    filed.append(f"REFUSED:{exc}")
            else:
                new = {k: d[k] for k in ("default_code", "never_ready_code", "never_ready_swrs")}
                if validate_scenarios(ws, new, pl["topics"][topic]) != []:
                    continue
                try:
                    defects.report(ws, detected_phase=PHASE, reported_by="swe6-author", kind="TEST",
                                   summary=f"scn_{topic} corrected: {d['reason']}"[:400], requirement_ids=swr_ids,
                                   test_files=[f for f in scn_files(topic) if (ws / f).is_file()], evidence_refs=[],
                                   requirement_quote=d["reason"][:300])
                except defects.DefectError as exc:
                    filed.append(f"REFUSED:{exc}")
                    continue
                recs[topic] = {**recs[topic], "doc": new}
                V._ckpt(ws, PHASE, f"scenario:{topic}").write_text(json.dumps(recs[topic], indent=1))
        _write(ws, pl, recs)
        res = T.call(ws, "forge-tests-mcp", "run_robot", {}, "swe6-author", PHASE)
    S.record(ws, "SWE.6/tests-assembly.json", {"at": utc_now(), "topics": sorted(recs), "defects": filed,
                                               "run_robot": res.get("summary")})
    if res["status"] != "PASS":
        return V.reply(ws, PHASE, "FAILED", [f"run_robot: {i}" for i in res["issues"][:12]] +
                       [f"defect filed: {x}" for x in filed], budget)
    return V.reply(ws, PHASE, "PASS", [], budget, artifacts=[_suite(ws)])


def visit_report(ws: Path, model: str = "", **_k) -> dict:
    """Deterministic SWE.6 report from the journaled tool results (no model call)."""
    from ..assurance.register_contract import _requirements
    from . import tools as T

    ws = Path(ws)
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    rob = T.call(ws, "forge-tests-mcp", "run_robot", {}, "swe6-author", PHASE)
    tr = T.call(ws, "forge-evidence-mcp", "validate_trace", {}, "swe6-author", PHASE)
    failed = {i.split(":")[1] for i in rob.get("issues", []) if i.startswith(("ROBOT_FAIL:", "REQUIREMENT_NOT_OBSERVED:"))}
    rows = ["| SWR | Robot test | result | evidence |", "| --- | --- | --- | --- |"]
    rows += [f"| {s} | {s} ({_suite(ws)}) | {'FAIL' if s in failed or rob['status'] != 'PASS' and not failed else 'PASS'}"
             " | build/robot/output.xml, build/robot/log.html |" for s in _requirements(ws)]
    dfs = [json.loads(p.read_text()) for p in sorted((ws / ".forge-run/defects").glob("DEF-*.json"))] \
        if (ws / ".forge-run/defects").is_dir() else []
    md = ["# Software verification report", "", "Requirement-based tests: one Robot test per SWE.1 requirement on the "
          "simulated STM32N6 target (Renode) and the measured size/stack evidence.", "", *rows, "",
          f"run_robot: status {rob['status']}; \"{rob['summary']}\". validate_trace: status {tr['status']}; "
          f"\"{tr.get('summary', '')}\".", "", "## Fault responses and target constraints", "",
          "LL functions have no error codes or waits; fault responses (bounded polling, timeouts) belong to the caller "
          "or the HAL. Target constraints are the measured flash, static RAM and stack budgets above.", "",
          "## Regressions and defect status", ""]
    md += [f"- {d['id']} {d['kind']} -> {d.get('target_phase')}: {d.get('status')} - {d.get('summary', '')[:160]}"
           for d in dfs] or ["- no defects recorded"]
    md += ["", "## Unverified items", "", "Host tests plus a simulated Cortex-M55 target (Renode, behavioural "
           f"{m.get('peripheral', 'RCC').upper()} model) only; no silicon or board verification. Safety allocation as "
           f"stated in the manifest: {m['target'].get('safety_allocation', 'UNSPECIFIED')}. The HAL is not part of "
           "this work order.", ""]
    V.write_scoped(ws, {"workproducts/SWE.6/software_verification_report.md": "\n".join(md)}, "swe6_author")
    ok = rob["status"] == "PASS"
    return V.reply(ws, PHASE, "PASS" if ok else "FAILED", [] if ok else rob.get("issues", [])[:12], None,
                   artifacts=["workproducts/SWE.6/software_verification_report.md"])


def visit(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    """The SWE.6 author node (also the rework entry): the scenario visit, then the deterministic report."""
    rep = visit_tests(ws, model, max_calls, resume=resume, time_budget_s=time_budget_s)
    return rep if rep["status"] != "PASS" else visit_report(ws, model)
