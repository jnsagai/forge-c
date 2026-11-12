"""Actual node/model/serve provenance controls only; no model capability is claimed."""

import json

import pytest
from forge_factory.afo import line_product_context as C
from forge_factory.afo.durable import Refused


@pytest.fixture
def source(tmp_path, monkeypatch):
    from forge_factory.lrtx import profile as P

    run = tmp_path / ".forge-run"
    run.mkdir()
    graph = (
        "digraph g {\n"
        '  author [prompt="author", model="author-model"]\n'
        '  inspector [prompt="inspector", model="inspector-model"]\n'
        '  author_serve [script="python -m forge_factory.lrtx.stack serve --model author-model"]\n'
        '  inspector_serve [script="python -m forge_factory.lrtx.stack serve --model inspector-model"]\n'
        '  author_serve -> author [condition="outcome=succeeded"]\n'
        '  inspector_serve -> inspector [condition="outcome=succeeded"]\n}\n'
    )
    (run / "workflow.fabro").write_text(graph)
    (run / "binding.json").write_text(
        json.dumps(
            {"workspace": str(tmp_path), "nodes": {"author": {"role": "swe3-author"}, "inspector": {"role": "swe3-inspector"}}}
        )
    )
    (run / "model-profile.json").write_text(json.dumps({"default": "author-model"}))
    profile = {
        "_sha256": "a" * 64,
        "models": {
            "allowed": {
                "author-model": {"digest": "b" * 64, "quantization": "Q8_0"},
                "inspector-model": {"digest": "c" * 64, "quantization": "Q8_0"},
            }
        },
    }
    monkeypatch.setattr(P, "load", lambda _: profile)
    job = {
        "job_id": "afo-product-fixture",
        "nonce": "nonce",
        "workspace": str(tmp_path),
        "profile": "fixture",
        "model": "author-model",
        "factory_revision": {"commit": "d" * 40},
        "mission_id": "same-mission",
        "role_capabilities": {},
        "reserved_tokens": 120000,
    }
    return tmp_path, job, profile


def test_mixed_actual_roles_share_one_job_and_budget_without_capability_inference(source):
    ws, job, profile = source
    job["line_product_context"] = C.capture(ws, job, profile)
    author = C.request_job(job, "swe3-author", "author-model", None)
    inspector = C.request_job(job, "swe3-inspector", "inspector-model", None)
    assert author["model_digest"] == "b" * 64 and inspector["model_digest"] == "c" * 64
    for key in ("job_id", "nonce", "mission_id", "reserved_tokens"):
        assert author[key] == inspector[key] == job[key]
    assert inspector["role_capabilities"] == {}  # provenance does not manufacture competence


def test_undeclared_model_or_native_helper_cannot_borrow_a_qualified_role(source):
    ws, job, profile = source
    job["line_product_context"] = C.capture(ws, job, profile)
    for role, model in [("swe3-author", "inspector-model"), ("native-helper", "author-model")]:
        with pytest.raises(Refused, match="UNDECLARED"):
            C.request_job(job, role, model, None)


def test_immutable_graph_or_serve_context_change_refuses_before_provider(source):
    ws, job, profile = source
    job["line_product_context"] = C.capture(ws, job, profile)
    graph = ws / ".forge-run/workflow.fabro"
    graph.write_text(graph.read_text().replace("--model inspector-model", "--model author-model"))
    with pytest.raises(Refused, match="SOURCE_CHANGED"):
        C.request_job(job, "swe3-inspector", "inspector-model", None)
    with pytest.raises(Refused, match="SERVE_BINDING_MISMATCH"):
        C.capture(ws, job, profile)


def test_native_node_missing_registered_role_is_refused(source):
    ws, job, profile = source
    path = ws / ".forge-run/binding.json"
    value = json.loads(path.read_text())
    value["nodes"].pop("inspector")
    path.write_text(json.dumps(value))
    with pytest.raises(Refused, match="UNDECLARED_MODEL_NODE"):
        C.capture(ws, job, profile)


def test_native_routing_cannot_substitute_a_model_for_the_pinned_inspector(source):
    ws, job, profile = source
    profile["structured"] = {"role_models": {"author": "author-model", "inspector": "inspector-model"}}
    path = ws / ".forge-run/workflow.fabro"
    path.write_text(path.read_text().replace("inspector-model", "author-model"))
    with pytest.raises(Refused, match="PROFILE_ROLE_MODEL_MISMATCH"):
        C.capture(ws, job, profile)


def test_actual_factory_structured_continuation_keeps_declared_role_and_serve_map(source, monkeypatch):
    from forge_factory.workflow.builder import binding_for, build

    ws, job, profile = source
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(ws / "runtime"))
    graph, nodes = build(
        "WO-FIXTURE",
        phases=["SWE.1"],
        stop_after="SWE.1",
        structured={
            "phases": ["SWE.1"],
            "inspect_phases": ["SWE.1"],
            "model": "author-model",
            "author_model": "author-model",
            "inspector_model": "inspector-model",
        },
    )
    (ws / ".forge-run/workflow.fabro").write_text(graph)
    binding_for("WO-FIXTURE", str(ws), nodes).dump(ws / ".forge-run/binding.json")
    ref = C.capture(ws, job, profile)
    context = json.loads(__import__("pathlib").Path(ref["path"]).read_text())
    assert context["nodes"]["swe1_author_more"]["role"] == "swe1-author"
    assert context["nodes"]["swe1_inspector_more"]["model"] == "inspector-model"
