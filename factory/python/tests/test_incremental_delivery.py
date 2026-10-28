"""Incremental M1 plumbing, with explicit external-review/inspector fixtures; no Qwen claim."""
import copy
import json
import shutil
import subprocess

import pytest
from forge_factory import development_execution as D
from forge_factory import peripheral
from forge_factory import provided_requirements as P
from forge_factory import workorder as W
from forge_factory.afo.durable import digest
from forge_factory.brownfield.inject import inject
from forge_factory.common import REPO_ROOT, pretty_json, sha256_file
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1
from forge_factory.policy.authz import Binding
from test_resume_from import _all_pass

EX = REPO_ROOT / "examples/0014d-st-cube-crc-idr-assisted"


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    for key in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + key + "_DIR", str(tmp_path / key))
    ws, man = W.prepare(EX, "WO-IDR-PLUMBING", purpose="ASPICE_ONLY")
    Binding("idr-fixture", str(ws), {"swe1_author": {"role": "swe1-author", "phase": "SWE.1"}}).dump(
        ws / ".forge-run/binding.json")
    return ws, man


def reviewed_fixture(ws, man):
    """Synthetic external review input for plumbing only; never an owner/live review."""
    path = ws / man["provided_requirements"]["path"]
    d = json.loads(path.read_text())
    d["review"] = {"status": "REVIEWED", "reviewed_by": "Synthetic fixture reviewer",
                   "reviewed_at": "2026-10-28", "record_ref": "fixture:NOT_A_LIVE_HUMAN_REVIEW",
                   "payload_sha256": digest(P.payload(d))}
    path.chmod(0o644)
    path.write_text(pretty_json(d))
    path.chmod(0o444)
    man["provided_requirements"]["sha256"] = sha256_file(path)
    for item in man["inputs"]:
        if item["path"] == man["provided_requirements"]["path"]:
            item["sha256"] = sha256_file(path)
    (ws / ".forge-run/manifest.json").write_text(pretty_json(man))


def test_exact_idr_scope_keeps_shared_profile_and_delivery_frozen(prepared):
    ws, man = prepared
    assert man["delivery"]["scope"]["functions"] == ["LL_CRC_Write_IDR", "LL_CRC_Read_IDR"]
    assert [g["register"] for g in swe1.groups(swe1.inventory(ws))] == ["CRC_IDR"]
    assert len(peripheral.load("crc")["rm"]["key_sections"]) == 5
    assert len(peripheral.of_ws(ws)["rm"]["key_sections"]) == 1
    assert not (ws / "software/ll/stm32n6xx_ll_crc.h").exists()
    assert man["code_mode"] == "FROZEN"


def test_pending_review_is_not_replaced_by_codex_or_a_model(prepared):
    ws, man = prepared
    with pytest.raises(ValueError, match="REVIEW_MISSING"):
        P.materialize(ws)
    assert Store(ws).latest_baseline("SWE.1") is None
    assert json.loads((EX / "provided-requirements.json").read_text())["review"]["status"] == "PENDING"


def imported(prepared):
    ws, man = prepared
    reviewed_fixture(ws, man)
    rep = P.materialize(ws)
    assert rep["status"] == "PASS"
    assert gate.step_author(Store(ws), "SWE.1", json.dumps(rep)) == 0
    store = Store(ws)
    baseline = store.latest_baseline("SWE.1")
    record = store.record_inspection("SWE.1", "swe1-inspector", baseline["baseline_id"], _all_pass("SWE.1"))
    assert record["verdict"] == "PASS", record  # Explicit inspector substitution; deterministic checks are real.
    return ws, man


