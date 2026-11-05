"""Actual CPU/public SDK and normal approval CONTROL; no live role/phase qualification.

Independent inspector criteria are synthetic deterministic test oracles. Target
observations, source hashing, defect transitions and resume/trace paths are real.
"""
import json
import shutil
from types import SimpleNamespace

import pytest
import test_unit_target_carry as F
from forge_factory import workorder as W
from forge_factory.common import canonical_json, sha256_file
from forge_factory.inspection import defects, swtrace
from forge_factory.inspection import provided_changes as PC
from forge_factory.inspection.engine import Store
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import sim
from forge_factory.mcp.servers import tests as U
from forge_factory.policy.authz import Authorizer, Binding
from forge_factory.workflow import provided_input_identity as I
from forge_factory.workflow import provided_ll_unit as P
from forge_factory.workflow import unit_target_carry as C
from forge_factory.workflow import unit_target_observation as O
from forge_factory.workflow import unit_target_timing as T
from test_unit_target_observation import actual, write

LL = "software/ll/stm32n6xx_ll_wwdg.h"


@pytest.fixture
def corrected(tmp_path, monkeypatch, request):
    original = F.observation_ws

    def origin(ws):
        original.__wrapped__(ws)
        path = ws / LL
        path.write_text(path.read_text().replace("x->SR = 0U", "x->SR = ~WWDG_SR_EWIF"))
        man = json.loads((ws / ".forge-run/manifest.json").read_text())
        man.update(unit_verification="uspec-gtest-v1", hal_unit_isolation="ll-fake-v1")
        write(ws, ".forge-run/manifest.json", man)

    class BeforeUnit(Exception):
        pass

    def stop(*args, **kwargs):
        raise BeforeUnit

    # Stop only the fixture bootstrap after its real S1–3 approval records.
    # No adapter substitution: actual verification below uses the public SDK.
    with monkeypatch.context() as bootstrap:
        bootstrap.setattr(F, "observation_ws", SimpleNamespace(__wrapped__=origin))
        bootstrap.setattr(sdk, "invoke", stop)
        with pytest.raises(BeforeUnit):
            F.passed.__wrapped__(tmp_path, monkeypatch)
    ws = tmp_path / "state/workorders/WO-CONTROL-SOURCE/workspace"
    PC.save_original(ws, LL, (ws / LL).read_bytes())
    quote = O.SWR
    cited = [O.DECLARATION] if getattr(request, "param", "") == "cited" else []
    if cited:
        defects.integrity(ws, [ws / O.DECLARATION], [])  # exact protected CONTROL snapshot, no execution verdict
    defect = defects.report(ws, detected_phase="SWE.4", reported_by="swe4-author", kind="CODE",
        summary="CONTROL UT-021 USPEC-HAL-04-03: " + LL + " writes reserved bits as1 with ~EWIF contrary to SWR-034.",
        requirement_ids=["SWR-034"], test_files=cited, evidence_refs=[LL + ":3"], requirement_quote=quote)
    assert defects.take_upstream(ws, "SWE.3")[0]["id"] == defect["id"]
    auth = Authorizer(Binding("CONTROL", str(ws), {"a": {"role": "swe3-author", "phase": "SWE.3"}}))
    assert auth.decide("a", "write_file", {"path": LL, "content": "CONTROL"}).allow
    path = ws / LL
    path.write_text(path.read_text().replace("x->SR = ~WWDG_SR_EWIF", "x->SR = 0U"))
    assert PC.findings(ws) == []
    F.pass_control(Store(ws), "SWE.3")
    baseline = Store(ws).latest_baseline("SWE.3")
    assert defects.mark_fixed(ws, "SWE.3", baseline["baseline_id"]) == [defect["id"]]
    return ws


def execute(ws, monkeypatch, *, phase="SWE.4", operation=U.OPERATIONS[0], server="forge-tests-mcp", args=None):
    with monkeypatch.context() as context:
        for key, value in {"FORGE_MCP_TRUST": "env", "FORGE_ROLE": "swe" + phase[-1] + "-author", "FORGE_PHASE": phase,
                           "FORGE_WORKSPACE": str(ws), "FORGE_RUN_ID": "CONTROL-NOT-LIVE"}.items():
            context.setenv(key, value)
        return sdk.invoke(server, operation, args if args is not None else {"coverage": False})


