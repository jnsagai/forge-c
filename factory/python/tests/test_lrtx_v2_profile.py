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
    ({"model": "llama3:70b"}, "PROFILE_MODEL_NOT_ALLOWED:llama3:70b"),
], ids=["acp-authors", "acp-inspectors", "cloud", "unlisted-model", "unknown-model"])
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


def test_inspector_candidates_are_pinned_and_not_qualified():
    allowed = V2["models"]["allowed"]
    for m in ("gpt-oss:20b", "glm4:9b", "phi4:14b", "mistral-small3.2:24b", "granite3.3:8b"):
        assert len(allowed[m]["digest"]) == 64 and allowed[m]["role_qualification"].startswith("NOT_QUALIFIED")


def test_the_omniverse2_profile_differs_from_v2_only_in_host_paths_and_the_engine_build():
    """The second host's profile may not drift from local-rtx-v2: same structured settings, gates, ports, models and
    engine source commit; only paths, the cross-host engine build, the host reference and its identity differ."""
    from forge_factory.lrtx.profile import load

    v2, om = load("local-rtx-v2"), load("local-rtx-v2-omniverse2")
    host_keys = {"id", "description", "host_reference", "deployment", "existing_deployment", "safec", "runtime", "gateway",
                 "_path", "_sha256"}
    # host tuning may differ (owner 2026-10-22, 48 GB host): Ollama runtime settings and each listed model's reasoning
    # effort/allowance; the models allowed to reason, the timeout scale and every other key stay the same
    assert set(v2["gateway"]["reasoning"]) == set(om["gateway"]["reasoning"])
    assert set(v2["runtime"]["ollama"]) == set(om["runtime"]["ollama"])
    assert {k: v for k, v in v2["runtime"].items() if k != "ollama"} == {k: v for k, v in om["runtime"].items() if k != "ollama"}
    assert {k: v for k, v in v2.items() if k not in host_keys} == {k: v for k, v in om.items() if k not in host_keys}
    assert {k: v for k, v in v2["deployment"].items() if k not in ("default_root", "shared_readonly")} == \
        {k: v for k, v in om["deployment"].items() if k not in ("default_root", "shared_readonly")}
    assert set(v2["deployment"]["shared_readonly"]) == set(om["deployment"]["shared_readonly"])
    e2, eo = v2["safec"]["engine"], om["safec"]["engine"]
    assert e2["source_commit_sha"].split()[0] == eo["source_commit_sha"].split()[0] and \
        e2["semantic_profile"] == eo["semantic_profile"]
    assert {k: v for k, v in v2["safec"].items() if k != "engine"} == {k: v for k, v in om["safec"].items() if k != "engine"}


@pytest.mark.parametrize("example", ["0008a-rcc-ll-delivered", "0008c-st-cube-rcc"])
def test_a_delivered_code_work_order_keeps_only_swe1_and_swe2_structured_on_v2(example):
    """F011-T036 (owner 2026-10-24): the structured SWE.3-SWE.6 tasks need code tasks of a local code author, which a
    delivered-code work order has none of (the build refused with STRUCTURED_NODE_MISSING:swe3_ll_author). On v2 those
    phases run as the existing agent nodes; SWE.1/SWE.2 stay structured; v1 and greenfield work orders are unchanged."""
    import json

    from forge_factory import acp
    from forge_factory.workflow.builder import build

    spec = json.loads((REPO_ROOT / "examples" / example / "workorder.json").read_text())
    bf = {"layer": spec["layer"], "delivery": spec["delivery"]}
    s2 = workorder.local_profile_structured({"id": "local-rtx-v2-omniverse2"}, bf, "qwen3.6:35b-a3b")
    assert s2["phases"] == s2["inspect_phases"] == ["SWE.1", "SWE.2"]
    assert workorder.local_profile_structured({"id": "local-rtx-v2"}, {"layer": "LL"}, "m")["phases"][2:] == [
        "SWE.3", "SWE.4", "SWE.5", "SWE.6"]  # greenfield: unchanged
    assert workorder.local_profile_structured({"id": "local-rtx-v1"}, bf, "m")["phases"][2:3] == ["SWE.3"]  # v1 too
    g, _nodes = build("WO-X", layer=spec["layer"], trace=True, brownfield=spec["delivery"]["code_mode"],
                      peripheral=spec.get("peripheral"), delivery_style=spec["delivery"]["build"]["style"],
                      structured=s2)
    agents = acp.native_agent_nodes(g)
    assert "swe1_author" not in agents and "swe2_author" not in agents and "swe2_inspector" not in agents
    assert {"swe3_author", "swe3_inspector", "swe4_author", "swe6_inspector"} <= set(agents)