def test_import_real_validation_freeze_and_later_tamper_invalidation(prepared):
    ws, man = imported(prepared)
    receipt = json.loads((ws / "traceability/assisted_requirements.json").read_text())
    assert receipt["qwen_authored"] is False and receipt["authorship"] == "EXTERNALLY_PREPARED"
    assert Store(ws).gate("SWE.1")["decision"] == "PASS"
    source = ws / "inputs/RM0486-rev4-ch26-crc.md"
    source.chmod(0o644)
    source.write_text(source.read_text() + "\nchanged primary input\n")
    assert P.findings(ws)
    assert all(Store(ws).gate("SWE." + str(i))["decision"] == "BLOCKED" for i in range(1, 7))


def test_shared_repair_pass_cannot_refill_on_task_or_phase_reentry(prepared):
    ws, _ = prepared
    p = {"phase": "SWE.2", "role": "swe2-author", "task": "interface:a"}
    assert D.reserve_call(ws, p)
    assert D.reserve_phase_rework(ws, "SWE.2")
    assert D.reserve_call(ws, p)
    assert not D.reserve_call(ws, p)
    assert not D.reserve_phase_rework(ws, "SWE.2")
    q = {**p, "task": "interface:b", "findings": ["previous task failed"]}
    assert D.reserve_call(ws, q)
    assert not D.reserve_call(ws, q)
    assert {r["status"] for r in D.ladder(ws, "SWE.2") if r["rung"] == "general_product_diagnosis"} == {
        "DEFERRED_BY_DEVELOPMENT_POLICY"}


def test_localized_repair_spends_the_only_phase_reentry(prepared):
    ws, _ = prepared
    p = {"phase": "SWE.4", "role": "swe4-author", "task": "triage:UT-001"}
    assert D.reserve_call(ws, p)
    assert not D.reserve_call(ws, p)
    assert not D.reserve_phase_rework(ws, "SWE.4")
    assert {r["status"] for r in D.ladder(ws, "SWE.4") if r["rung"] in
            ("initial_engineering", "bounded_phase_repair")} == {"RESERVED"}
    token = S.RECOVERY_WORKSPACE.set(ws)
    try:
        assert S.call(p)["errors"] == ["CALL_REFUSED:DEVELOPMENT_PHASE_REPAIR_EXHAUSTED"]
    finally:
        S.RECOVERY_WORKSPACE.reset(token)


def test_default_work_orders_keep_existing_repair_behavior(tmp_path):
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text("{}")
    for _ in range(10):
        assert D.reserve_call(tmp_path, {"role": "swe1-author"})
    assert not (tmp_path / ".forge-run/lrtx").exists()


def test_native_tool_repair_cannot_become_another_edit_verify_loop(prepared):
    from forge_factory.policy.authz import Authorizer

    ws, _ = prepared
    auth = Authorizer(Binding("repair-fixture", str(ws), {
        "author": {"role": "swe4-author", "phase": "SWE.4"}}))
    assert D.verification(ws, "SWE.4", "swe4-author", "run_unit", "FAIL")
    first = auth.decide("author", "write_file", {"path": "software/tests/unit/test_crc.c", "content": "fix"})
    assert first.allow
    D.verification(ws, "SWE.4", "swe4-author", "run_unit", "FAIL")
    assert not D.verification(ws, "SWE.4", "swe4-author", "run_unit")
    second = auth.decide("author", "write_file", {"path": "software/tests/unit/test_other.c", "content": "more"})
    assert not second.allow and second.code == "DEVELOPMENT_PHASE_REPAIR_EXHAUSTED"
    assert auth.decide("author", "write_file", {
        "path": "workproducts/SWE.4/unit_verification_report.md", "content": "BLOCKED"}).allow


def test_cmsis_development_uses_existing_pointer_capable_mcp_author(prepared):
    _, man = prepared
    local = {"id": "local-rtx-v2-omniverse2-q38-aspice"}
    scoped = W.local_profile_structured(local, man, "qwen3.8:27b-q8_0")
    assert "SWE.1" in scoped["phases"] and "SWE.2" not in scoped["phases"]
    assert "SWE.2" not in scoped["inspect_phases"]
    legacy = copy.deepcopy(man)
    legacy.pop("development_execution")
    assert "SWE.2" in W.local_profile_structured(local, legacy, "qwen3.8:27b-q8_0")["phases"]