def files(ws):
    return {p.relative_to(ws).as_posix(): sha256_file(p) for p in ws.rglob("*") if p.is_file() and ".git" not in p.parts}


def test_effective_identity_validates_frozen_normal_chain_without_writing(corrected):
    ws = corrected
    before = files(ws)
    identity = I.effective_identity(ws, LL)
    assert identity["original_sha256"] != identity["effective_sha256"]
    assert identity["approval"]["defects"][0]["fixed_event"]["baseline_id"] == Store(ws).latest_baseline("SWE.3")["baseline_id"]
    report = json.loads((ws / PC.REPORT_JSON).read_text())
    assert report["files"][0]["reasons"][0]["status"] == "IN_FIX"
    assert files(ws) == before


@actual
def test_real_public_target_verification_and_verified_progression_are_stable(corrected, monkeypatch):
    ws = corrected
    before = I.effective_identity(ws, LL)
    frozen_report = (ws / PC.REPORT_JSON).read_bytes()
    result = execute(ws, monkeypatch)
    assert result["status"] == "PASS", result
    assert O.verify(ws, result)[0]["observed"]["sr_reserved_write_values_valid"] is True
    assert defects.verify_on_freeze(ws, "SWE.4") == []
    assert defects.all_defects(ws)[0]["status"] == "VERIFIED"
    assert I.effective_identity(ws, LL) == before
    assert (ws / PC.REPORT_JSON).read_bytes() == frozen_report
    assert O.verify(ws, result)[0]["status"] == "PASS"
    legacy = json.loads(json.dumps(result))
    frame = json.loads(T._artifact(ws, legacy["artifact_refs"], legacy["metrics"][O.METRIC], "json"))
    frame["schema"] = "forge-c/swe4-target-observation-proof/2"
    ctx = sdk.ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "CONTROL")
    ref = ctx.store(canonical_json(frame), "json")
    legacy["artifact_refs"].append(ref)
    legacy["metrics"][O.METRIC] = ref
    with pytest.raises(O.ObservationError, match="PROOF_VERSION_UNSUPPORTED"):
        O.verify(ws, legacy)


@actual
def test_real_LL_RAM_backend_executes_reviewed_corrected_LL(corrected, monkeypatch):
    ws = corrected
    (ws / O.DECLARATION).unlink()  # separate host-only CONTROL, no target claim
    write(ws, "software/tests/unit/test_reviewed.cpp", P.MARKER + '\n#include <gtest/gtest.h>\nextern "C" {\n'
          '#include "stm32n6xx_hal_wwdg.h"\n}\nTEST(ReviewedLL, UT_099) { WWDG->SR=1U; '
          'EXPECT_EQ(HAL_WWDG_ClearEarlyWakeupFlag(),HAL_OK); EXPECT_EQ(WWDG->SR,0U); }\n')
    result = execute(ws, monkeypatch)
    assert result["status"] == "PASS", result
    binding_path = next((ws / "build/tests-unit/test_reviewed").rglob("binding.json"))
    binding = json.loads(binding_path.read_text())
    assert binding["provided_effective_identity"] == [I.effective_identity(ws, LL)]
    assert binding["target_or_hil_claim"] is False


def test_rejected_missing_stale_forged_and_unlinked_controls_refuse(corrected):
    ws = corrected
    base = I.effective_identity(ws, LL)
    for rel, kind in ((LL, "append"), (PC.ORIGINALS + "/" + LL, "append"),
        ("workproducts/SWE.1/software_requirements.md", "append"), (PC.REPORT_JSON, "append"),
        ("inspection/SWE.3/INS-SWE.3-002.json", "role"), (".forge-run/defects/DEF-001.json", "rejected"),
        (".forge-run/defects/DEF-001.json", "baseline"), (".forge-run/defects/DEF-001.json", "ordering"),
        (".forge-run/defects/DEF-001.json", "missing")):
        path = ws / rel
        old = path.read_bytes()
        if kind == "append":
            path.chmod(0o644)
            path.write_bytes(old + b"\nCHANGED\n")
        elif kind == "missing":
            path.unlink()
        else:
            value = json.loads(old)
            if kind == "role":
                value["inspector_role"] = "swe3-author"
            elif kind == "rejected":
                value["status"] = "REJECTED"
            elif kind == "baseline":
                value["history"][-1]["baseline_id"] = "BL-SWE.3-999"
            else:
                value["history"][-1]["ts"] = "2000-01-01T00:00:00Z"
            path.write_text(json.dumps(value))
        with pytest.raises((I.ProvidedIdentityError, ValueError, KeyError)):
            I.effective_identity(ws, LL)
        path.write_bytes(old)
        assert I.effective_identity(ws, LL) == base
    header = ws / LL
    raw = header.read_bytes()
    header.unlink()
    outside = ws.parent / "outside.h"
    outside.write_bytes(raw)
    header.symlink_to(outside)
    with pytest.raises(I.ProvidedIdentityError, match="SYMLINK"):
        I.effective_identity(ws, LL)


