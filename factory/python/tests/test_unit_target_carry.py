"""Private deterministic CONTROL inspections and actual CPU evidence; no model/role qualification.

The observation integration seam here adapts the already-qualified public unit
pipeline without editing either producer or the shared MCP/trace implementations.
"""
import copy
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory import workorder as W
from forge_factory.common import REPO_ROOT, canonical_json, sha256_file, utc_now
from forge_factory.inspection import swtrace
from forge_factory.inspection.engine import PHASES, Store
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import sim
from forge_factory.mcp.servers import tests as U
from forge_factory.workflow import unit_target_carry as C
from forge_factory.workflow import unit_target_observation as O
from forge_factory.workflow import unit_target_timing as T
from test_resume_from import _all_pass
from test_swe2_architecture import add_reqif
from test_unit_target_observation import actual, write
from test_unit_target_observation import ws as observation_ws
from test_unit_target_timing import ws as timing_ws


def git(ws, *args):
    return subprocess.run(["git", *args], cwd=ws, text=True, capture_output=True, check=True).stdout.strip()


def guarded_header(path):
    guard = path.name.upper().replace(".", "_")
    path.write_text(f"#ifndef {guard}\n#define {guard}\n" + path.read_text() + f"#endif /* {guard} */\n")


def pass_control(store, phase):
    """Deterministic synthetic inspector oracle, explicitly NOT a real role qualification."""
    baseline = store.freeze(phase, f"swe{phase[-1]}-author")
    report = store.record_inspection(phase, f"swe{phase[-1]}-inspector", baseline["baseline_id"], _all_pass(phase))
    assert report["verdict"] == "PASS", report
    assert store.gate(phase)["decision"] == "PASS"