def test_frozen_st_idr_host_oracle_target_compile_and_wrong_read_negative(prepared, tmp_path):
    from forge_factory.brownfield import cmsis

    ws, man = imported(prepared)
    assert inject(ws)["status"] == "INJECTED"
    header = ws / "software/ll/stm32n6xx_ll_crc.h"
    before = sha256_file(header)
    c = tmp_path / "idr.c"
    c.write_text("""
#define FORGE_HOST_DEVICE_IMPLEMENTATION
#include "forge_host_device.h"
#include "stm32n6xx_ll_crc.h"
int main(void) {
 CRC_TypeDef r = {0}; const uint32_t v[] = {0U,0xffffffffU,0xaaaaaaaaU,0x55555555U,0x80000001U};
 for(unsigned i=0;i<5;i++) {
  r.DR=0x87654321U; r.CR=0x12340000U; r.INIT=0xfedcba98U; r.POL=0x04c11db7U;
  LL_CRC_Write_IDR(&r,v[i]);
  if(r.IDR!=v[i] || r.DR!=0x87654321U || r.CR!=0x12340000U ||
     r.INIT!=0xfedcba98U || r.POL!=0x04c11db7U) return 1;
  r.IDR=~v[i];
  if(LL_CRC_Read_IDR(&r)!=~v[i]) return 2;
 } return 0;
}
""")
    flags = cmsis.host_flags(ws)
    compiler = shutil.which("clang")
    assert compiler, "real host compiler required"
    def compile_and_run(directory, name):
        exe = tmp_path / name
        cmd = [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", *flags, "-I" + str(directory),
               str(c), "-o", str(exe)]
        built = subprocess.run(cmd, capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        return subprocess.run([str(exe)]).returncode
    assert compile_and_run(header.parent, "correct") == 0
    mutant = tmp_path / "mutant"
    mutant.mkdir()
    text = header.read_text()
    assert "READ_REG(CRCx->IDR)" in text
    (mutant / header.name).write_text(text.replace("READ_REG(CRCx->IDR)", "READ_REG(CRCx->DR)", 1))
    assert compile_and_run(mutant, "wrong") != 0
    unit = cmsis.delivered_unit(ws, tmp_path / "target")
    obj = tmp_path / "target.o"
    target = subprocess.run(["arm-none-eabi-gcc", "-mcpu=cortex-m55", "-mthumb", "-std=c11", "-Os",
                             "-Wall", "-Werror", *cmsis.target_flags(ws), "-I" + str(header.parent),
                             "-c", str(unit), "-o", str(obj)], capture_output=True, text=True)
    assert target.returncode == 0, target.stderr
    assert obj.is_file() and sha256_file(header) == before

def test_six_phase_anchor_and_broken_required_trace_prevent_acceptance(prepared, tmp_path, monkeypatch):
    from forge_factory.release import finalize
    from incremental_idr_anchor import Anchor

    ws, _ = imported(prepared)
    assert inject(ws)["status"] == "INJECTED"
    anchor = Anchor(ws, monkeypatch)
    anchor.architecture()
    anchor.implementation()
    anchor.unit()
    anchor.integration()
    anchor.validation()
    result = finalize.finalize(ws, "idr-scripted-provider-fixture")
    assert result["package_status"] == "READY_FOR_OFFLINE_REVIEW", result["gaps"]
    assert finalize.verify_archive(__import__("pathlib").Path(result["archive"]))["integrity"] == "PASS"
    mutant = tmp_path / "broken-trace-workspace"
    shutil.copytree(ws, mutant)
    trace = mutant / "traceability/requirements_to_tests.csv"
    trace.write_text("requirement_id,test_id,test_file\n")
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "mutant-archives"))
    negative = finalize.finalize(mutant, "idr-broken-trace-fixture")
    assert negative["package_status"] == "BLOCKED"
