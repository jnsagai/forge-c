"""Native HAL nodes must honor the same per-role model choice as structured LL nodes."""
import re

import pytest
from forge_factory.acp import _split_attrs, statements
from forge_factory.workflow.builder import build
from forge_factory.workorder import local_profile_structured


@pytest.mark.parametrize("profile,author,inspector", [
    ("cloud-bridge-terra-author-sol-inspector", "gpt-6.1-terra", "gpt-6.1-sol"),
    ("local-rtx-v2-omniverse2-ornith-think-author-q38-inspector",
     "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0", "qwen3.8:27b-q8_0"),
])
def test_native_hal_inspector_model_and_serve_agree(monkeypatch, profile, author, inspector):
    monkeypatch.setenv("FORGE_LRTX_ROOT", "/fixture/stack")
    st = local_profile_structured({"id": profile}, {"layer": "HAL"}, author)
    dot, roles = build("WO-NATIVE-MODELS", layer="HAL", peripheral="crc", structured=st, stop_after="SWE.1")
    attrs = {name: a for _, _, _, name, a in statements(dot)}
    assert 'prompt="' in attrs["swe1_author"] and 'prompt="' in attrs["swe1_inspector"]
    assert f'model="{inspector}"' in _split_attrs(attrs["swe1_inspector"])
    assert roles["swe1_inspector"]["model"] == inspector
    for name, expected in (("swe1_author", author), ("swe1_inspector", inspector), ("release_manager", author)):
        assert re.search(r"--model (\S+) --workspace", attrs[name + "_serve"])[1] == expected
    assert not any(a.startswith("model=") for a in _split_attrs(attrs["release_manager"]))


def test_without_role_model_configuration_native_graph_stays_unchanged(monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", "/fixture/stack")
    plain, plain_roles = build("WO-LEGACY-MODELS", layer="HAL", peripheral="crc", stop_after="SWE.1")
    legacy, roles = build("WO-LEGACY-MODELS", layer="HAL", peripheral="crc", stop_after="SWE.1",
                          structured={"model": "legacy", "phases": [], "inspect_phases": []})
    assert legacy == plain and roles == plain_roles
