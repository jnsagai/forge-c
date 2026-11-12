"""RPR-076 (standalone SWE.1 omission test on Omniverse2, 2026-10-31): a gate-frozen SWE.1 baseline (Ornith a02, CRC
IDR) left out three obligations of the owner contract (no polling, no error code, other registers preserved). No gate
compared the requirements with owner obligations, and four inspector configurations passed the baseline.

Scenario: the IWDG LL work order (tracked RM inputs, a stub for the git-ignored datasheet) declares an owner
obligations input; a scripted author writes every requirement but maps none to OBL-no-polling, records no gap and
replies PASS. Symptom: the unchanged SWE.1 author gate freezes that baseline."""
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "SWE.1 baseline that omits a declared owner obligation is frozen by the author gate"
SYS = "IWDG LL driver"
OBL = {"schema": "forge-c/owner-obligations/1", "status": "DRAFT_FOR_OWNER_REVIEW", "owner": "rpr076",
       "source_inputs": [], "obligations": [
           {"id": "OBL-start-key", "statement": "Enable starts the watchdog by writing the start key.",
            "critical": True, "effects": [{"register": "IWDG_KR", "field": "KEY", "op": "write"}]},
           {"id": "OBL-no-polling", "statement": "The driver never waits on a status flag.", "critical": True}]}


def _req(key, st, page, effects=(), by="host_unit_test"):
    return {"key": key, "statement": st, "source_page": page, "verified_by": by, "effects": list(effects),
            "obligations": ["OBL-start-key"] if key == "start" else [],
            "verification": "Host unit test calls the function on the RAM register array and passes when the register "
                            "field holds the expected value."}


def _eff(case, reg, fld, op, value=""):
    return {"case": case, "register": reg, "field": fld, "op": op, "value": value}