def test_fabro_command_nodes_carry_the_local_profile_only_inside_a_local_stack(monkeypatch):
    """F011-T036: the first Fabro run on local-rtx-v2-omniverse2 failed every SWE.1 call (connection refused): command
    nodes get only the builder's explicit environment, and without FORGE_LRTX_PROFILE the runner used the v1 gateway
    port. Inside a stack the profile is passed; elsewhere the node environment is unchanged."""
    from forge_factory.workflow import builder

    monkeypatch.delenv("FORGE_LRTX_PROFILE", raising=False)
    plain = builder._env()
    assert "FORGE_LRTX_PROFILE" not in plain
    monkeypatch.setenv("FORGE_LRTX_PROFILE", "local-rtx-v2-omniverse2")
    assert builder._env() == plain + " FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2"


def test_reasoning_off_variant_differs_from_omniverse2_only_in_the_qwen36_reasoning_factor():
    """Feature 014 (owner 2026-10-25): one controlled configuration factor for the diagnosis comparison."""
    from forge_factory.llm_gateway import sanitize_request
    from forge_factory.lrtx.profile import load

    base, variant = load("local-rtx-v2-omniverse2"), load("local-rtx-v2-omniverse2-q36-noreason")
    ignored = {"id", "status", "description", "_path", "_sha256", "gateway", "deployment"}
    assert {k: v for k, v in base.items() if k not in ignored} == {k: v for k, v in variant.items() if k not in ignored}
    assert {k: v for k, v in base["deployment"].items() if k != "default_root"} == \
        {k: v for k, v in variant["deployment"].items() if k != "default_root"}
    reasoning = dict(base["gateway"]["reasoning"])
    assert reasoning.pop("qwen3.6:35b-a3b") == {"effort": "high", "extra_output_tokens": 16384}
    assert variant["gateway"] == {**base["gateway"], "reasoning": reasoning}
    body = {"model": "qwen3.6:35b-a3b", "max_tokens": 2048, "messages": []}
    assert sanitize_request(body, policy=variant["gateway"]["reasoning"])["reasoning_effort"] == "none"
    assert sanitize_request(body, policy=variant["gateway"]["reasoning"])["max_tokens"] == 2048


def test_qwen38_variant_only_adds_the_verified_model_without_reasoning():
    """Feature 014 (owner 2026-10-25): diagnosis model comparison against the reasoning-off qwen3.6 batch."""
    from forge_factory.lrtx.profile import load

    base, variant = load("local-rtx-v2-omniverse2"), load("local-rtx-v2-omniverse2-q38")
    ignored = {"id", "status", "description", "_path", "_sha256", "models", "deployment"}
    assert {k: v for k, v in base.items() if k not in ignored} == {k: v for k, v in variant.items() if k not in ignored}
    allowed = dict(variant["models"]["allowed"])
    added = allowed.pop("qwen3.8:27b-q8_0")
    assert added["digest"] == "8f5fb6b71ea00052cbe8545738c55ce61112c4e571cb60ca4dad00b131766039" and added["quantization"] == "Q8_0"
    assert allowed == base["models"]["allowed"] and variant["models"]["default"] == base["models"]["default"]
    assert "qwen3.8:27b-q8_0" not in variant["gateway"]["reasoning"]
