"""The real graph verifies final bytes after the model's release-manager visit."""
# ruff: noqa: F811 - conventional imported pytest fixture
import json
import zipfile
from pathlib import Path

import pytest
from forge_factory import delivery_first as D
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import evidence
from forge_factory.release import finalize as F
from forge_factory.workflow.builder import build
from test_delivery_first import (
    GOOD,
    candidate,
    prepared,  # noqa: F401 - shared isolated fixture
)


@pytest.mark.parametrize("bad_final", [False, True])
def test_model_cannot_seal_before_final_graph_verification(prepared, bad_final):
    ws, man = prepared
    D.preflight(ws)
    candidate(ws)
    assert D.verify(ws, 0)["status"] == "PASS"
    ctx = sdk.ToolContext("forge-evidence-mcp", "build_package", "release-manager", None, ws, man["work_order"])
    early = evidence.build_package(ctx, evidence.PackageIn())
    assert early["status"] == "BLOCKED", early
    assert "DELIVERY_FIRST_FINAL_VERIFICATION_PENDING" in early["issues"]
    assert not list(F.archive_root().glob("**/*.zip"))
    assert not (ws / ".forge-run/package.json").exists()
    if bad_final:
        candidate(ws, GOOD.replace("return CRCx->IDR;", "return 0U;"))
    final = D.verify(ws, "final")
    assert final["status"] == ("FAIL" if bad_final else "PASS")
    sealed = F.finalize(ws, man["work_order"])
    with zipfile.ZipFile(sealed["archive"]) as archive:
        root = "evidence/verification/delivery-first/"
        assert json.loads(archive.read(root + "attempts/attempt-final/result.json")) == final
        report = json.loads(archive.read(root + "report.json"))
        assert report["functional_verification"] == final["status"]
        assert report["release_eligibility"] == "BLOCKED"
        assert len(report["attempts"]) == 2
    assert F.verify_archive(Path(sealed["archive"]))["integrity"] == "PASS"
    # No sealed archive is rewritten by a later model or graph finalizer call.
    assert F.finalize(ws, man["work_order"])["archive_sha256"] == sealed["archive_sha256"]


def test_delivery_release_manager_is_inventory_only_before_graph_finalizer(prepared):
    _, man = prepared
    graph, _ = build(man["work_order"], layer="LL", peripheral="crc", assessment_manifest=man,
                     execution_policy=man["development_execution"], operation_scope=man["operation_scope"])
    node = next(line for line in graph.splitlines() if line.startswith("  release_manager ["))
    assert "Do not call build_package" in node
    assert "release_manager -> df_final_verify" in graph
    assert "df_final_verify -> finalize" in graph


@pytest.mark.parametrize("raw", ["not json", "[]", "{}", '{"attempt":0,"status":"PASS"}'])
def test_missing_or_invalid_final_receipt_never_permits_model_sealing(prepared, raw):
    ws, man = prepared
    receipt = ws / ".forge-run/delivery-first/attempt-final/result.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(raw)
    ctx = sdk.ToolContext("forge-evidence-mcp", "build_package", "release-manager", None, ws, man["work_order"])
    out = evidence.build_package(ctx, evidence.PackageIn())
    assert out["status"] == "BLOCKED" and not out["artifact_refs"]
    assert not list(F.archive_root().glob("**/*.zip"))


def test_existing_strict_mcp_packaging_is_not_deferred(tmp_path, monkeypatch):
    from test_m7_governance_release import complete_workspace

    for key, path in (("FORGE_STATE_DIR", "state"), ("FORGE_EVENTS_DIR", "events"),
                      ("FORGE_ARCHIVE_DIR", "archives")):
        monkeypatch.setenv(key, str(tmp_path / path))
    ws = tmp_path / "ws"
    ws.mkdir()
    complete_workspace(ws)
    ctx = sdk.ToolContext("forge-evidence-mcp", "build_package", "release-manager", None, ws, "WO-STRICT-FIXTURE")
    out = evidence.build_package(ctx, evidence.PackageIn())
    assert out["status"] == "PASS", out
    assert out["metrics"]["package_status"] == "READY_FOR_OFFLINE_REVIEW"
    assert list(F.archive_root().glob("**/*.zip"))
