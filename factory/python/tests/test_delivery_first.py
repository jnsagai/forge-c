"""Delivery-first uses real compilers/oracles; fixture code is never a Qwen result."""
import json

import pytest
from forge_factory import delivery_first as D
from forge_factory import development_execution as E
from forge_factory import workorder as W
from forge_factory.common import REPO_ROOT
from forge_factory.workflow.builder import build

EXAMPLE = REPO_ROOT / "examples/0014g-st-crc-idr-qwen-delivery"
# Deliberately supplied test fixture. Not model output and not milestone evidence.
GOOD = """#ifndef TEST_CRC_H
#define TEST_CRC_H
#include "forge_crc_device.h"
static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)
{
    CRCx->IDR = InData;
}
static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)
{
    return CRCx->IDR;
}
#endif
"""


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    for name in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + name + "_DIR", str(tmp_path / name))
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    return W.prepare(EXAMPLE, "WO-DF-FIXTURE-ONLY", purpose="QM", execution_policy=E.DEMO)


def candidate(ws, text=GOOD):
    p = ws / "software/ll/stm32n6xx_ll_crc.h"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_new_scope_contains_no_vendor_candidate_or_imported_review(prepared):
    ws, man = prepared
    assert "delivery" not in man and "provided_requirements" not in man
    assert not (ws / "software/ll/stm32n6xx_ll_crc.h").exists()
    assert man["operation_scope"]["functions"] == D.contract(man)["required_functions"]
    ref = json.loads((ws / "inputs/provided-requirements.json").read_text())
    original = json.loads((REPO_ROOT / "examples/0014f-st-cube-crc-idr-qm/provided-requirements.json").read_text())
    assert ref == original
    assert D.preflight(ws)["candidate_initially_absent"]
    assert D.preflight(ws)["candidate_code_substituted"] is False


def test_real_positive_oracle_fixture_and_stale_final_candidate(prepared):
    ws, man = prepared
    D.preflight(ws)
    p = candidate(ws)
    result = D.verify(ws, 0)
    assert result["status"] == "PASS", result
    assert {r["check"]: r["status"] for r in result["calls"]} == {
        "host_compile": "PASS", "target_compile": "PASS", "independent_behavior": "PASS"}
    assert D.verify(ws, 0) == result
    # Real independent simulation/cost is a separate required result. Fixture
    # source is not model authorship or an accepted process/release milestone.
    report = D.report(ws)
    assert report["slice_behavior_and_compile"] == "PASS"
    assert report["functional_verification"] == "PASS"
    assert result["independent_target"]["status"] == "PASS"
    assert result["independent_target"]["outputs"]["simulation"]["metrics"]["passed"] == 351
    assert report["milestone"] == "NOT_PROVEN" and report["release_eligibility"] == "BLOCKED"
    assert "630 checks, 0 failures" in (ws / ".forge-run/delivery-first/attempt-0/independent_behavior.stdout").read_text()
    p.write_text(GOOD.replace("return CRCx->IDR;", "return CRCx->IDR & 0xFFU;"))
    assert D.report(ws)["functional_verification"] == "NOT_RUN"
    with pytest.raises(ValueError, match="COMPLETED_ATTEMPT_CHANGED"):
        D.verify(ws, 0)


@pytest.mark.parametrize("bad", [
    GOOD.replace("CRCx->IDR = InData;", "CRCx->IDR = InData & 0xFFU;"),
    GOOD.replace("return CRCx->IDR;", "return CRCx->IDR & 0xFFU;"),
    GOOD.replace("CRCx->IDR = InData;", "CRCx->IDR = InData; CRCx->DR = 0U;"),
    GOOD.replace("return CRCx->IDR;", "return 0U;"),
])
def test_independent_oracle_rejects_behavioral_mutants(prepared, bad):
    ws, _ = prepared
    D.preflight(ws)
    candidate(ws, bad)
    result = D.verify(ws, 0)
    assert result["status"] == "FAIL"
    assert any(c["status"] == "FAIL" for c in result["calls"])
    assert D.report(ws)["functional_verification"] == "FAIL"


def test_compile_failure_then_two_corrections_preserve_failed_candidates(prepared):
    ws, _ = prepared
    D.preflight(ws)
    candidate(ws, "this is invalid C")
    first = D.verify(ws, 0)
    assert first["status"] == "FAIL" and first["calls"][0]["exit_code"] != 0
    candidate(ws, GOOD.replace("return CRCx->IDR;", "return CRCx->IDR & 1U;"))
    assert D.verify(ws, 1)["status"] == "FAIL"
    candidate(ws)
    assert D.verify(ws, 2)["status"] == "PASS"
    with pytest.raises(ValueError, match="ATTEMPT_INVALID"):
        D.verify(ws, 3)
    root = ws / ".forge-run/delivery-first"
    assert (root / "attempt-0/candidate/software/ll/stm32n6xx_ll_crc.h").read_text() == "this is invalid C"
    assert json.loads((root / "attempt-0/result.json").read_text()) == first
    assert len(D.report(ws)["attempts"]) == 3


