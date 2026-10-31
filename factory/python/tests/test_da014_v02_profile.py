"""Candidate engine selection stays explicit and frozen to the parsed profile bytes."""

import json

import pytest
import yaml
from forge_factory.common import sha256_bytes
from forge_factory.lrtx import profile as P
from forge_factory.lrtx import swe1_semantic as S

CANDIDATE = "local-rtx-v2-omniverse2-wwdg-v02"


def test_candidate_changes_only_identity_and_explicit_engine_pin():
    base = P.load("local-rtx-v2-omniverse2-q36-noreason")
    candidate = P.load(CANDIDATE)
    allowed = {"id", "description", "status", "_path", "_sha256"}
    old = {k: v for k, v in base.items() if k not in allowed}
    new = {k: v for k, v in candidate.items() if k not in allowed}
    old.pop("safec")
    new.pop("safec")
    assert old == new
    assert {k: v for k, v in base["safec"].items() if k != "engine"} == {
        k: v for k, v in candidate["safec"].items() if k != "engine"
    }
    pin = candidate["safec"]["engine"]
    assert pin["semantic_profile"] == "register-io-0.2"
    assert pin["binary_sha256"] == "d1df63cea412d672fbe042b1a2b0e31f5167cfd1ea21c717c4dfcbdf81e8ef72"
    assert pin["source_commit_sha"] == "c241a9a7ca7f04270b8de182719ec64555f04207"
    assert candidate["admission"]["max_inflight"] == 1
    assert candidate["network"]["required"] == "namespace_denied"
    assert "NOT_QUALIFIED" in candidate["status"]
    assert base["safec"]["engine"]["semantic_profile"] == "register-io-0.1"


@pytest.fixture
def context(tmp_path, monkeypatch):
    prof = {
        "id": CANDIDATE,
        "version": 1,
        "_path": "config/factory/profiles/" + CANDIDATE + ".yaml",
        "_sha256": "a" * 64,
        "safec": {
            "engine": {
                "binary": "/unused/qualified-engine",
                "binary_sha256": "b" * 64,
                "source_commit_sha": "c" * 40,
                "semantic_profile": "register-io-0.2",
            }
        },
    }
    local = {
        "id": prof["id"],
        "version": 1,
        "config": prof["_path"],
        "config_sha256": prof["_sha256"],
        "semantic_profile": "register-io-0.2",
    }
    manifest = {"work_order": "CANDIDATE", "local_profile": local}
    (tmp_path / ".forge-run").mkdir()
    monkeypatch.setattr(P, "load", lambda pid: prof)
    monkeypatch.setattr(S.V1, "_manifest", lambda ws: manifest)
    built = []

    def build(ws, *, semantic_profile):
        built.append(semantic_profile)
        return {"registers": []}, b'{"registers":[]}'

    monkeypatch.setattr(S.D, "build", build)
    return tmp_path, prof, manifest, built


@pytest.mark.parametrize(
    "field,value",
    [
        ("config_sha256", "d" * 64),
        ("config_sha256", None),
        ("config", "different.yaml"),
        ("version", 2),
        ("version", True),
        ("id", "other-profile"),
        ("semantic_profile", "register-io-0.1"),
        ("semantic_profile", None),
    ],
)
def test_new_semantics_refuse_unfrozen_profile_before_domain_or_model(context, field, value):
    ws, prof, manifest, built = context
    manifest["local_profile"][field] = value
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(S.EngineFault, match="PROFILE_BINDING"):
        S.Context(ws)
    assert built == []


def test_new_context_accepts_frozen_profile_and_domain_version(context):
    ws, prof, manifest, built = context
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    ctx = S.Context(ws)
    assert built == ["register-io-0.2"] and ctx.pin.semantic_profile == "register-io-0.2"
    assert ctx.binding["policy_sha256"] == prof["_sha256"]


