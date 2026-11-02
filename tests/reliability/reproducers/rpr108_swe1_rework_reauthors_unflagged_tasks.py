"""RPR-108 (Fabro run WO-F014-CMP-SWE1-RCC-20261102-03, cloud comparison line, loop10, 2026-11-02): RCC LL structured
SWE.1. The first author visit froze BL-SWE.1-001 (61 register tasks + cross-cutting, 65 calls); INS-SWE.1-001 returned
REWORK with eight findings in SWE1-02/-03/-05 that name 11 register tasks. One finding cited 'SWR-001-SWR-010 and Open
points' without a note id and was routed to every note origin, i.e. all 62 tasks; a finding citing only the work-order
flash budget requirement was routed to none. Every resumed node execution then re-sent the visit's findings to tasks
that had already answered them: 21 continuations re-authored the first 9 tasks over and over (190 of 256 calls by
07:15Z) and the visit never reached the rest.

Scenario: the real swe1.visit on the prepared IWDG LL work order (5 register tasks + cross-cutting) with scripted model
answers (no model call). Every task records an open point; after a PASS visit the gate log carries incident-shaped
findings (an SWR range with an open-points mention but no note id, one single-SWR finding, one budget-only finding).
The rework visit runs under a time box that admits one model call per node execution (fake clock), resumed up to 8
times. Symptom: a register task no finding names is re-authored, or a named task is re-authored more than once.

No git-ignored input is read and nothing is written into a checkout: the checkout under test is the one the imported
forge_factory belongs to (forge_factory.common.REPO_ROOT, which the CRE runner sets to its worktree). The IWDG LL work
order is copied into a fresh temporary directory with its input paths pointed at the tracked files of that checkout;
its datasheet input (git-ignored owner input, read by no SWE.1 code: register tasks read their RM section files) is
left out."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "a SWE.1 rework re-authors register tasks no finding names or repeats answered tasks after each time box"
SYS = "IWDG LL driver"
EXAMPLE = "0009a-iwdg-ll"
VER = "Host unit test calls the function on the RAM register array and passes when the register field holds the value."


def _req(key, st, page, effects=(), by="host_unit_test"):
    return {"key": key, "statement": st, "source_page": page, "verified_by": by, "effects": list(effects),
            "verification": VER}


def _eff(case, reg, fld, op, value=""):
    return {"case": case, "register": reg, "field": fld, "op": op, "value": value}


def _answers() -> dict:
    kr = [_req(k, f"When LL_IWDG_{fn} is called, the {SYS} shall write 0x0000{v} to IWDG_KR.KEY.", 2989,
               [_eff(k.upper(), "IWDG_KR", "KEY", "write", f"0x{v.lstrip('0') or '0'}")])
          for k, fn, v in (("start", "Enable", "CCCC"), ("refresh", "ReloadCounter", "AAAA"),
                           ("unlock", "EnableWriteAccess", "5555"), ("lock", "DisableWriteAccess", "0000"))]
    return {
        "requirements:IWDG_KR": {"requirements": kr, "not_covered": []},
        "requirements:IWDG_PR": {"requirements": [_req("prescaler", f"When LL_IWDG_SetPrescaler is called with a value "
                                 f"from 0U to 15U, the {SYS} shall write the value to IWDG_PR.PR.", 2990,
                                 [_eff("SET_PRESCALER", "IWDG_PR", "PR", "write", "0x5")])], "not_covered": []},
        "requirements:IWDG_RLR": {"requirements": [_req("reload", f"When LL_IWDG_SetReloadCounter is called with a "
                                  f"value from 0U to 4095U, the {SYS} shall write the value to IWDG_RLR.RL.", 2990,
                                  [_eff("SET_RELOAD", "IWDG_RLR", "RL", "write", "0xFFF")])], "not_covered": []},
        "requirements:IWDG_SR_1": {"requirements": [_req("onf_set", f"When LL_IWDG_IsActive is called with IWDG_SR.ONF "
                                   f"set, the {SYS} shall return 1U.", 2991, [_eff("ONF_SET", "IWDG_SR", "ONF",
                                                                                   "no_write")])],
                                   "not_covered": [{"field": "IWDG_SR.EWIF", "reason": "early wake-up out of scope"},
                                                   {"field": "EWU", "reason": "early wake-up out of scope"}]},
        "requirements:IWDG_SR_2": {"requirements": [
            _req("pvu", f"When LL_IWDG_IsActiveFlag_PVU is called with IWDG_SR.PVU set, the {SYS} shall return 1U.",
                 2991, [_eff("PVU_SET", "IWDG_SR", "PVU", "no_write")]),
            _req("rvu", f"When LL_IWDG_IsActiveFlag_RVU is called with IWDG_SR.RVU set, the {SYS} shall return 1U.",
                 2991, [_eff("RVU_SET", "IWDG_SR", "RVU", "no_write")])],
            "not_covered": [{"field": "IWDG_SR.WVU", "reason": "window option out of scope"}]},
        "requirements:crosscutting": {"requirements": [_req("startup", f"While no LL function has been called after "
                                      f"reset, the {SYS} shall not write any IWDG register.", 2989,
                                      by="target_robot_test")], "not_covered": []},
    }


def _example(repo: Path, root: Path) -> Path:
    """The work order in `root`, its inputs resolved to the tracked files of `repo` (prepare requires that)."""
    src = repo / "examples" / EXAMPLE
    example = root / "examples" / EXAMPLE
    shutil.copytree(src / "upstream", example / "upstream")
    spec = json.loads((src / "workorder.json").read_text())
    spec["inputs"] = [{**item, "path": str((src / item["path"]).resolve())} for item in spec["inputs"]
                      if item["role"] != "datasheet"]
    for item in spec["inputs"]:
        if not Path(item["path"]).is_file():
            raise FileNotFoundError(item["path"])
    (example / "workorder.json").write_text(json.dumps(spec, indent=1))
    return example


def main() -> int:
    from forge_factory.common import REPO_ROOT

    if not (REPO_ROOT / "examples" / EXAMPLE / "workorder.json").is_file():
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:IWDG LL example not present")
        return 2
    with tempfile.TemporaryDirectory(prefix="rpr108-") as td:
        return _run(td, _example(REPO_ROOT, Path(td) / "tree"))


def _run(td: str, example: Path) -> int:
    os.environ["FORGE_STATE_DIR"] = str(Path(td) / "state")
    from forge_factory import workorder
    from forge_factory.common import utc_now
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe1
    from forge_factory.lrtx import visit as V
    from forge_factory.workflow.builder import binding_for, build

    ws, _m = workorder.prepare(example, "WO-RPR108")
    _g, nodes = build("WO-RPR108", layer="LL", trace=True, peripheral="iwdg")
    binding_for("WO-RPR108", str(ws), nodes).dump(ws / ".forge-run/binding.json")
    answers = _answers()
    for task, doc in answers.items():
        doc["open_points"] = [f"{task.split(':')[1]} write access depends on the caller's privilege configuration."]
    calls, clock = [], {"t": 0.0}

    def call(p, **_k):
        clock["t"] += 100.0
        calls.append(p)
        doc = json.loads(json.dumps(answers[p["task"]]))
        if p.get("findings"):  # a rework answer states the precondition the finding asks for
            doc["open_points"].append("The caller holds the access rights the write needs before calling the driver.")
        return {"doc": doc, "errors": S.validate(doc, p["output_schema"]),
                "usage": {"prompt_tokens": 1000, "completion_tokens": 200}, "wall_ms": 1.0, "finish_reason": "stop"}

    S.call = call
    V.time = type("Clock", (), {"monotonic": staticmethod(lambda: clock["t"])})
    first = swe1.visit(ws, "scripted")
    if first["status"] != "PASS":
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:first visit {first['status']}:{first['issues'][:2]}")
        return 2
    amap = json.loads((ws / ".forge-run/lrtx/SWE.1/assembly.json").read_text())
    swr = {t: sorted(s for s, v in amap["swr"].items() if v["task"] == t) for t in {v["task"] for v in amap["swr"].values()}}
    kr, rlr, budget = swr["requirements:IWDG_KR"], swr["requirements:IWDG_RLR"], swr["budgets"]
    findings = [
        f"SWE1-02: Major - software_requirements.md, {kr[0]}–{kr[-1]} and Open points: the register writes lack a "
        "defined caller access precondition, although the open points identify privilege restrictions.",
        f"SWE1-03: Major - software_requirements.md, {rlr[0]}: failure behaviour within the supported domain is not "
        "established; specify the caller preconditions.",
        f"SWE1-02: Major - software_requirements.md, {budget[0]}: the flash limit does not define the measured image."]
    (ws / ".forge-run/gates").mkdir(parents=True, exist_ok=True)
    with (ws / ".forge-run/gates/gate-log.jsonl").open("a") as f:
        f.write(json.dumps({"phase": "SWE.1", "ts": utc_now(), "result": "FAIL", "issues": findings}) + "\n")
    named = {"requirements:IWDG_KR", "requirements:IWDG_RLR"}
    calls.clear()
    statuses = []
    for n in range(9):
        statuses.append(swe1.visit(ws, "scripted", resume=n > 0, time_budget_s=50)["status"])
        if statuses[-1] != "CONTINUE":
            break
    if "CONTINUE" not in statuses:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the rework visit never hit its time box")
        return 2
    per = {t: sum(p["task"] == t for p in calls) for t in sorted({p["task"] for p in calls})}
    print(json.dumps({"node_executions": len(statuses), "last_status": statuses[-1], "calls": len(calls),
                      "authored": per}, sort_keys=True))
    unnamed = [t for t in per if t not in named and t != "requirements:crosscutting"]
    repeated = [t for t, k in per.items() if k > 1]
    if not set(per) & named:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no named task was re-authored")
        return 2
    if unnamed or repeated or statuses[-1] != "PASS":
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