def test_report_alone_or_verified_string_cannot_authorize_corrected_input(corrected):
    ws = corrected
    record = ws / ".forge-run/defects/DEF-001.json"
    value = json.loads(record.read_text())
    value["status"] = "VERIFIED"
    write(ws, record.relative_to(ws).as_posix(), value)
    with pytest.raises(I.ProvidedIdentityError, match="HISTORY_INVALID"):
        I.effective_identity(ws, LL)


def test_additional_independent_review_retains_exact_original_fix_approval(corrected):
    ws = corrected
    before = I.effective_identity(ws, LL)
    F.pass_control(Store(ws), "SWE.3")  # same baseline, a later independent inspection record
    after = I.effective_identity(ws, LL)
    assert before["approval"]["defects"] == after["approval"]["defects"]
    assert before["approval"]["phase3_inspection_sha256"] != after["approval"]["phase3_inspection_sha256"]


@pytest.mark.parametrize("missing", ["baseline", "inspection"])
def test_gate_pass_cannot_replace_missing_actual_approval_records(corrected, monkeypatch, missing):
    ws = corrected
    gate = Store.gate
    monkeypatch.setattr(Store, "gate", lambda self, phase: {"decision": "PASS"}
                        if phase == "SWE.3" else gate(self, phase))
    root, pattern = (("configuration/baselines/SWE.3", "BL-*.json") if missing == "baseline"
                     else ("inspection/SWE.3", "INS-*.json"))
    for path in (ws / root).glob(pattern):
        path.unlink()
    with pytest.raises(I.ProvidedIdentityError, match="INDEPENDENT_PHASE_APPROVAL_MISSING:SWE.3"):
        I.effective_identity(ws, LL)


def test_vendor_dependencies_remain_original_strict_despite_LL_approval(corrected):
    ws = corrected
    path = ws / "inputs/vendor/include/stm32n6xx.h"
    path.write_text(path.read_text() + "\n/* changed vendor dependency */\n")
    with pytest.raises(ValueError, match="TARGET_TIMING_APPROVED_INPUT_CHANGED"):
        T._approved_inputs(ws)
    with pytest.raises(ValueError, match="PROVIDED_BUILD_INPUT_CHANGED"):
        P.headers(ws)


@pytest.mark.parametrize("rel", [".forge-run/defects/DEF-001.json", "configuration/baselines/SWE.3/BL-SWE.3-002.json",
                                  "inspection/SWE.3/INS-SWE.3-002.json"])
def test_selected_approval_context_cannot_be_symlinked_even_with_identical_bytes(corrected, rel):
    ws = corrected
    path = ws / rel
    outside = ws.parent / "context.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(I.ProvidedIdentityError, match="SYMLINK"):
        I.effective_identity(ws, LL)