def test_missing_candidate_and_tampered_authority_never_pass(prepared):
    ws, man = prepared
    D.preflight(ws)
    assert D.verify(ws, 0)["status"] == "FAIL"
    p = ws / "inputs/idr_oracle.c"
    p.chmod(0o600)
    p.write_text("int main(void) { return 0; }")
    with pytest.raises(ValueError, match="DEMONSTRATION_INPUT_CHANGED"):
        D.verify(ws, 1)


def test_profile_boundary_and_escaped_candidate(prepared):
    ws, man = prepared
    cfg = man["delivery_first"]
    with pytest.raises(ValueError, match="REQUIRES_NEW_GREENFIELD"):
        D.contract({**man, "purpose": "ASPICE_ONLY"})
    with pytest.raises(ValueError, match="REQUIRES_NEW_GREENFIELD"):
        D.contract({**man, "delivery": {"code_mode": "FROZEN"}})
    with pytest.raises(Exception, match="PATH_TRAVERSAL"):
        D.checked_paths(ws, {**cfg, "candidate_files": ["../outside.c"]})
    with pytest.raises(ValueError, match="CANDIDATE_PATH_DENIED"):
        D.checked_paths(ws, {**cfg, "candidate_files": ["inputs/replace-oracle.c"]})
    candidate(ws)
    with pytest.raises(ValueError, match="INITIAL_CANDIDATE_MUST_BE_ABSENT"):
        D.preflight(ws)


def test_declared_target_harness_reuses_pointer_api_in_existing_tools(prepared):
    from forge_factory.mcp.servers import build as compiler
    from forge_factory.mcp.servers import sim
    from forge_factory.workflow.scaffold import scaffold

    ws, _ = prepared
    candidate(ws)
    result = scaffold(ws)
    assert result["declared_target_harness"] is True
    text = (ws / result["file"]).read_text()
    assert "ll_crc_regs" not in text and "FORGE_HOST_DEVICE_IMPLEMENTATION" in text
    assert "-I" in compiler.includes(D.context(ws))
    test = ws / "software/tests/target/test_crc_target.c"
    test.parent.mkdir(parents=True)
    test.write_text('#include "stm32n6xx_ll_crc.h"\nint main(void) { LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU); '
                    'return LL_CRC_Read_IDR(CRC) == 0xFFFFFFFFU ? 0 : 1; }\n')
    elf = ws / "build/declared-adapter/test.elf"
    elf.parent.mkdir(parents=True)
    ok, log, _ = sim.build_image(ws, test, elf)
    assert ok, log.decode(errors="replace")
    assert elf.is_file()


def test_generated_header_uses_declared_probe_in_normal_build_tools(prepared):
    from forge_factory.mcp.servers import build as compiler

    ws, _ = prepared
    candidate(ws)
    ctx = D.context(ws)
    configured = compiler.configure(ctx, compiler.ConfigureIn())
    assert configured["status"] == "PASS", configured
    assert compiler.sources(ctx) == [ws / "inputs/idr_target_probe.c"]
    built = compiler.compile_(ctx, compiler.CompileIn())
    assert built["status"] == "PASS", built
    candidate(ws, "invalid C")
    assert compiler.compile_(ctx, compiler.CompileIn())["status"] == "FAIL"


def test_unselected_tool_workspaces_retain_empty_adapter_flags(tmp_path):
    assert D.selected(tmp_path) == (None, {})
    assert D.include_flags(tmp_path) == []


def test_native_graph_has_exactly_two_corrections_then_all_six_phases(prepared):
    ws, man = prepared
    graph, nodes = build(man["work_order"], layer="LL", peripheral="crc", sections=W.section_map(ws),
                         operation_scope=man["operation_scope"], assessment_manifest=man,
                         execution_policy=man["development_execution"])
    for i in range(3):
        assert nodes["df_author_" + str(i)] == {"role": "swe3-author", "phase": "SWE.3"}
        assert f"df_author_{i} -> df_verify_{i}" in graph
    assert "df_author_3" not in graph and "df_verify_2 -> swe1_author" in graph
    assert "swe3_fix_author" not in nodes
    assert "df_preflight -> df_final_verify" in graph and "df_final_verify -> finalize" in graph
    for i in range(1, 7):
        assert f"swe{i}_author" in nodes and f"swe{i}_inspector" in nodes
    assert "forge_factory.lrtx.runner" not in graph
    strict, strict_nodes = build("WO-STRICT-COMPAT", layer="LL")
    assert "df_author" not in strict and not any(n.startswith("df_") for n in strict_nodes)
    assert D.contract({"purpose": "LEGACY"}) is None


