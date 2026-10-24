"""Feature 012: real baseline/inspection hashes, isolated intake stores and shared resume budgets."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest
from brownfield_fixtures import example_copy
from forge_factory import workorder as WO
from forge_factory.brownfield import resume as R
from forge_factory.brownfield.inject import inject
from forge_factory.common import pretty_json, sha256_file
from forge_factory.inspection.engine import PHASES, Store
from test_resume_from import _all_pass
from test_swe2_architecture import ARCH_MIN, add_reqif, add_views


def write(ws, rel, data):
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else pretty_json(data))


def save(ws, man):
    write(ws, ".forge-run/manifest.json", man)


@pytest.fixture()
def pair(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    monkeypatch.setattr(WO, "factory_revision", lambda: {"commit": "1" * 40, "dirty": False})
    # Compatibility drift is tested separately; avoid hashing the full host toolchain in every fixture.
    monkeypatch.setattr(R, "runtime_identity", lambda: {"factory_assets_sha256": "a" * 64, "tools": {"clang": "pinned"}})
    monkeypatch.setattr("forge_factory.fabro.client.client_for_workspace",
                        lambda *a, **kw: Mock(get_run=lambda rid: {"lifecycle": {"status": {"kind": "succeeded"}}}))
    ex = example_copy(tmp_path)

    def prepare(wo):
        ws, man = WO.prepare(ex, wo)
        # A minimal native checklist fixture; no mocked gate/PASS predicate.
        man["trace_profile"] = None
        man["register_contract"] = None
        R.initialize(ws, man)
        save(ws, man)
        return ws, man

    src, old = prepare("WO-SRC")
    write(src, "workproducts/SWE.1/software_requirements.md",
          "- **SWR-001** When enable is requested, the RCC driver shall set the clock enable bit.\n")
    write(src, "traceability/requirements_to_tests.csv", "requirement_id,test_id,test_file\nSWR-001,UT-001,t.c\n")
    add_reqif(src)
    store = Store(src)
    bl = store.freeze("SWE.1", "swe1-author")
    record = store.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], _all_pass("SWE.1"))
    assert record["verdict"] == "PASS", record
    assert inject(src)["status"] == "INJECTED"
    write(src, ".forge-run/fabro_run_id", "test-run-id")
    dst, new = prepare("WO-DST")
    return src, old, dst, new, prepare, ex


def test_resume_reuses_passed_swe1_and_injects_own_delivery(pair):
    src, old, dst, new, _, _ = pair
    before = R.files(src, ".")
    assert WO.resume_from(dst, new, "WO-SRC") == PHASES[1:]
    assert Store(dst).gate("SWE.1")["decision"] == "PASS"
    assert R.files(src, ".") == before  # original workspace, inspections and delivery untouched
    assert new["delivery_intake"]["store"] != old["delivery_intake"]["store"]
    injection = json.loads((dst / ".forge-run/delivery/injection.json").read_text())
    assert injection["swe1_baseline_hash"] == Store(src).latest_baseline("SWE.1")["baseline_hash"]
    assert injection["injected_at"] > new["created_at"]
    for rec in new["delivered"]:
        assert sha256_file(dst / rec["path"]) == rec["sha256"]
        assert (dst / rec["path"]).stat().st_mode & 0o222 == 0
    report = json.loads((dst / ".forge-run/resume/validation.json").read_text())
    assert report["restart_phase"] == "SWE.2" and report["source_fabro_run_id"] == "test-run-id"
    assert report["lineage"]["attempt_seq"] == 2
    assert not (dst / ".forge-run/package.json").exists()


def test_resume_carries_two_phases_and_earliest_invalid_wins(pair):
    src, _, dst, new, _, _ = pair
    write(src, "workproducts/SWE.2/software_architecture.md", ARCH_MIN)
    add_views(src)
    st = Store(src)
    base = st.freeze("SWE.2", "swe2-author")
    rec = st.record_inspection("SWE.2", "swe2-inspector", base["baseline_id"], _all_pass("SWE.2"))
    assert rec["verdict"] == "PASS", rec
    assert WO.resume_from(dst, new, "WO-SRC")[0] == "SWE.3"
    assert Store(dst).gate("SWE.2")["decision"] == "PASS"
    assert not (dst / "inspection/SWE.3").exists()


def test_stale_phase_and_all_downstream_are_not_accepted(pair):
    src, _, dst, new, _, _ = pair
    write(src, "workproducts/SWE.1/software_requirements.md", "changed after freeze\n")
    assert WO.resume_from(dst, new, "WO-SRC") == PHASES
    assert not (dst / "software/ll/stm32n6xx_ll_rcc.h").exists()
    assert not (dst / "configuration/baselines/SWE.1").exists()


def test_explicit_return_to_swe1_does_not_expose_code(pair):
    _, _, dst, new, _, _ = pair
    assert WO.resume_from(dst, new, "WO-SRC", "SWE.1") == PHASES
    assert not (dst / "software").exists()


@pytest.mark.parametrize("mutation,code", [
    (lambda s, m: m["factory_revision"].update(commit="2" * 40), "FACTORY_REVISION"),
    (lambda s, m: m["factory_revision"].update(dirty=True), "FACTORY_REVISION"),
    (lambda s, m: m.update(local_profile={"id": "other"}), "LOCAL_PROFILE_CHANGED"),
    (lambda s, m: m["resume_identity"]["runtime"].update(tools={"clang": "changed"}), "CONTRACT_OR_RUNTIME"),
    (lambda s, m: m["delivery"]["scope"]["functions"].pop(), "CONTRACT_OR_RUNTIME"),
    (lambda s, m: m["target"].update(core="other core"), "CONTRACT_OR_RUNTIME"),
])
def test_incompatible_source_is_refused_before_copy(pair, mutation, code):
    src, old, dst, new, _, _ = pair
    mutation(src, old)
    save(src, old)
    with pytest.raises(R.ResumeRefused, match=code):
        WO.resume_from(dst, new, "WO-SRC")
    assert not (dst / "workproducts").exists()


def test_input_tamper_refused(pair):
    src, old, dst, new, _, _ = pair
    p = src / old["inputs"][0]["path"]
    p.write_text("changed input")
    with pytest.raises(R.ResumeRefused, match="INPUT_MISMATCH"):
        WO.resume_from(dst, new, "WO-SRC")


def test_original_delivery_store_tamper_refused(pair):
    _, old, dst, new, _, _ = pair
    p = Path(old["delivery_intake"]["store"]) / "files" / old["delivered"][0]["path"]
    p.chmod(0o644)
    p.write_text("tampered")
    with pytest.raises(R.ResumeRefused, match="DELIVERY_STORE_MISMATCH"):
        WO.resume_from(dst, new, "WO-SRC")


def test_frozen_workspace_code_tamper_refused(pair):
    src, old, dst, new, _, _ = pair
    p = src / old["delivered"][0]["path"]
    p.chmod(0o644)
    p.write_text("tampered")
    with pytest.raises(R.ResumeRefused, match="FROZEN_DELIVERY_CHANGED"):
        WO.resume_from(dst, new, "WO-SRC")


def test_injection_binding_cannot_be_forged(pair):
    src, _, dst, new, _, _ = pair
    p = src / ".forge-run/delivery/injection.json"
    rec = json.loads(p.read_text())
    rec["swe1_baseline_hash"] = "0" * 64
    p.write_text(pretty_json(rec))
    with pytest.raises(R.ResumeRefused, match="INJECTION_PROVENANCE_MISMATCH"):
        WO.resume_from(dst, new, "WO-SRC")


@pytest.mark.parametrize("status", ["running", "unknown", "queued"])
def test_live_or_unknown_source_never_resumes(pair, monkeypatch, status):
    _, _, dst, new, _, _ = pair
    monkeypatch.setattr("forge_factory.fabro.client.client_for_workspace",
                        lambda *a, **kw: Mock(get_run=lambda rid: {"lifecycle": {"status": {"kind": status}}}))
    with pytest.raises(R.ResumeRefused, match="SOURCE_NOT_TERMINAL"):
        WO.resume_from(dst, new, "WO-SRC")


def test_unreachable_source_never_resumes(pair, monkeypatch):
    _, _, dst, new, _, _ = pair
    monkeypatch.setattr("forge_factory.fabro.client.client_for_workspace",
                        lambda *a, **kw: Mock(get_run=Mock(side_effect=OSError("offline"))))
    with pytest.raises(R.ResumeRefused, match="SOURCE_STATUS_UNKNOWN"):
        WO.resume_from(dst, new, "WO-SRC")


def test_symlink_evidence_refused(pair, tmp_path):
    src, _, dst, new, _, _ = pair
    external = tmp_path / "outside"
    external.mkdir()
    write(external, "secret", "must not copy")
    (src / "workproducts/SWE.1/external").symlink_to(external, target_is_directory=True)
    with pytest.raises(R.ResumeRefused, match="UNSAFE_PATH"):
        WO.resume_from(dst, new, "WO-SRC")


def test_inspector_identity_tamper_invalidates_prefix(pair):
    src, _, dst, new, _, _ = pair
    p = next((src / "inspection/SWE.1").glob("INS-*.json"))
    rec = json.loads(p.read_text())
    rec["inspector_role"] = "swe1-author"
    p.write_text(pretty_json(rec))
    assert WO.resume_from(dst, new, "WO-SRC") == PHASES


def test_legacy_source_refused_and_no_overwrite_of_it(pair):
    src, old, _, _, _, ex = pair
    old.pop("resume_identity")
    save(src, old)
    before = R.files(src, ".")
    with pytest.raises(R.ResumeRefused, match="SOURCE_UNVERSIONED"):
        WO.run(ex, "WO-LEGACY-NEW", resume="WO-SRC", detach=True)
    with pytest.raises(R.ResumeRefused, match="SOURCE_EQUALS_DESTINATION"):
        WO.run(ex, "WO-SRC", resume="WO-SRC", detach=True)
    assert R.files(src, ".") == before


def test_sibling_resumes_share_one_finite_budget(pair):
    src, old, dst, new, prepare, _ = pair
    for man in (old, new):
        man["resume_identity"]["limits"]["max_attempts"] = 2
    save(src, old)
    save(dst, new)
    # Fixture's initial budget: configure the root registry before any reservation.
    with sqlite3.connect(R.state_dir() / "resume/lineages.sqlite3") as db:
        db.execute("UPDATE lineages SET limits=? WHERE root='WO-SRC'",
                   (json.dumps(old["resume_identity"]["limits"], sort_keys=True),))
    WO.resume_from(dst, new, "WO-SRC")
    second, other = prepare("WO-SIBLING")
    other["resume_identity"]["limits"]["max_attempts"] = 2
    save(second, other)
    with pytest.raises(R.ResumeRefused, match="ATTEMPT_BUDGET_EXHAUSTED"):
        WO.resume_from(second, other, "WO-SRC")


def test_deadline_survives_multiple_resumes(pair):
    src, old, dst, new, prepare, _ = pair
    WO.resume_from(dst, new, "WO-SRC")
    write(dst, ".forge-run/fabro_run_id", "second-run")
    next_ws, next_man = prepare("WO-THIRD")
    WO.resume_from(next_ws, next_man, "WO-DST")
    assert next_man["resume_lineage"]["attempt_seq"] == 3
    assert next_man["resume_lineage"]["started_epoch"] == new["resume_lineage"]["started_epoch"]
    assert next_man["resume_lineage"]["deadline_epoch"] == new["resume_lineage"]["deadline_epoch"]
    assert R.remaining_seconds(next_ws) > 0


def test_budget_expiry_blocks_next_launch(pair, monkeypatch):
    _, _, dst, new, _, _ = pair
    WO.resume_from(dst, new, "WO-SRC")
    monkeypatch.setattr(R.time, "time", lambda: new["resume_lineage"]["deadline_epoch"] + 1)
    with pytest.raises(R.ResumeRefused, match="WALL_BUDGET_EXHAUSTED"):
        R.remaining_seconds(dst)


def test_deadline_tamper_is_refused(pair):
    _, _, dst, new, _, _ = pair
    WO.resume_from(dst, new, "WO-SRC")
    new["resume_lineage"]["deadline_epoch"] += 10000
    save(dst, new)
    with pytest.raises(R.ResumeRefused, match="DEADLINE_CHANGED"):
        R.remaining_seconds(dst)


def test_missing_lineage_ledger_is_not_recreated(pair, monkeypatch):
    _, _, dst, new, prepare, _ = pair
    WO.resume_from(dst, new, "WO-SRC")
    write(dst, ".forge-run/fabro_run_id", "second-run")
    (Path(dst).parents[2] / "resume/lineages.sqlite3").unlink()
    next_ws, next_man = prepare("WO-THIRD")
    with pytest.raises(R.ResumeRefused, match="LINEAGE_LEDGER_MISSING"):
        WO.resume_from(next_ws, next_man, "WO-DST")


def test_only_accepted_phase_tool_records_are_reused(pair):
    src, _, dst, new, _, _ = pair
    write(src, "evidence/tool-results.jsonl", json.dumps({"phase": "SWE.1", "op": "accepted"}) + "\n" +
          json.dumps({"phase": "SWE.4", "op": "failed-attempt-pass"}) + "\n")
    WO.resume_from(dst, new, "WO-SRC")
    rows = [json.loads(line) for line in (dst / "evidence/tool-results.jsonl").read_text().splitlines()]
    assert [r["op"] for r in rows] == ["accepted"]


def test_afo_launcher_forwards_local_profile_and_resume(monkeypatch):
    from forge_factory.afo import runtime

    seen = {}

    def launch(example, wo, **kwargs):
        seen.update(kwargs)
        return {"fabro_run_id": "new-run"}

    monkeypatch.setattr(WO, "run", launch)
    runtime.launcher({"example": "examples/x", "model": "qwen3.6:35b-a3b", "provider": "ollama",
                      "profile": "local-rtx-v2-omniverse2", "resume_from": "WO-SRC"}, "WO-NEW", {})
    assert seen["profile"] == "local-rtx-v2-omniverse2" and seen["resume"] == "WO-SRC"


def test_runtime_identity_detects_binary_source_and_build_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(R, "TOOLS", ("test-cc",))
    write(tmp_path, "factory/python/forge_factory/compile.py", "original source")
    compiler = tmp_path / "test-cc"
    compiler.write_text("#!/bin/sh\nexit 0\n")
    compiler.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    original = R.runtime_identity()
    compiler.write_text("#!/bin/sh\nexit 1\n")
    assert R.runtime_identity()["tools"] != original["tools"]
    write(tmp_path, "factory/python/forge_factory/compile.py", "changed source")
    assert R.runtime_identity()["factory_assets_sha256"] != original["factory_assets_sha256"]
    monkeypatch.setenv("CFLAGS", "-DCHANGED")
    assert R.runtime_identity()["build_environment"] != original["build_environment"]


def test_parallel_sibling_reservations_cannot_exceed_budget(pair):
    from concurrent.futures import ThreadPoolExecutor

    _, old, _, _, _, _ = pair
    old["resume_identity"]["limits"]["max_attempts"] = 2
    with sqlite3.connect(R.state_dir() / "resume/lineages.sqlite3") as db:
        db.execute("UPDATE lineages SET limits=? WHERE root='WO-SRC'",
                   (json.dumps(old["resume_identity"]["limits"], sort_keys=True),))

    def reserve(n):
        try:
            return R._reserve(old, {"work_order": f"WO-SIBLING-{n}"})["attempt_seq"]
        except R.ResumeRefused:
            return "REFUSED"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(4)))
    assert results.count(2) == 1 and results.count("REFUSED") == 3


def test_native_hook_blocks_expired_resume_without_tools(pair, monkeypatch):
    from forge_factory.policy.authz import Binding
    from forge_factory.policy.fabro_hook import handle

    _, _, dst, new, _, _ = pair
    WO.resume_from(dst, new, "WO-SRC")
    monkeypatch.setattr(R.time, "time", lambda: new["resume_lineage"]["deadline_epoch"] + 1)
    d = handle({"event": "stage_start", "node_id": "author", "run_id": "new"}, Binding("new", str(dst), {}))
    assert not d.allow and d.code == "RESUME_BUDGET_REFUSED"


def test_package_carries_resume_validation_and_lineage(pair, tmp_path):
    from forge_factory.brownfield.package import stage

    _, _, dst, new, _, _ = pair
    WO.resume_from(dst, new, "WO-SRC")
    output = tmp_path / "package"
    stage(dst, output)
    report = json.loads((output / "configuration/resume-validation.json").read_text())
    lineage = json.loads((output / "configuration/resume-lineage.json").read_text())
    assert report["source_work_order"] == "WO-SRC"
    assert lineage["attempt_seq"] == 2


def test_accepted_fix_allowed_corrections_keep_defect_provenance(pair, monkeypatch):
    """Real delivery verification rejects a correction whose CODE defect provenance was lost."""
    src, old, dst, new, _, _ = pair
    for ws, man in ((src, old), (dst, new)):
        man["delivery"]["code_mode"] = man["code_mode"] = "FIX_ALLOWED"
        R.initialize(ws, man)
        save(ws, man)
    write(src, "workproducts/SWE.2/software_architecture.md", ARCH_MIN)
    add_views(src)
    st = Store(src)
    base = st.freeze("SWE.2", "swe2-author")
    assert st.record_inspection("SWE.2", "swe2-inspector", base["baseline_id"], _all_pass("SWE.2"))["verdict"] == "PASS"
    header = src / "software/ll/stm32n6xx_ll_rcc.h"
    header.chmod(0o644)
    # Change inside a scope function; the unchanged authoritative intake remains in its separate store.
    text = header.read_text().replace("ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK;",
                                     "ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= (LL_RCC_CR_HSION_MSK);")
    assert text != header.read_text()
    header.write_text(text)
    write(src, ".forge-run/defects/DEF-001.json", {"id": "DEF-001", "kind": "CODE", "status": "VERIFIED",
                                                "target_phase": "SWE.3", "summary": "HSI enable correction",
                                                "evidence_refs": ["software/ll/stm32n6xx_ll_rcc.h"]})
    write(src, "workproducts/SWE.3/detailed_design.md", "# Accepted implementation\n")
    base = st.freeze("SWE.3", "swe3-author")
    # Fixture inspector: deterministic artifact checks are covered by the separate brownfield suites.
    monkeypatch.setattr(Store, "deterministic_items", lambda *args: {})
    verdicts = {c["id"]: {"verdict": "PASS", "evidence_refs": ["fixture"]}
                for c in st.checklist("SWE.3")["checks"]}
    assert st.record_inspection("SWE.3", "swe3-inspector", base["baseline_id"], verdicts)["verdict"] == "PASS"
    assert WO.resume_from(dst, new, "WO-SRC")[0] == "SWE.4"
    assert (dst / "software/ll/stm32n6xx_ll_rcc.h").read_text() == text
    changes = json.loads((dst / ".forge-run/delivery/change_report.json").read_text())["changes"]
    assert changes[0]["defects"] == ["DEF-001"]


def test_provided_readonly_and_vendor_dependency_survive(pair):
    from forge_factory.common import sha256_bytes

    src, old, dst, new, _, _ = pair
    rel = "software/ll/provided_dependency.h"
    data = "#define PROVIDED 1\n"
    for ws, man in ((src, old), (dst, new)):
        write(ws, rel, data)
        (ws / rel).chmod(0o444)
        man["provided"] = [{"path": rel, "sha256": sha256_bytes(data.encode())}]
        R.initialize(ws, man)
        save(ws, man)
    WO.resume_from(dst, new, "WO-SRC")
    assert (dst / rel).read_text() == data and (dst / rel).stat().st_mode & 0o222 == 0


def test_workorder_api_launches_at_first_unaccepted_phase(pair, monkeypatch):
    _, _, _, _, _, example = pair
    prepare = WO.prepare
    seen = {}

    def minimal_prepare(*args, **kwargs):
        ws, man = prepare(*args, **kwargs)
        man["trace_profile"] = man["register_contract"] = None
        R.initialize(ws, man)
        save(ws, man)
        return ws, man

    def launch(ws, wo, toml, fab, labels):
        seen["graph"] = (ws / ".forge-run/workflow.fabro").read_text()
        seen["ws"] = ws
        return "new-run"

    monkeypatch.setattr(WO, "prepare", minimal_prepare)
    monkeypatch.setattr(WO, "agent_preflight", lambda roles: {"status": "PASS", "issues": []})
    monkeypatch.setattr(WO, "mcp_preflight", lambda *a, **kw: {"status": "PASS", "issues": [],
                                                            "disabled_optional_ops": [], "servers": {}})
    monkeypatch.setattr(WO, "launch_run", launch)
    result = WO.run(example, "WO-API", resume="WO-SRC", detach=True)
    assert result["fabro_run_id"] == "new-run"
    assert "start -> swe2_author" in seen["graph"]
    assert Store(seen["ws"]).gate("SWE.1")["decision"] == "PASS"
    assert (seen["ws"] / ".forge-run/delivery/injection.json").is_file()


def test_destination_symlink_cannot_redirect_writes(pair, tmp_path):
    _, _, dst, new, _, _ = pair
    external = tmp_path / "outside"
    external.mkdir()
    (dst / "workproducts").symlink_to(external, target_is_directory=True)
    with pytest.raises(R.ResumeRefused, match="UNSAFE_PATH"):
        WO.resume_from(dst, new, "WO-SRC")
    assert list(external.iterdir()) == []


def test_unknown_or_malformed_snapshot_cannot_be_forced(pair):
    src, old, dst, new, _, _ = pair
    old["resume_identity"] = {"schema": R.SCHEMA}
    save(src, old)
    with pytest.raises(R.ResumeRefused, match="SOURCE_IDENTITY_INVALID"):
        WO.resume_from(dst, new, "WO-SRC")


def test_open_upstream_defects_survive_even_with_no_reusable_phase(pair):
    src, _, dst, new, _, _ = pair
    write(src, ".forge-run/defects/DEF-001.json", {"id": "DEF-001", "kind": "REQUIREMENT", "status": "IN_FIX",
                                                "target_phase": "SWE.1", "summary": "Correct the requirement"})
    assert WO.resume_from(dst, new, "WO-SRC") == PHASES
    assert (dst / ".forge-run/defects/DEF-001.json").read_bytes() == \
        (src / ".forge-run/defects/DEF-001.json").read_bytes()
    assert not (dst / "software").exists()


def test_workspace_configuration_tamper_refused(pair):
    src, _, dst, new, _, _ = pair
    write(src, "configuration/system_names.json", ["changed system name"])
    with pytest.raises(R.ResumeRefused, match="CONFIGURATION_MISMATCH"):
        WO.resume_from(dst, new, "WO-SRC")


def test_fix_allowed_does_not_authorize_dependency_changes(pair):
    from forge_factory.common import sha256_bytes

    src, old, dst, new, _, _ = pair
    rel, data = "inputs/vendor/include/vendor.h", "#define VENDOR 1\n"
    rec = {"path": rel, "role": "delivered_dependency", "sha256": sha256_bytes(data.encode())}
    for ws, man in ((src, old), (dst, new)):
        man["code_mode"] = man["delivery"]["code_mode"] = "FIX_ALLOWED"
        man["delivered"].append(dict(rec))
        write(Path(man["delivery_intake"]["store"]) / "files", rel, data)
        R.initialize(ws, man)
        save(ws, man)
    write(src, rel, "#define VENDOR 2\n")
    injection = json.loads((src / ".forge-run/delivery/injection.json").read_text())
    injection["files"] = old["delivered"]
    write(src, ".forge-run/delivery/injection.json", injection)
    with pytest.raises(R.ResumeRefused, match="DEPENDENCY_CHANGED"):
        WO.resume_from(dst, new, "WO-SRC")


def test_derived_input_section_tamper_refused(pair):
    src, _, dst, new, _, _ = pair
    section = next((src / "inputs/sections").rglob("*.md"))
    section.write_text("altered derived input; original RM file is unchanged\n")
    with pytest.raises(R.ResumeRefused, match="INPUT_MISMATCH"):
        WO.resume_from(dst, new, "WO-SRC")


def test_model_switch_cannot_upgrade_inherited_independence(pair):
    from forge_factory.assurance.package import attestation

    src, _, dst, _, prepare, _ = pair
    write(src, ".forge-run/model-profile.json", {"default": "qwen", "provider": "ollama"})
    new = json.loads((dst / ".forge-run/manifest.json").read_text())
    WO.resume_from(dst, new, "WO-SRC")
    write(dst, ".forge-run/model-profile.json", {"default": "unused", "provider": "unused",
          "acp_authors": {"model": "author", "provider": "author-provider"},
          "acp_inspectors": {"model": "inspector", "provider": "inspector-provider"}})
    result = attestation(dst)
    assert result["decision"] == "PARTIAL" and not result["independent"]
    assert any("COMMON_CAUSE_MODEL:qwen@ollama" in r for r in result["shared_common_cause_refs"])
    assert not result["schema_issues"]


def test_lost_ledger_cannot_reset_original_root_budget(pair):
    _, _, dst, new, _, _ = pair
    (R.state_dir() / "resume/lineages.sqlite3").unlink()
    with pytest.raises(R.ResumeRefused, match="LINEAGE_LEDGER_MISSING"):
        WO.resume_from(dst, new, "WO-SRC")


def test_existing_greenfield_attestation_is_unchanged(tmp_path):
    from forge_factory.assurance.package import attestation

    write(tmp_path, ".forge-run/manifest.json", {"resumed_from": {"stable_phases": {"SWE.1": "old-inspection"}}})
    write(tmp_path, ".forge-run/model-profile.json", {"default": "unused", "provider": "unused",
          "acp_authors": {"model": "author", "provider": "author-provider"},
          "acp_inspectors": {"model": "inspector", "provider": "inspector-provider"}})
    assert attestation(tmp_path)["decision"] == "SUPPORTED"
