"""Native HAL instructions distinguish result reads from register-preserving query calls."""
import copy
import re

import pytest
from forge_factory.peripheral import load
from forge_factory.inspection import assessment_context
from forge_factory.release import qm
from forge_factory.workflow.builder import build


@pytest.mark.parametrize("peripheral", ["crc", "wwdg"])
@pytest.mark.parametrize("purpose", ["ASPICE_ONLY", "QM"])
def test_native_hal_scope_and_register_contract_explain_the_two_different_obligations(peripheral, purpose):
    profile = load(peripheral)
    scope = [f"Implement HAL_{peripheral.upper()} initialization and scoped calculation or flag operations."]
    manifest = {"purpose": purpose, "scope": scope,
                "semantic_required_operations": profile.get("semantic_required_operations", [])}
    if purpose == "QM":
        manifest.update(safety_target="QM", **{qm.FIELD: qm.binding()})
        manifest[assessment_context.FIELD] = assessment_context.binding(manifest)
    frozen = copy.deepcopy(manifest)
    graph, _ = build("WO-HAL-CONTRACT", layer="HAL", peripheral=peripheral,
                     sections={s: f"inputs/sections/{s}.md" for s in profile["rm"]["key_sections"]},
                     assessment_manifest=manifest)
    prompts = dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', graph))
    for node in ("swe1_author", "swe1_inspector"):
        assert "engine capability preflight forms" in prompts[node]
        assert "including every requested read/query" in prompts[node]
        assert "Preserve that frozen catalog" in prompts[node]
    author = prompts["swe1_author"]
    assert "A calculation or update call can write and then read the same register" in author
    assert "never assert no_write on a register that call changes" in author
    assert "verify it in the separate requirement-based tests" in author
    assert "For a call that preserves the queried register" in author
    assert manifest == frozen  # Clarification never rewrites authority or capability binding.


def test_legacy_unassessed_graph_does_not_receive_the_new_scope_guidance():
    graph, _ = build("WO-LEGACY-CONTRACT", layer="HAL", peripheral="wwdg")
    assert "engine capability preflight forms" not in graph
    assert "A calculation or update call" not in graph
