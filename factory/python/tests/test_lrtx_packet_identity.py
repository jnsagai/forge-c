"""G3 / D10 (process-first design, owner 2026-10-31): the structured packet hash binds the served model identity.

Before: `input_hash` covered the model *name* and sampling only, so a different GGUF under the same alias, a changed
reasoning setting, context length or probed schema mode silently reused checkpointed answers. The identity is
derived from the work order's selected local profile (manifest `local_profile`), deliberately without
`adapter_revision` (the factory commit): code changes keep the existing revision/revalidation handling (D10).
"""
from __future__ import annotations

import json

import pytest
from forge_factory.lrtx import profile as lp
from forge_factory.lrtx import structured as S

PROFILE_ID = "g3-identity-fixture"
MODEL = "fixture-model:q8"
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["a"], "properties": {"a": {"type": "string"}}}


def _profile(digest="a" * 64, quant="Q8_0", ctx="32768", effort="medium", role_effort="xhigh", reasoning="on"):
    return (
        "schema: forge-c/local-profile/1\n"
        f"id: {PROFILE_ID}\n"
        "version: 1\n"
        "models:\n"
        f"  default: {MODEL}\n"
        "  allowed:\n"
        f"    {MODEL}:\n"
        f"      digest: {digest}\n"
        f"      quantization: {quant}\n"
        "runtime:\n"
        "  ollama:\n"
        f'    OLLAMA_CONTEXT_LENGTH: "{ctx}"\n'
        "  llama_server:\n"
        f"    reasoning: '{reasoning}'\n"
        "gateway:\n"
        "  reasoning:\n"
        f"    {MODEL}:\n"
        f"      effort: {effort}\n"
        "      role_efforts:\n"
        f"        swe1-inspector: {role_effort}\n"
    )


@pytest.fixture
def bound(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    monkeypatch.setattr(lp, "PROFILE_DIR", profiles)
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))

    def write(text, config_sha="c" * 64):
        (profiles / f"{PROFILE_ID}.yaml").write_text(text)
        (ws / ".forge-run/manifest.json").write_text(
            json.dumps({"local_profile": {"id": PROFILE_ID, "config_sha256": config_sha}}))

    token = S.RECOVERY_WORKSPACE.set(ws)
    yield write
    S.RECOVERY_WORKSPACE.reset(token)


def _packet(role="swe1-author", model=MODEL):
    return S.packet(phase="SWE.1", task="identity-fixture", role=role, instructions="Answer.", sources=[], criteria=[],
                    output_schema=SCHEMA, model=model, with_skill=False, with_lessons=False)


def test_same_identity_reuses_the_hash(bound):
    bound(_profile())
    assert _packet()["input_hash"] == _packet()["input_hash"]


@pytest.mark.parametrize("change", [
    {"digest": "b" * 64},          # another GGUF under the same alias
    {"quant": "Q4_K_M"},           # precision
    {"ctx": "65536"},              # context envelope
    {"effort": "high"},            # gateway reasoning effort
    {"reasoning": "off"},          # served reasoning mode
])
def test_every_identity_field_invalidates_the_hash(bound, change):
    bound(_profile())
    before = _packet()["input_hash"]
    bound(_profile(**change))
    assert _packet()["input_hash"] != before


def test_role_effort_binds_only_the_role_it_applies_to(bound):
    bound(_profile())
    author, inspector = _packet()["input_hash"], _packet(role="swe1-inspector")["input_hash"]
    bound(_profile(role_effort="low"))
    assert _packet()["input_hash"] == author
    assert _packet(role="swe1-inspector")["input_hash"] != inspector


def test_profile_config_sha_invalidates_the_hash(bound):
    bound(_profile(), config_sha="c" * 64)
    before = _packet()["input_hash"]
    bound(_profile(), config_sha="d" * 64)
    assert _packet()["input_hash"] != before


def test_probed_schema_mode_invalidates_the_hash(bound):
    bound(_profile())
    before = _packet()["input_hash"]
    path = S.capability_path(MODEL)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"digest": "a" * 64, "selected_mode": "json_object", "probed_at": "t"}))
    assert _packet()["input_hash"] != before


def test_identity_excludes_adapter_revision_and_never_reaches_the_prompt(bound):
    bound(_profile())
    p = _packet()
    assert p["identity"]["model_digest"] == "a" * 64
    assert "adapter_revision" not in p["identity"]
    assert all("a" * 64 not in m["content"] for m in p["_messages"])


def test_unbound_packet_keeps_the_legacy_hash_shape(monkeypatch):
    token = S.RECOVERY_WORKSPACE.set(None)
    try:
        assert "identity" not in _packet()
    finally:
        S.RECOVERY_WORKSPACE.reset(token)