def test_existing_finalizer_packages_attempts_without_releasing(prepared):
    from forge_factory.release import finalize

    ws, _ = prepared
    D.preflight(ws)
    candidate(ws)
    assert D.verify(ws, 0)["status"] == "PASS"
    result = finalize.finalize(ws, "delivery-first-fixture-only")
    assert result["package_status"] == "BLOCKED"
    import zipfile

    with zipfile.ZipFile(result["archive"]) as archive:
        doc = json.loads(archive.read("evidence/verification/delivery-first/report.json"))
        assert doc["slice_behavior_and_compile"] == "PASS"
        assert doc["functional_verification"] == "PASS"
        assert doc["milestone"] == "NOT_PROVEN"
        assert "release_eligibility: BLOCKED" in archive.read(
            "evidence/verification/delivery-first/SCORECARD.md").decode()
        assert archive.read("evidence/inputs/idr_oracle.c") == (ws / "inputs/idr_oracle.c").read_bytes()
        assert any("attempt-0/host_compile.stderr" in n for n in archive.namelist())
    assert finalize.verify_archive(__import__("pathlib").Path(result["archive"]))["integrity"] == "PASS"


def test_legacy_host_only_receipt_remains_inconclusive(prepared):
    ws, man = prepared
    man["delivery_first"].pop("simulation_oracle")
    (ws / ".forge-run/manifest.json").write_text(json.dumps(man))
    D.preflight(ws)
    candidate(ws)
    assert D.verify(ws, 0)["status"] == "PASS"
    assert D.report(ws)["functional_verification"] == "INCONCLUSIVE"


def test_final_recheck_rejects_downstream_code_change_without_new_model_pass(prepared):
    ws, _ = prepared
    D.preflight(ws)
    candidate(ws)
    initial = D.verify(ws, 0)
    assert initial["status"] == "PASS"
    candidate(ws, GOOD.replace("return CRCx->IDR;", "return CRCx->IDR & 0xFFU;"))
    final = D.verify(ws, "final")
    assert final["status"] == "FAIL" and final["correction_count"] == 0
    assert final["verification_round"] == "FINAL_RECHECK_NO_NEW_AUTHOR"
    assert D.report(ws)["functional_verification"] == "FAIL"
    assert json.loads((ws / ".forge-run/delivery-first/attempt-0/result.json").read_text()) == initial
    assert "return CRCx->IDR;" in (ws / ".forge-run/delivery-first/attempt-0/candidate/software/ll/stm32n6xx_ll_crc.h").read_text()


def test_changed_independent_evidence_cannot_reuse_a_pass(prepared):
    ws, _ = prepared
    D.preflight(ws)
    candidate(ws)
    result = D.verify(ws, 0)
    assert result["status"] == "PASS"
    shadow = ws / result["independent_target"]["workspace"]
    path = shadow / "software/ll/stm32n6xx_ll_crc.h"
    path.write_text(path.read_text() + "\n/* altered snapshot */\n")
    report = D.report(ws)
    assert report["functional_verification"] == "FAIL" and report["integrity_issues"]


def test_existing_afo_preflight_uses_the_selected_delivery_graph(prepared, monkeypatch):
    from forge_factory.afo import product_role_trial
    from forge_factory.lrtx.profile import load

    ws, _ = prepared
    profile = load("local-rtx-v2-omniverse2-q38-delivery-first")
    monkeypatch.setattr(W, "factory_revision", lambda: {"commit": "fixture-only-source", "dirty": False})
    model = profile["models"]["default"]
    job = {"factory_revision": {"commit": "fixture-only-source"}, "profile": profile["id"], "model": model,
           "model_digest": profile["models"]["allowed"][model]["digest"],
           "precision": profile["models"]["allowed"][model]["quantization"]}
    result = product_role_trial.preflight(ws, job, [])
    assert result["status"] == "NOT_RUN" and result["generation_performed"] is False
    assert set(result["required_roles"]) == {f"swe{i}-{role}" for i in range(1, 7) for role in ("author", "inspector")} | {
        "release-manager"}