ANSWERS = {
    "requirements:IWDG_KR": {"requirements": [
        _req("start", f"When LL_IWDG_Enable is called, the {SYS} shall write 0x0000CCCC to IWDG_KR.KEY.", 2989,
             [_eff("START", "IWDG_KR", "KEY", "write", "0xCCCC")]),
        _req("refresh", f"When LL_IWDG_ReloadCounter is called, the {SYS} shall write 0x0000AAAA to IWDG_KR.KEY.", 2989,
             [_eff("REFRESH", "IWDG_KR", "KEY", "write", "0xAAAA")]),
        _req("unlock", f"When LL_IWDG_EnableWriteAccess is called, the {SYS} shall write 0x00005555 to IWDG_KR.KEY.",
             2989, [_eff("UNLOCK", "IWDG_KR", "KEY", "write", "0x5555")]),
        _req("lock", f"When LL_IWDG_DisableWriteAccess is called, the {SYS} shall write 0x00000000 to IWDG_KR.KEY.",
             2989, [_eff("LOCK", "IWDG_KR", "KEY", "write", "0x0")])], "not_covered": [], "open_points": []},
    "requirements:IWDG_PR": {"requirements": [
        _req("prescaler", f"When LL_IWDG_SetPrescaler is called with a value from 0U to 15U, the {SYS} shall write the "
             "value to IWDG_PR.PR.", 2990, [_eff("SET_PRESCALER", "IWDG_PR", "PR", "write", "0x5")])],
        "not_covered": [], "open_points": []},
    "requirements:IWDG_RLR": {"requirements": [
        _req("reload", f"When LL_IWDG_SetReloadCounter is called with a value from 0U to 4095U, the {SYS} shall write "
             "the value to IWDG_RLR.RL.", 2990, [_eff("SET_RELOAD", "IWDG_RLR", "RL", "write", "0xFFF")])],
        "not_covered": [], "open_points": []},
    "requirements:IWDG_SR_1": {"requirements": [
        _req("onf_set", f"When LL_IWDG_IsActive is called with IWDG_SR.ONF set, the {SYS} shall return 1U.", 2991,
             [_eff("ONF_SET", "IWDG_SR", "ONF", "no_write")])],
        "not_covered": [{"field": "IWDG_SR.EWIF", "reason": "early wake-up interrupt out of scope"},
                        {"field": "EWU", "reason": "early wake-up interrupt out of scope"}], "open_points": []},
    "requirements:IWDG_SR_2": {"requirements": [
        _req("pvu", f"When LL_IWDG_IsActiveFlag_PVU is called with IWDG_SR.PVU set, the {SYS} shall return 1U.", 2991,
             [_eff("PVU_SET", "IWDG_SR", "PVU", "no_write")]),
        _req("rvu", f"When LL_IWDG_IsActiveFlag_RVU is called with IWDG_SR.RVU set, the {SYS} shall return 1U.", 2991,
             [_eff("RVU_SET", "IWDG_SR", "RVU", "no_write")])],
        "not_covered": [{"field": "IWDG_SR.WVU", "reason": "window option out of scope"}], "open_points": []},
    "requirements:crosscutting": {"requirements": [
        _req("startup", f"While no LL function has been called after reset, the {SYS} shall not write any IWDG "
             "register.", 2989, by="target_robot_test")], "not_covered": [], "open_points": [],
        "obligation_gaps": []},
}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "state/events")
        from forge_factory import workorder
        from forge_factory.common import REPO_ROOT, sha256_file
        from forge_factory.inspection import gate
        from forge_factory.lrtx import structured as S
        from forge_factory.lrtx import swe1
        from forge_factory.workflow.builder import binding_for, build

        spec = json.loads((REPO_ROOT / "examples/0009a-iwdg-ll/workorder.json").read_text())
        ex = root / "examples/0009a-iwdg-ll"
        ex.mkdir(parents=True)
        for item in spec["inputs"]:
            src, dst = REPO_ROOT / "examples/0009a-iwdg-ll" / item["path"], ex / item["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file() and item["role"] != "datasheet":
                shutil.copyfile(src, dst)
            else:  # the git-ignored datasheet: SWE.1 reads the RM chapter only
                dst.write_text("# datasheet (reproducer stub)\n")
        shutil.copytree(REPO_ROOT / "examples/0009a-iwdg-ll/upstream", ex / "upstream")
        (ex / "workorder.json").write_text(json.dumps(spec))
        workorder.REPO_ROOT = root
        ws, _m = workorder.prepare(ex, "WO-RPR076")
        _g, nodes = build("WO-RPR076", layer="LL", trace=True, peripheral="iwdg")
        binding_for("WO-RPR076", str(ws), nodes).dump(ws / ".forge-run/binding.json")
        p = ws / "inputs/owner-obligations.json"
        p.write_text(json.dumps(OBL, indent=1))
        mp = ws / ".forge-run/manifest.json"
        man = json.loads(mp.read_text())
        man["inputs"].append({"path": "inputs/owner-obligations.json", "role": "owner_obligations",
                              "sha256": sha256_file(p), "bytes": p.stat().st_size})
        mp.write_text(json.dumps(man, indent=1))

        def call(packet, **_):
            return {"doc": json.loads(json.dumps(ANSWERS[packet["task"]])), "errors": [],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "wall_ms": 1.0, "finish_reason": "stop"}

        S.call = call
        swe1.visit(ws, "fixture")  # the fixed author may self-reject; the gate below decides
        if not (ws / swe1.REQS).is_file():
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no requirements assembled")
            return 2
        rp = ws / ".forge-run/lrtx/SWE.1/reply.json"
        reply = json.loads(rp.read_text())
        reply.update(status="PASS", issues=[])  # an author (any path) claiming PASS on the omitted obligation
        sys.stdin = io.StringIO(json.dumps(reply))
        rc = gate.main(["--workspace", str(ws), "--phase", "SWE.1", "--step", "author"])
        log = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    if rc == 0:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    last = [e for e in log if e.get("phase") == "SWE.1" and e.get("step") == "author"][-1:]
    issues = [str(i) for e in last for i in e.get("issues") or []]
    if not any(i.startswith("SWE1_OBLIGATION_UNCOVERED:OBL-no-polling") for i in issues):
        print(f"REPRODUCER_ERROR:GATE_REFUSED_FOR_ANOTHER_REASON:{issues[:2]}")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