def test_normal_report_refreeze_binds_exact_historical_fix_and_fresh_current_approval(corrected):
    ws = corrected
    before = I.effective_identity(ws, LL)
    hal = ws / "software/hal/stm32n6xx_hal_wwdg.c"
    hal.write_text(hal.read_text() + "\n/* CONTROL new HAL baseline, identical provided LL correction. */\n")
    assert PC.findings(ws) == []  # normal author path: current CODE reason is now FIXED
    F.pass_control(Store(ws), "SWE.3")
    assert Store(ws).gate("SWE.3")["decision"] == "PASS"
    after = I.effective_identity(ws, LL)
    assert before["approval"]["defects"] == after["approval"]["defects"]
    assert before["approval"]["phase3_baseline_sha256"] != after["approval"]["phase3_baseline_sha256"]
    # Reusing the old closed CODE for a NEW LL hunk is never authorized by a regenerated report/review.
    path = ws / LL
    path.write_text(path.read_text().replace("x->SR = 0U", "x->SR = WWDG_SR_EWIF"))
    assert PC.findings(ws) == []  # the older report filter alone is intentionally insufficient authority
    F.pass_control(Store(ws), "SWE.3")
    with pytest.raises(I.ProvidedIdentityError, match="HISTORICAL_EFFECTIVE_CODE_CHANGED"):
        I.effective_identity(ws, LL)


@actual
def test_normal_corrected_copy_resume_then_real_target_and_multihop_trace(corrected, monkeypatch):
    src = corrected
    before = files(src)
    dst, manifest = F.destination(src, "WO-CONTROL-REVIEWED4")
    assert W.resume_from(dst, manifest, "WO-CONTROL-SOURCE") == ["SWE.4", "SWE.5", "SWE.6"]
    assert I.effective_identity(dst, LL) == I.effective_identity(src, LL)
    assert json.loads((dst / ".forge-run/manifest.json").read_text())["provided"] == manifest["provided"]
    # Fresh CONTROL author inputs in phase4, not carried as an already-passed phase.
    for rel in ("workproducts/SWE.4/unit_test_plan.json", "workproducts/SWE.4/unit_verification_report.md",
                O.DECLARATION, "software/tests/unit/test_control.c"):
        path = dst / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, path)
    result = execute(dst, monkeypatch)
    assert result["status"] == "PASS", result
    assert defects.verify_on_freeze(dst, "SWE.4") == []
    F.pass_control(Store(dst), "SWE.4")
    F.git(dst, "add", "-A")
    F.git(dst, "-c", "user.name=CONTROL", "-c", "user.email=control@example.invalid", "commit", "-qm", "CONTROL")
    next_ws, next_man = F.destination(dst, "WO-CONTROL-REVIEWED5")
    assert W.resume_from(next_ws, next_man, "WO-CONTROL-REVIEWED4") == ["SWE.5", "SWE.6"]
    assert C.trace(next_ws, O)[1:] == ({"UT-021": "PASS"}, [])
    report = swtrace.build_all(next_ws, upto="SWE.5", render=False, doxygen=False, export=False, write=set())
    assert report["findings"]["SWE.4"] == [], report
    write(next_ws, "software/tests/integration/test_control.c", "int main(void) { return 0; }\n")
    write(next_ws, "software/tests/target/test_control.c", O.harness())
    write(next_ws, "workproducts/SWE.5/integration_verification_report.md", "# CONTROL\nActual host and target tools.\n")
    assert execute(next_ws, monkeypatch, phase="SWE.5", operation=U.OPERATIONS[1])["status"] == "PASS"
    assert execute(next_ws, monkeypatch, phase="SWE.5", operation=sim.OPERATIONS[0], server="forge-sim-mcp", args={})["status"] == "PASS"
    F.pass_control(Store(next_ws), "SWE.5")
    final, last = F.destination(next_ws, "WO-CONTROL-REVIEWED6")
    assert W.resume_from(final, last, "WO-CONTROL-REVIEWED5") == ["SWE.6"]
    assert C.trace(final, O)[1:] == ({"UT-021": "PASS"}, [])
    assert files(src) == before


