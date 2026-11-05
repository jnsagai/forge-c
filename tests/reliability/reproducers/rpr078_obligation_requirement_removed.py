"""RPR-078 (Fabro SWE.1 run WO-F014-SWE1-OBL-20261031-03 on Omniverse2, 2026-10-31): the critical owner obligation
"preserve every other register" stayed unimplemented. The natural requirement names the task register; the cross-
cutting validator answered "remove requirement [k] from the cross-cutting task", which contradicts the obligation, and
the one development repair pass was spent before the post-assembly coverage check reported it.

Scenario: IWDG LL work order with a critical obligation without register effects; a scripted cross-cutting author that
follows findings literally names IWDG_KR.KEY in its preservation requirement, deletes the requirement when told to
remove it, and rephrases it when told how. Symptom: the factory tells the author to remove a requirement that
implements a declared owner obligation."""
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "SWE.1 author told to remove a requirement that implements a declared owner obligation"
SYS = "IWDG LL driver"
OBL = {"schema": "forge-c/owner-obligations/1", "status": "DRAFT_FOR_OWNER_REVIEW", "owner": "rpr078",
       "source_inputs": [], "obligations": [
           {"id": "OBL-start-key", "statement": "Enable starts the watchdog by writing the start key.",
            "critical": True, "effects": [{"register": "IWDG_KR", "field": "KEY", "op": "write"}]},
           {"id": "OBL-preserve-others", "statement": "Preserve every other register and other peripheral instances.",
            "critical": True}]}


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
        ws, _m = workorder.prepare(ex, "WO-RPR078")
        _g, nodes = build("WO-RPR078", layer="LL", trace=True, peripheral="iwdg")
        binding_for("WO-RPR078", str(ws), nodes).dump(ws / ".forge-run/binding.json")
        p = ws / "inputs/owner-obligations.json"
        p.write_text(json.dumps(OBL, indent=1))
        mp = ws / ".forge-run/manifest.json"
        man = json.loads(mp.read_text())
        man["inputs"].append({"path": "inputs/owner-obligations.json", "role": "owner_obligations",
                              "sha256": sha256_file(p), "bytes": p.stat().st_size})
        mp.write_text(json.dumps(man, indent=1))

        told_remove = []

        def call(packet, **_):
            doc = json.loads(json.dumps(ANSWERS[packet["task"]]))
            if packet["task"] == "requirements:crosscutting":
                fs = " ".join(packet.get("findings") or [])
                if "remove requirement [preserve_others]" in fs:
                    told_remove.append(True)
                    return {"doc": doc, "errors": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                            "wall_ms": 1.0, "finish_reason": "stop"}  # the literal author deletes it
                st = (f"When an LL function is called, the {SYS} shall leave every other register and every other "
                      "IWDG instance unchanged.") if "without naming" in fs else (
                      f"When an LL function is called, the {SYS} shall leave every register other than IWDG_KR.KEY "
                      "unchanged.")
                doc["requirements"].append({"key": "preserve_others", "statement": st, "source_page": 2989,
                                            "verified_by": "host_unit_test", "effects": [],
                                            "obligations": ["OBL-preserve-others"],
                                            "verification": "Host unit test snapshots every IWDG register and passes "
                                                            "when only the named field changed."})
            return {"doc": doc, "errors": S.validate(doc, packet["output_schema"]),
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "wall_ms": 1.0, "finish_reason": "stop"}

        S.call = call
        rep = swe1.visit(ws, "fixture")
    if told_remove:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if rep["status"] != "PASS":
        print(f"REPRODUCER_ERROR:VISIT_{rep['status']}:{(rep.get('issues') or [''])[0][:120]}")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
