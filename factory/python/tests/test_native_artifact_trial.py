"""A native QM artifact trial uses the shared agent graph and retains failed-check evidence."""
from forge_factory import development_execution as D
from forge_factory import workorder as W
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import profile
from forge_factory.workflow.builder import build


def test_native_artifact_trial_keeps_full_scope_and_no_structured_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, manifest = W.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-NATIVE-ARTIFACTS",
                             purpose="QM", execution_policy=D.DEMO_REPAIR)
    p = profile.load("local-rtx-v2-omniverse2-q38-qm-native-artifacts")
    structured = W.local_profile_structured(p, manifest, p["models"]["default"])
    assert structured["phases"] == [] and structured["inspect_phases"] == []
    graph, nodes = build(manifest["work_order"], layer="LL", trace=True, sections=W.section_map(ws),
                         assessment_manifest=manifest, execution_policy=manifest["development_execution"],
                         structured=structured)
    assert "forge_factory.lrtx.runner" not in graph
    for n in range(1, 7):
        assert nodes[f"swe{n}_author"]["role"] == f"swe{n}-author"
        assert nodes[f"swe{n}_inspector"]["role"] == f"swe{n}-inspector"
    assert "14.10.90" in graph and "12-26 requirements" not in graph
    assert manifest["development_execution"]["demonstration_only"] is True
    assert manifest["development_execution"]["quality_gates_block_workflow"] is False
    assert "queries return the specified value, not void" in graph