@actual
@pytest.mark.parametrize("corrected", ["cited"], indirect=True)
def test_normal_restored_test_reverification_receipt_and_resume(corrected, monkeypatch):
    ws = corrected
    before = I.effective_identity(ws, LL)
    original_report = (ws / PC.REPORT_JSON).read_bytes()
    declared = ws / O.DECLARATION
    declared.write_text(json.dumps(O.CASE, sort_keys=True, indent=4))
    assert defects.verify_on_freeze(ws, "SWE.4") == []  # actual normal restored-test handler, no mock
    defect = defects.all_defects(ws)[0]
    assert defect["status"] == "VERIFIED" and defect["history"][-1]["tools"] == ["gate-reverify"]
    ref = defect["history"][-1]["reverify_receipt"]
    receipt = ws / ref["path"]
    frame = json.loads(receipt.read_text())
    assert frame["status"] == "PASS" and frame["tools"][0]["result"]["metrics"]["observation_ut_passed"] == 1
    assert I.effective_identity(ws, LL) == before and (ws / PC.REPORT_JSON).read_bytes() == original_report
    raw = receipt.read_bytes()
    receipt.chmod(0o644)
    receipt.write_bytes(raw + b"changed")
    with pytest.raises(I.ProvidedIdentityError, match="RECEIPT_CHANGED"):
        I.effective_identity(ws, LL)
    receipt.write_bytes(raw)
    artifact = I.artifact_paths(ws, frame["tools"][0]["result"]["artifact_refs"])[0]
    old_artifact = artifact.read_bytes()
    artifact.write_bytes(old_artifact + b"changed")
    with pytest.raises(I.ProvidedIdentityError, match="ARTIFACT_CHANGED"):
        I.effective_identity(ws, LL)
    artifact.write_bytes(old_artifact)
    record = ws / ".forge-run/defects/DEF-001.json"
    raw_record = record.read_bytes()
    value = json.loads(raw_record)
    del value["history"][-1]["reverify_receipt"]
    record.write_text(json.dumps(value))
    with pytest.raises(I.ProvidedIdentityError, match="RECEIPT_UNBOUND"):
        I.effective_identity(ws, LL)
    record.write_bytes(raw_record)
    assert I.effective_identity(ws, LL) == before
    # A later, independently approved HAL baseline cannot rewrite historical
    # test/code evidence or borrow its phase PASS. The exact LL correction is unchanged.
    hal = ws / "software/hal/stm32n6xx_hal_wwdg.c"
    hal.write_text(hal.read_text() + "\n/* CONTROL new HAL baseline after historical restored-test verification. */\n")
    assert PC.findings(ws) == []
    F.pass_control(Store(ws), "SWE.3")
    current = I.effective_identity(ws, LL)
    assert current["approval"]["defects"] == before["approval"]["defects"]
    assert current["approval"]["phase3_baseline_sha256"] != before["approval"]["phase3_baseline_sha256"]
    before = current
    # The corrected LL approval travels without pretending the unpassed phase4
    # test is a new result. Cited bytes and receipt stay protected context only.
    dst, manifest = F.destination(ws, "WO-CONTROL-REVERIFIED4")
    assert W.resume_from(dst, manifest, "WO-CONTROL-SOURCE") == ["SWE.4", "SWE.5", "SWE.6"]
    assert not (dst / O.DECLARATION).exists()
    assert I.effective_identity(dst, LL) == before
    for rel in ("workproducts/SWE.4/unit_test_plan.json", "workproducts/SWE.4/unit_verification_report.md",
                O.DECLARATION, "software/tests/unit/test_control.c"):
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ws / rel, target)
    actual_result = execute(dst, monkeypatch)
    assert actual_result["status"] == "PASS", actual_result
    F.pass_control(Store(dst), "SWE.4")
    F.git(dst, "add", "-A")
    F.git(dst, "-c", "user.name=CONTROL", "-c", "user.email=control@example.invalid", "commit", "-qm", "CONTROL")
    phase5, man = F.destination(dst, "WO-CONTROL-REVERIFIED5")
    assert W.resume_from(phase5, man, "WO-CONTROL-REVERIFIED4") == ["SWE.5", "SWE.6"]
    assert C.trace(phase5, O)[1:] == ({"UT-021": "PASS"}, [])