@pytest.fixture
def passed(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws = tmp_path / "state/workorders/WO-CONTROL-SOURCE/workspace"
    ws.mkdir(parents=True)
    observation_ws.__wrapped__(ws)
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    revision = git(REPO_ROOT, "rev-parse", "HEAD")
    man.update(work_order="WO-CONTROL-SOURCE", created_at="2026-01-01T00:00:00Z",
               factory_revision={"commit": revision, "dirty": False, "branch": "CONTROL"},
               quality={"purpose": "private deterministic protocol CONTROL"})
    for rel in ("inputs/vendor/include/stm32n6xx.h", "software/ll/stm32n6xx_ll_wwdg.h",
                "software/hal/stm32n6xx_hal_wwdg.h"):
        guarded_header(ws / rel)
    for item in man["provided"] + man["provided_build"]["files"]:
        item["sha256"] = sha256_file(ws / item["path"])
    write(ws, ".forge-run/manifest.json", man)
    write(ws, swtrace.REQS, "- **SWR-033** When clearing is requested, the WWDG driver shall clear its early wakeup flag.\n"
          "- **SWR-034** " + O.SWR + "\n")
    write(ws, "configuration/system_names.json", json.dumps(["WWDG driver"]))
    write(ws, "traceability/requirements_to_tests.csv", "requirement_id,test_id,test_file\nSWR-033,UT-021,target\nSWR-034,UT-021,target\n")
    add_reqif(ws)
    write(ws, "workproducts/SWE.2/software_architecture.md", "# Architecture\n## Components\nHAL, LL\n"
          "## Interfaces\nHAL_WWDG_ClearEarlyWakeupFlag\n## Requirement allocation\n| SWR | Function |\n|---|---|\n"
          "| SWR-033, SWR-034 | HAL_WWDG_ClearEarlyWakeupFlag |\n## Register table\n| Name | Offset |\n|---|---|\n| WWDG_SR | 0x8 |\n")
    write(ws, swtrace.ARCH, '@startuml\ncomponent "stm32n6xx_hal_wwdg" <<SWC>> as SWC_HAL\n'
          'component "stm32n6xx_ll_wwdg" <<SWC>> as SWC_LL\nnote right of SWC_HAL : Allocated: SWR-033, SWR-034\n'
          'SWC_HAL --> SWC_LL : IF-01 clear flag\n@enduml\n')
    write(ws, "workproducts/SWE.2/architecture_dynamic.puml", "@startuml\nparticipant Caller\nparticipant HAL\n"
          "Caller -> HAL : HAL_WWDG_ClearEarlyWakeupFlag()\nHAL --> Caller : HAL_OK\n@enduml\n")
    write(ws, "workproducts/SWE.3/detailed_design.md", "# CONTROL design\nThe HAL delegates to the immutable LL.\n")
    unit = write(ws, swtrace.UNITS_MD, "## SWU-HAL-04: Flag clear\n- SWC: SWC_HAL\n"
                 "- Functions: HAL_WWDG_ClearEarlyWakeupFlag\n- **USPEC-HAL-04-03** " + O.BEHAVIOUR + " Traces: SWR-033, SWR-034\n")
    write(ws, swtrace.DESIGN_DIR + "/SWU-HAL-04.puml", "@startuml\nstart\n:Clear flag through LL;\nstop\n@enduml\n")
    plan = json.loads((ws / "workproducts/SWE.4/unit_test_plan.json").read_text())
    plan["unit_specification"]["sha256"] = sha256_file(unit)
    write(ws, "workproducts/SWE.4/unit_test_plan.json", plan)
    path = ws / "software/hal/stm32n6xx_hal_wwdg.c"
    path.write_text(path.read_text().replace("hal_status_t HAL_", "/** @unit SWU-HAL-04 @spec USPEC-HAL-04-03 */\nhal_status_t HAL_"))
    # A real, obligation-free host executable plus the independently executed target UT.
    write(ws, "software/tests/unit/test_control.c", "int main(void) { return 0; }\n")
    write(ws, "workproducts/SWE.4/unit_verification_report.md", "# CONTROL CPU execution\nActual target output is recorded by run_unit.\n")
    store = Store(ws)
    for phase in PHASES[:3]:
        pass_control(store, phase)
    # The normal SDK performs actual public compilation/execution and appends the ledger.
    with monkeypatch.context() as seam:
        seam.setattr(T, "DECLARATION", O.DECLARATION)
        seam.setattr(T, "declaration", lambda p: {"cases": O.expected_tests(p)})
        seam.setattr(T, "run", O.run)
        for key, value in {"FORGE_MCP_TRUST": "env", "FORGE_ROLE": "swe4-author", "FORGE_PHASE": "SWE.4",
                           "FORGE_WORKSPACE": str(ws), "FORGE_RUN_ID": "CONTROL-NOT-LIVE"}.items():
            seam.setenv(key, value)
        result = sdk.invoke("forge-tests-mcp", U.OPERATIONS[0], {"coverage": False})
    assert result["status"] == "PASS", result
    pass_control(store, "SWE.4")
    assert O.trace(ws)[1] == {"UT-021": "PASS"}
    git(ws, "init", "-q")
    git(ws, "add", "-A")
    git(ws, "-c", "user.name=CONTROL", "-c", "user.email=control@example.invalid", "commit", "-qm", "CONTROL fixture")
    return ws


def destination(src, wo):
    ws = src.parents[1] / wo / "workspace"
    ws.mkdir(parents=True)
    man = copy.deepcopy(json.loads((src / ".forge-run/manifest.json").read_text()))
    man.update(work_order=wo, created_at=utc_now(), input_baseline_commit="CONTROL-NEW-INPUT-COMMIT")
    man.pop("resumed_from", None)
    for rel in ("inputs", "software/ll"):
        if (src / rel).is_dir():
            shutil.copytree(src / rel, ws / rel)
    if (src / "configuration/system_names.json").is_file():
        shutil.copyfile(src / "configuration/system_names.json", write(ws, "configuration/system_names.json", "[]"))
    write(ws, ".forge-run/manifest.json", man)
    git(ws, "init", "-q")
    return ws, man


@actual
def test_actual_normal_resume_preserves_target_evidence_and_second_boundary(passed, monkeypatch):
    before = {p: (REPO_ROOT / "factory/python/forge_factory/workflow" / p).read_bytes()
              for p in ("unit_target_timing.py", "unit_target_observation.py")}
    ws, man = destination(passed, "WO-CONTROL-PHASE5")
    assert W.resume_from(ws, man, "WO-CONTROL-SOURCE") == ["SWE.5", "SWE.6"]
    assert O.trace(ws)[2]  # original producer correctly remains strict
    assert C.trace(ws, O)[1:] == ({"UT-021": "PASS"}, [])
    man["phase_scope"] = {"stop_after": "SWE.5"}
    write(ws, ".forge-run/manifest.json", man)
    assert C.trace(ws, O)[2]  # unsealed destination metadata never accepted
    C.seal_after_setup(ws)
    assert C.trace(ws, O)[1:] == ({"UT-021": "PASS"}, [])
    # Exercise the full real trace builder through the proposed shared integration seam.
    timing = SimpleNamespace(trace=T.trace, METRIC=T.METRIC)
    def traces(path):
        a, b, c = C.trace(path, timing)
        x, y, z = C.trace(path, O)
        return a + x, {**b, **y}, c + z
    with monkeypatch.context() as seam:
        seam.setattr(T, "trace", traces)
        report = swtrace.build_all(ws, render=False, doxygen=False, upto="SWE.5", write=set(), export=False)
    assert report["findings"]["SWE.4"] == [], report
    # Real CPU integration tools plus the explicitly synthetic independent
    # inspection oracle make the next normal resume advance to SWE.6.
    write(ws, "software/tests/integration/test_control.c", "int main(void) { return 0; }\n")
    write(ws, "software/tests/target/test_control.c", O.harness())
    write(ws, "workproducts/SWE.5/integration_verification_report.md", "# Private CONTROL\nActual host and target tools only.\n")
    with monkeypatch.context() as control:
        for key, value in {"FORGE_MCP_TRUST": "env", "FORGE_ROLE": "swe5-author", "FORGE_PHASE": "SWE.5",
                           "FORGE_WORKSPACE": str(ws), "FORGE_RUN_ID": "CONTROL-NOT-LIVE"}.items():
            control.setenv(key, value)
        host = sdk.invoke("forge-tests-mcp", U.OPERATIONS[1], {"coverage": False})
        target = sdk.invoke("forge-sim-mcp", sim.OPERATIONS[0], {})
    assert host["status"] == target["status"] == "PASS", (host, target)
    assert Store(ws).missing_outputs("SWE.5") == []
    pass_control(Store(ws), "SWE.5")
    nxt, nextman = destination(ws, "WO-CONTROL-PHASE6")
    assert W.resume_from(nxt, nextman, "WO-CONTROL-PHASE5") == ["SWE.6"]
    nextman["phase_scope"] = {"stop_after": "SWE.6"}
    write(nxt, ".forge-run/manifest.json", nextman)
    C.seal_after_setup(nxt)
    assert C.trace(nxt, O)[1:] == ({"UT-021": "PASS"}, [])
    original = json.loads((nxt / C.PATH).read_text())["entries"][O.METRIC]
    assert original["creator_work_order"] == "WO-CONTROL-SOURCE"
    assert all((REPO_ROOT / "factory/python/forge_factory/workflow" / p).read_bytes() == raw for p, raw in before.items())


@actual
def test_copied_declaration_or_untrusted_receipt_never_creates_pass(passed):
    ws, man = destination(passed, "WO-CONTROL-REFUSALS")
    W.resume_from(ws, man, "WO-CONTROL-SOURCE")
    assert C.trace(ws, O)[1] == {"UT-021": "PASS"}
    receipt_path = ws / C.PATH
    receipt = receipt_path.read_bytes()
    receipt_path.unlink()
    assert C.trace(ws, O)[1] == {}  # copied evidence + self-asserted resumed_from is insufficient
    receipt_path.write_bytes(receipt.replace(b"WO-CONTROL-SOURCE", b"WO-CONTROL-FORGED"))
    assert "RECEIPT_CHANGED_AFTER_NORMAL_COMMIT" in C.trace(ws, O)[2][0]
    receipt_path.write_bytes(receipt)
    # Each changed current input must fail; a fresh legitimate run would be needed.
    for root, rel in ((ws, "software/hal/stm32n6xx_hal_wwdg.c"),
                      (ws, "software/ll/stm32n6xx_ll_wwdg.h"),
                      (ws, "inputs/vendor/include/stm32n6xx.h"),
                      (ws, O.DECLARATION), (ws, swtrace.REQS), (ws, swtrace.UNITS_MD),
                      (passed, "inspection/SWE.4/INS-SWE.4-001.json"),
                      (passed, ".forge-run/manifest.json")):
        path = root / rel
        original = path.read_bytes()
        path.write_bytes(original + b"\nCHANGED\n")
        assert C.trace(ws, O)[1] == {}, rel
        path.write_bytes(original)
        assert C.trace(ws, O)[1] == {"UT-021": "PASS"}, rel
    vendor = ws / "inputs/vendor/include"
    vendor.rename(vendor.with_name("saved-include"))
    vendor.symlink_to(vendor.with_name("saved-include"), target_is_directory=True)
    assert C.trace(ws, O)[1] == {}  # copied private views cannot hide symlinked original parents
    vendor.unlink()
    vendor.with_name("saved-include").rename(vendor)
    ledger = ws / "evidence/tool-results.jsonl"
    original = ledger.read_bytes()
    latest = json.loads(original.splitlines()[-1])
    latest["result"] = {"status": "FAIL", "metrics": {}, "artifact_refs": []}
    ledger.write_bytes(original + json.dumps(latest).encode() + b"\n")
    assert C.trace(ws, O)[1] == {}  # no stale success after later failed/unbound verification


@pytest.mark.parametrize("field,value", [("quality", {"weaker": True}), ("budgets", {"flash_bytes": 999}),
    ("unknown_future_contract", True), ("local_profile", {"model": "OTHER"}),
    ("simulation_performance", {"instructions_per_call": 999999}), ("provided", [])])
def test_every_semantic_or_unknown_manifest_field_remains_bound(tmp_path, field, value):
    original = {"work_order": "WO-A", "factory_revision": {"commit": "a" * 40, "dirty": False}}
    current = copy.deepcopy(original)
    current.update(work_order="WO-B", **{field: value})
    with pytest.raises(C.CarryRefused, match="SEMANTIC_CONTRACT_CHANGED"):
        C._compatible(original, current, tmp_path)


def registry_control(path, creator, consumer):
    """Normal DB schema with explicit deterministic CONTROL records, never a live CRE qualification claim."""
    from forge_factory.reliability.policy import load
    from forge_factory.reliability.promotion import tree_sha256
    from forge_factory.reliability.store import CREStore

    store = CREStore(path)
    row = {"schema_version": "1.0", "decision_id": "pd-" + "1" * 20,
           "candidate_sha256": tree_sha256(consumer), "baseline_sha256": tree_sha256(creator),
           "policy_sha256": load().sha256, "benchmark_sha256": "a" * 64,
           "decision": "ELIGIBLE_FOR_OFFLINE_REVIEW", "evaluator_id": "CONTROL-NOT-LIVE-QUALIFICATION",
           "evaluator_kind": "INDEPENDENT_DETERMINISTIC_RUNNER", "evaluated_at": utc_now(),
           "allowed_auto_deployment": False, "reasons": ["CONTROL FIXTURE ONLY"],
           "hard_gates": [{"name": n, "result": "PASS", "evidence_refs": ["CONTROL"]} for n in (
               "protected_files", "policy_integrity", "reproducer", "prevention", "quality_process", "golden_benchmark", "holdout")]}
    with store.conn() as db:
        db.execute("INSERT INTO cre_promotion_decisions VALUES (?,?,?,?,?,?)",
                   (row["decision_id"], consumer, creator, row["decision"], canonical_json(row).decode(), utc_now()))
    return {"registry_path": str(path), "decision_id": row["decision_id"]}


def test_exact_readonly_appendonly_registry_migration_and_refusals(tmp_path):
    creator, consumer = git(REPO_ROOT, "rev-parse", "HEAD~1"), git(REPO_ROOT, "rev-parse", "HEAD")
    ws = tmp_path / "workspace"
    ws.mkdir()
    ref = registry_control(tmp_path / "authority.sqlite3", creator, consumer)
    original = {"work_order": "WO-A", "factory_revision": {"commit": creator, "dirty": False}}
    current = {"work_order": "WO-B", "factory_revision": {"commit": consumer, "dirty": False}}
    with pytest.raises(C.CarryRefused, match="REVISION_CHANGE_UNQUALIFIED"):
        C._compatible(original, current, ws)
    assert C._compatible(original, current, ws, ref)["reference"] == ref
    for bad in ({**ref, "decision_id": "pd-" + "2" * 20}, {**ref, "record": {}},
                {**ref, "registry_path": str(ws / "fake.sqlite3")}):
        with pytest.raises((C.CarryRefused, sqlite3.Error)):
            C._compatible(original, current, ws, bad)
    with pytest.raises(C.CarryRefused, match="NOT_EXACT_ELIGIBLE"):
        C._promotion(ref, consumer, creator, ws)
    dbpath = Path(ref["registry_path"])
    dbpath.chmod(0o666)
    with pytest.raises(C.CarryRefused, match="REGISTRY_UNTRUSTED"):
        C._compatible(original, current, ws, ref)
    dbpath.chmod(0o600)
    with sqlite3.connect(dbpath) as db:
        db.execute("DROP TRIGGER cre_promotion_decisions_no_update")
    with pytest.raises(C.CarryRefused, match="MISSING_OR_MUTABLE"):
        C._compatible(original, current, ws, ref)


def test_reference_file_cannot_import_decision_or_unbounded_data(tmp_path):
    path = tmp_path / "ref.json"
    ref = {"registry_path": str(tmp_path / "authority.sqlite3"), "decision_id": "pd-" + "1" * 20}
    path.write_text(json.dumps(ref))
    assert C.promotion_reference(path) == ref
    for text in (json.dumps({**ref, "decision": "ELIGIBLE_FOR_OFFLINE_REVIEW"}), "x" * 4097, "{broken"):
        path.write_text(text)
        with pytest.raises(C.CarryRefused):
            C.promotion_reference(path)


@actual
def test_actual_crc_timing_carries_with_normal_passed_phase_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws = tmp_path / "state/workorders/WO-CONTROL-CRC/workspace"
    ws.mkdir(parents=True)
    timing_ws.__wrapped__(ws)
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    man.update(work_order="WO-CONTROL-CRC", created_at="2026-01-01T00:00:00Z",
               factory_revision={"commit": git(REPO_ROOT, "rev-parse", "HEAD"), "dirty": False, "branch": "CONTROL"})
    write(ws, swtrace.REQS, "- **SWR-001** When a calculation is requested, the CRC driver shall calculate the checksum.\n")
    write(ws, "traceability/requirements_to_tests.csv", "requirement_id,test_id,test_file\nSWR-001,UT-001,target\n")
    add_reqif(ws)
    write(ws, "workproducts/SWE.2/software_architecture.md", "# Architecture\n## Components\nHAL, LL\n"
          "## Interfaces\n" + ", ".join(T.FUNCTIONS) + "\n## Requirement allocation\n| SWR | Function |\n|---|---|\n"
          "| SWR-001 | " + ", ".join(T.FUNCTIONS) + " |\n## Register table\n| Name | Offset |\n|---|---|\n| CRC_DR | 0x0 |\n")
    write(ws, swtrace.ARCH, '@startuml\ncomponent "stm32n6xx_hal_crc" <<SWC>> as SWC_HAL\n'
          'component "stm32n6xx_ll_crc" <<SWC>> as SWC_LL\nnote right of SWC_HAL : Allocated: SWR-001\n'
          'SWC_HAL --> SWC_LL : IF-01 checksum\n@enduml\n')
    write(ws, "workproducts/SWE.2/architecture_dynamic.puml", "@startuml\nparticipant Caller\nparticipant HAL\n"
          "Caller -> HAL : HAL_CRC_Init()\nHAL --> Caller : HAL_OK\n@enduml\n")
    write(ws, "workproducts/SWE.3/detailed_design.md", "# Private CONTROL timing\nFinite target calls.\n")
    ll = write(ws, "software/ll/stm32n6xx_ll_crc.h", "#define LL_CRC_DR_OFFSET 0x0U\nstatic inline void LL_CRC_Control(void) { }\n")
    guarded_header(ll)
    guarded_header(ws / "software/hal/stm32n6xx_hal_crc.h")
    section = write(ws, "inputs/sections/RM0486/CRC_DR.md", "#### CRC data register (CRC_DR)\nAddress offset: 0x0\n")
    man["inputs"] = [{"path": section.relative_to(ws).as_posix(), "sha256": sha256_file(section), "role": "reference"}]
    write(ws, ".forge-run/manifest.json", man)
    source = ws / "software/hal/stm32n6xx_hal_crc.c"
    text = source.read_text()
    for n, function in enumerate(T.FUNCTIONS, 1):
        text = text.replace("hal_status_t " + function, f"/** @unit SWU-HAL-{n:02d} @spec USPEC-HAL-{n:02d}-07 */\nhal_status_t " + function)
    source.write_text(text)
    for n in range(1, 4):
        write(ws, swtrace.DESIGN_DIR + f"/SWU-HAL-{n:02d}.puml", "@startuml\nstart\n:Finite call;\nstop\n@enduml\n")
    write(ws, "software/tests/unit/test_control.c", "int main(void) { return 0; }\n")
    write(ws, "workproducts/SWE.4/unit_verification_report.md", "# Private CONTROL\nActual finite target calls.\n")
    store = Store(ws)
    for phase in PHASES[:3]:
        pass_control(store, phase)
    with monkeypatch.context() as control:
        for key, value in {"FORGE_MCP_TRUST": "env", "FORGE_ROLE": "swe4-author", "FORGE_PHASE": "SWE.4",
                           "FORGE_WORKSPACE": str(ws), "FORGE_RUN_ID": "CONTROL-NOT-LIVE"}.items():
            control.setenv(key, value)
        output = sdk.invoke("forge-tests-mcp", U.OPERATIONS[0], {"coverage": False})
    assert output["status"] == "PASS", output
    pass_control(store, "SWE.4")
    git(ws, "init", "-q")
    git(ws, "add", "-A")
    git(ws, "-c", "user.name=CONTROL", "-c", "user.email=control@example.invalid", "commit", "-qm", "CONTROL")
    dst, current = destination(ws, "WO-CONTROL-CRC5")
    assert W.resume_from(dst, current, "WO-CONTROL-CRC") == ["SWE.5", "SWE.6"]
    assert C.trace(dst, T)[1:] == ({"UT-001": "PASS", "UT-002": "PASS", "UT-003": "PASS"}, [])
    adapter = SimpleNamespace(trace=T.trace, METRIC=T.METRIC)
    with monkeypatch.context() as seam:
        seam.setattr(T, "trace", lambda p: C.trace(p, adapter))
        report = swtrace.build_all(dst, render=False, doxygen=False, upto="SWE.5", write=set(), export=False)
    assert report["findings"]["SWE.4"] == [], report