def test_profile_digest_binds_the_bytes_actually_parsed_during_concurrent_edit(tmp_path, monkeypatch):
    p = tmp_path / "one.yaml"
    original = b"schema: forge-c/local-profile/1\nid: one\nprovider: ollama\n"
    p.write_bytes(original)
    parse = yaml.safe_load

    def changed_after_parse(raw):
        result = parse(raw)
        p.write_bytes(original.replace(b"ollama", b"changed"))
        return result

    monkeypatch.setattr(yaml, "safe_load", changed_after_parse)
    profile = P.load("one", directory=tmp_path)
    assert profile["provider"] == "ollama"
    assert profile["_sha256"] == sha256_bytes(original)


def test_frozen_new_profile_cannot_downgrade_to_legacy_semantics(context):
    ws, prof, manifest, built = context
    prof["safec"]["engine"]["semantic_profile"] = "register-io-0.1"
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(S.EngineFault, match="PROFILE_BINDING"):
        S.Context(ws)
    assert built == []


def test_profile_selection_freezes_new_semantics_without_changing_legacy_record(tmp_path, monkeypatch):
    prof = P.load(CANDIDATE)
    env = {k: str(tmp_path / k) for k in prof["deployment"]["writable_env"]}
    monkeypatch.setattr(P, "isolation_issues", lambda *a: [])
    monkeypatch.setattr(P, "endpoint_issues", lambda *a: [])
    monkeypatch.setattr(P, "network_enforcement", lambda: {"status": "DENIED_VERIFIED"})
    monkeypatch.setattr(P, "model_identity", lambda *a: {"status": "MATCH"})
    kw = dict(model="qwen3.6:35b-a3b", provider="ollama", code_model=None, acp_authors=None, acp_inspectors=None, env=env)
    frozen = P.select(CANDIDATE, **kw)
    assert frozen["semantic_profile"] == "register-io-0.2"
    assert frozen["config_sha256"] == prof["_sha256"]
    old = P.select("local-rtx-v2-omniverse2-q36-noreason", **kw)
    assert "semantic_profile" not in old


def test_actual_intake_projection_retains_new_profile_marker(context, tmp_path, monkeypatch):
    from forge_factory import workorder

    ws, prof, manifest, built = context
    local = {**manifest["local_profile"], "status": "EXPERIMENTAL_NOT_QUALIFIED", "timeout_scale": 4}
    example = tmp_path / "example"
    example.mkdir()
    (example / "workorder.json").write_text("{}")
    monkeypatch.setattr(P, "select", lambda *a, **k: local)
    monkeypatch.setattr(workorder, "suspension", lambda provider: None)
    monkeypatch.setattr(workorder, "prepare", lambda *a, **k: (ws, {"work_order": "CANDIDATE"}))
    monkeypatch.setattr(S.S, "call", lambda *a, **k: pytest.fail("intake must never infer"))
    result = workorder.run(example, "CANDIDATE", intake_only=True, profile=CANDIDATE, model="qwen3.6:35b-a3b")
    frozen = json.loads((ws / ".forge-run/manifest.json").read_bytes())["local_profile"]
    assert frozen["semantic_profile"] == "register-io-0.2"
    assert frozen["config_sha256"] == prof["_sha256"]
    assert result["workspace"] == str(ws)


def test_manifest_edit_during_domain_build_is_refused(context, monkeypatch):
    ws, prof, manifest, built = context
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))

    def changed(ws, **kwargs):
        manifest["work_order"] = "OTHER"
        (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
        return {"registers": []}, b'{"registers":[]}'

    monkeypatch.setattr(S.D, "build", changed)
    with pytest.raises(S.EngineFault, match="WORKORDER_BINDING_CHANGED"):
        S.Context(ws)


def test_manifest_edit_after_context_never_reaches_the_engine(context, monkeypatch):
    ws, prof, manifest, built = context
    path = ws / ".forge-run/manifest.json"
    path.write_text(json.dumps(manifest))
    ctx = S.Context(ws)
    path.write_text(path.read_text() + " ")
    monkeypatch.setattr(S.CL, "invoke", lambda *a, **k: pytest.fail("changed binding reached engine"))
    with pytest.raises(S.EngineFault, match="WORKORDER_BINDING_CHANGED"):
        ctx.validate([], "must-not-run")
    assert ctx.calls == 0
