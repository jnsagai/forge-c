"""Feature 011 M3 (F011-T020): local-rtx-v2 is an explicit, isolated opt-in. It has its own root and ports, the same
refusals as v1 (ACP, cloud, unlisted models) and the same workflow graph. The semantic SWE.1 author is chosen at run
time from the work order's profile, so v1 and the default/ACP lines are untouched (their frozen fixtures still pass)."""
from __future__ import annotations

from pathlib import Path

import pytest
from forge_factory import workorder
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.lrtx import compat
from forge_factory.lrtx import profile as lp

V1, V2 = lp.load("local-rtx-v1"), lp.load("local-rtx-v2")


def test_v2_has_its_own_root_and_ports_and_never_touches_v1_or_the_deployment():
    d1, d2 = V1["deployment"], V2["deployment"]
    assert set(d2["ports"].values()).isdisjoint(d1["ports"].values())
    assert set(d1["ports"].values()) <= set(d2["forbidden_ports"])
    assert set(d1["forbidden_ports"]) <= set(d2["forbidden_ports"])
    r1, r2 = Path(d1["default_root"]), Path(d2["default_root"])
    assert r1 != r2 and not r2.is_relative_to(r1) and not r1.is_relative_to(r2)
    assert str(r1) in V2["existing_deployment"]["roots"]
    assert all(not r2.is_relative_to(Path(x)) for x in V2["existing_deployment"]["roots"])
    assert V2["local_only"] and V2["network"]["required"] == "namespace_denied" and V2["provider"] == "ollama"


@pytest.mark.parametrize("kw, issue", [
    ({"acp_authors": "codex"}, "PROFILE_REJECTS_ACP:codex"),
    ({"acp_inspectors": "claude"}, "PROFILE_REJECTS_ACP:claude"),
    ({"provider": "deepseek", "model": "deepseek-flash"}, "PROFILE_PROVIDER_NOT_LOCAL:deepseek"),
    ({"model": "qwen3:8b"}, "PROFILE_MODEL_NOT_ALLOWED:qwen3:8b"),  # not measured for v2: not allowed
], ids=["acp-authors", "acp-inspectors", "cloud", "unlisted-model"])
def test_v2_refuses_cloud_acp_and_unlisted_models_before_launch(kw, issue):
    args = {"model": "qwen3-coder:30b", "provider": "ollama", "code_model": None, "acp_authors": None,
            "acp_inspectors": None, **kw}
    assert issue in lp.selection_issues(V2, **args)
    assert lp.selection_issues(V2, model="qwen3-coder:30b", provider="ollama", code_model=None, acp_authors=None,
                               acp_inspectors=None) == []


def test_v2_builds_the_same_graph_as_v1_and_names_semantic_swe1():
    s1 = workorder.local_profile_structured({"id": "local-rtx-v1"}, {"layer": "LL"}, "qwen3-coder:30b")
    s2 = workorder.local_profile_structured({"id": "local-rtx-v2"}, {"layer": "LL"}, "qwen3-coder:30b")
    assert s1 == s2  # the runner, not the graph, selects the semantic SWE.1 author
    assert V2["structured"]["semantic_phases"] == ["SWE.1"] and "semantic_phases" not in V1["structured"]


def test_v2_pins_an_exact_safec_engine():
    e = V2["safec"]["engine"]
    assert len(e["binary_sha256"]) == 64 and len(e["source_commit_sha"]) == 40
    assert e["semantic_profile"] == "register-io-0.1"
    if Path(e["binary"]).is_file():  # the private engine exists only on the owner's host
        assert sha256_file(Path(e["binary"])) == e["binary_sha256"]


def test_v1_profile_file_is_byte_identical_to_the_frozen_fixture():
    data = compat.load(REPO_ROOT / "tests/compat/lrtx/local-rtx-v1-2f4b9cf.json.gz")
    assert data["profile"]["config_sha256"] == V1["_sha256"]