@actual
def test_actual_CRC_timing_reexecutes_same_cases_after_reviewed_LL_correction(tmp_path, monkeypatch):
    original_pass = F.pass_control
    clause = "When a valid initialization is requested, the CRC driver shall accept the configuration."

    class BeforeUnit(Exception):
        pass

    def construct(store, phase):
        ws = store.workspace
        if phase == "SWE.1":
            write(ws, swtrace.REQS, "- **SWR-001** " + clause + "\n")
            F.add_reqif(ws)
            ll = ws / "software/ll/stm32n6xx_ll_crc.h"
            ll.write_text(ll.read_text().replace("static inline void LL_CRC_Control(void) { }",
                "#include <stdint.h>\nstatic inline uint32_t LL_CRC_Control(void) { return 0U; }"))
            source = ws / "software/hal/stm32n6xx_hal_crc.c"
            source.write_text(source.read_text().replace('#include "stm32n6xx_hal_crc.h"',
                '#include "stm32n6xx_hal_crc.h"\n#include "stm32n6xx_ll_crc.h"').replace(
                "return config->polynomial & 1U ? HAL_OK : HAL_ERROR;",
                "return ((config->polynomial & 1U) && LL_CRC_Control() == 1U) ? HAL_OK : HAL_ERROR;"))
            manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
            rel = ll.relative_to(ws).as_posix()
            manifest.update(provided=[{"path": rel, "role": "provided_ll_driver", "sha256": sha256_file(ll)}],
                            unit_verification="uspec-gtest-v1", hal_unit_isolation="ll-fake-v1")
            write(ws, ".forge-run/manifest.json", manifest)
            PC.save_original(ws, rel, ll.read_bytes())  # fresh CONTROL approval, before any execution
        original_pass(store, phase)

    def stop(*args, **kwargs):
        raise BeforeUnit

    with monkeypatch.context() as bootstrap:
        bootstrap.setattr(F, "pass_control", construct)
        bootstrap.setattr(sdk, "invoke", stop)
        with pytest.raises(BeforeUnit):
            F.test_actual_crc_timing_carries_with_normal_passed_phase_contract(tmp_path, monkeypatch)
    ws = tmp_path / "state/workorders/WO-CONTROL-CRC/workspace"
    rel = "software/ll/stm32n6xx_ll_crc.h"
    manifest = (ws / ".forge-run/manifest.json").read_bytes()
    declaration = (ws / T.DECLARATION).read_bytes()
    failing = execute(ws, monkeypatch)
    assert failing["status"] == "FAIL" and T.verify(ws, failing)[0]["status"] == "FAIL"
    defect = defects.report(ws, detected_phase="SWE.4", reported_by="swe4-author", kind="CODE",
        summary="CONTROL UT-001 USPEC-HAL-01-07: " + rel + " returns0 and rejects the specified valid initialization.",
        requirement_ids=["SWR-001"], test_files=[T.DECLARATION], evidence_refs=[rel + ":4"], requirement_quote=clause)
    assert defects.take_upstream(ws, "SWE.3")[0]["id"] == defect["id"]
    auth = Authorizer(Binding("CONTROL", str(ws), {"a": {"role": "swe3-author", "phase": "SWE.3"}}))
    assert auth.decide("a", "write_file", {"path": rel, "content": "CONTROL"}).allow
    path = ws / rel
    path.write_text(path.read_text().replace("return 0U;", "return 1U;"))
    assert PC.findings(ws) == []
    F.pass_control(Store(ws), "SWE.3")
    assert defects.mark_fixed(ws, "SWE.3", Store(ws).latest_baseline("SWE.3")["baseline_id"]) == [defect["id"]]
    result = execute(ws, monkeypatch)
    assert result["status"] == "PASS", result
    assert [t["status"] for t in T.verify(ws, result)] == ["PASS", "PASS", "PASS"]
    assert defects.verify_on_freeze(ws, "SWE.4") == []
    assert [t["status"] for t in T.verify(ws, result)] == ["PASS", "PASS", "PASS"]
    assert (ws / T.DECLARATION).read_bytes() == declaration and (ws / ".forge-run/manifest.json").read_bytes() == manifest
    assert I.effective_identity(ws, rel)["approval"] is not None
    legacy = json.loads(json.dumps(result))
    frame = json.loads(T._artifact(ws, legacy["artifact_refs"], legacy["metrics"][T.METRIC], "json"))
    frame["schema"] = "forge-c/swe4-target-timing-proof/1"
    ctx = sdk.ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "CONTROL")
    ref = ctx.store(canonical_json(frame), "json")
    legacy["artifact_refs"].append(ref)
    legacy["metrics"][T.METRIC] = ref
    with pytest.raises(T.TimingError, match="PROOF_VERSION_UNSUPPORTED"):
        T.verify(ws, legacy)