def test_unsupported_target_is_not_silently_compiled_as_current_fixture(prepared):
    _, man = prepared
    for field, value in (("compiler_profiles", {"host": "host-clang", "target": "unknown-target"}),
                         ("simulation_adapter", "unknown-simulator")):
        cfg = {**man["delivery_first"], field: value}
        with pytest.raises(ValueError, match="ADAPTER_UNSUPPORTED"):
            D.contract({**man, "delivery_first": cfg})
    with pytest.raises(ValueError, match="ADAPTER_UNSUPPORTED"):
        D.contract({**man, "target": {**man["target"], "core": "Unsupported ISA"}})


def test_correction_bound_is_enforced_by_existing_tool_policy(prepared):
    from forge_factory.policy.authz import Authorizer, Binding

    ws, man = prepared
    roles = {name: {"role": "swe3-author", "phase": "SWE.3"} for name in
             ("df_author_0", "df_author_1", "df_author_2", "swe3_author", "swe3_fix_author")}
    auth = Authorizer(Binding(man["work_order"], str(ws), roles))
    args = {"file_path": man["delivery_first"]["candidate_files"][0], "content": GOOD}
    D.preflight(ws)
    assert auth.decide("df_author_0", "write_file", args).allow
    assert not auth.decide("df_author_1", "write_file", args).allow
    assert not auth.decide("swe3_fix_author", "write_file", args).allow
    candidate(ws, "invalid C")
    D.verify(ws, 0)
    assert not auth.decide("df_author_0", "write_file", args).allow
    assert auth.decide("df_author_1", "write_file", args).allow
    candidate(ws, "invalid C again")
    D.verify(ws, 1)
    assert auth.decide("df_author_2", "write_file", args).allow
    candidate(ws)
    assert D.verify(ws, 2)["status"] == "PASS"
    assert not auth.decide("df_author_2", "write_file", args).allow
    assert not auth.decide("swe3_author", "write_file", args).allow
    assert not auth.decide("df_author_2", "write_file", {**args, "file_path": "software/ll/extra.h"}).allow
    assert auth.decide("swe3_author", "write_file", {"file_path": "workproducts/SWE.3/design.md", "content": "draft"}).allow


@pytest.mark.parametrize("error,node,tamper,expected", [
    (False, "df_author_0", False, "CONFIRMED_NATIVE_WRITE_FILE"),
    (True, "df_author_0", False, "UNVERIFIED_EDIT_CHAIN"),
    (False, "swe3_inspector", False, "UNVERIFIED_EDIT_CHAIN"),
    (False, "df_author_0", True, "UNVERIFIED_EDIT_CHAIN"),
])
def test_native_authorship_requires_success_role_and_exact_content(prepared, monkeypatch, error, node, tamper, expected):
    from forge_factory.common import sha256_bytes
    from forge_factory.fabro import client as native

    ws, _ = prepared
    run = ws / ".forge-run"
    (run / "fabro_run_id").write_text("FIXTURE_ONLY")
    (run / "fabro_server.json").write_text("{}")
    (run / "binding.json").write_text(json.dumps({"nodes": {"df_author_0": {"role": "swe3-author"},
                                                           "swe3_inspector": {"role": "swe3-inspector"}}}))
    rel = "software/ll/stm32n6xx_ll_crc.h"
    events = [{"event": "agent.event", "node_id": node, "properties": {"event": {"ToolCallStarted": {
        "tool_call_id": "fixture-call", "tool_name": "write_file", "arguments": {"file_path": rel, "content": GOOD}}}}},
        {"event": "agent.event", "node_id": node, "properties": {"event": {"ToolCallCompleted": {
            "tool_call_id": "fixture-call", "is_error": error}}}}]
    events += [{"event": "stage.started", "node_id": f"swe{i}_{role}"}
               for i in range(1, 7) for role in ("author", "inspector")]

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def iter_events(self, _):
            return iter(events)

        def get_run(self, _):
            return {"data": {"status": "succeeded"}}

        def usage(self, _):
            return {"totals": {"usage": {"tokens": {"input": 8, "output": 13}}},
                    "stages": [{"stage": {"id": "df_author_0"}, "usage": {"tokens": {"output": 13}}}]}

    monkeypatch.setattr(native, "client_for_workspace", lambda *a, **k: Client())
    result = D.native_record(ws, {rel: sha256_bytes((GOOD + " " if tamper else GOOD).encode())})
    assert result["authorship"] == expected, result
    assert result["reported_tokens"]["output"] == 13 and result["reported_author_output_tokens"] == 13
    assert result["model_requests"] == "UNKNOWN" and result["reasoning_token_breakdown"] == "UNKNOWN"
    assert all(all(v.values()) for v in result["phase_attempts"].values())
