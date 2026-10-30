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
    # A host+compile pass is explicitly narrower than the full reviewed contract.
    report = D.report(ws)
    assert report["slice_behavior_and_compile"] == "PASS"
    assert report["functional_verification"] == "INCONCLUSIVE"
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
    assert "df_preflight -> finalize" in graph
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
        assert doc["functional_verification"] == "INCONCLUSIVE"
        assert doc["milestone"] == "NOT_PROVEN"
        assert archive.read("evidence/inputs/idr_oracle.c") == (ws / "inputs/idr_oracle.c").read_bytes()
        assert any("attempt-0/host_compile.stderr" in n for n in archive.namelist())
    assert finalize.verify_archive(__import__("pathlib").Path(result["archive"]))["integrity"] == "PASS"

