"""Feature 017 T005: served-model identity (FR-003, FR-011, research R4)."""
import json

import pytest
from forge_factory.modelservice import identity as I


def _weights(tmp_path, content=b"weights-A"):
    d = tmp_path / "w"
    d.mkdir()
    (d / "model-00001.safetensors").write_bytes(content)
    (d / "model-00002.safetensors").write_bytes(b"second")
    (d / "config.json").write_text('{"a": 1}')
    return d


def test_fingerprint_is_stable_and_sensitive(tmp_path):
    d = _weights(tmp_path)
    tok, tpl = tmp_path / "tok.json", tmp_path / "tpl.jinja"
    tok.write_text("tok")
    tpl.write_text("{{ messages }}")
    a = I.fingerprint(d, tokenizer=tok, chat_template=tpl)
    assert a == I.fingerprint(d, tokenizer=tok, chat_template=tpl) and len(a) == 64
    # order independence: the same (path, sha) entries in another order give the same fingerprint
    entries = I.file_entries(d)
    assert I.fingerprint_entries(list(reversed(entries)), I.sha(tok), I.sha(tpl)) == a
    (d / "model-00001.safetensors").write_bytes(b"weights-B")
    assert I.fingerprint(d, tokenizer=tok, chat_template=tpl) != a
    (d / "model-00001.safetensors").write_bytes(b"weights-A")
    tok.write_text("tok2")
    assert I.fingerprint(d, tokenizer=tok, chat_template=tpl) != a
    tok.write_text("tok")
    tpl.write_text("other template")
    assert I.fingerprint(d, tokenizer=tok, chat_template=tpl) != a


def test_single_file_model_fingerprint(tmp_path):
    f = tmp_path / "ornith.gguf"
    f.write_bytes(b"gguf")
    assert I.fingerprint(f) == I.fingerprint_entries([("ornith.gguf", I.sha(f))], None, None)


def _ident(**kw):
    base = dict(name="qwen3.6-35b-a3b-fp8", revision_fingerprint="ab" * 32, precision="fp8", reasoning_mode="off",
                context_limit=65536, engine={"name": "vllm", "version": "0.0.0"}, attested=True)
    base.update(kw)
    return I.build(**base)


def test_identity_validates_and_verify_names_differences():
    a = _ident()
    I.validate(a)
    assert I.verify(a, _ident()) == []
    assert I.verify(a, _ident(revision_fingerprint="cd" * 32)) == ["revision_fingerprint"]
    assert set(I.verify(a, _ident(precision="bf16", context_limit=1))) == {"precision", "context_limit"}
    with pytest.raises(ValueError):
        I.validate({**a, "precision": "fp4"})


def test_lock_lookup_and_refusal():
    lock = {"identities": {"qwen3.6-35b-a3b-fp8": _ident()}}
    assert I.from_lock(lock, "qwen3.6-35b-a3b-fp8")["precision"] == "fp8"
    with pytest.raises(I.IdentityError, match="NOT_IN_LOCK"):
        I.from_lock(lock, "other")
    with pytest.raises(I.IdentityError, match="IDENTITY_MISMATCH:revision_fingerprint"):
        I.require_match(I.from_lock(lock, "qwen3.6-35b-a3b-fp8"), _ident(revision_fingerprint="ee" * 32))


def test_inferred_identity_from_models_endpoint_is_not_attested():
    payload = {"data": [{"id": "qwen3.6-35b-a3b-fp8", "root": "/models/qwen", "max_model_len": 65536},
                        {"id": "ornith", "max_model_len": 131072}]}
    declared = {"precision": "fp8", "reasoning_mode": "off", "revision_fingerprint": "ab" * 32,
                "engine": {"name": "vllm", "version": "unknown"}}
    got = I.inferred_from_models_endpoint(payload, "qwen3.6-35b-a3b-fp8", declared)
    I.validate(got)
    assert got["attested"] is False and got["context_limit"] == 65536 and got["revision_fingerprint"] == "ab" * 32
    with pytest.raises(I.IdentityError, match="MODEL_NOT_OFFERED"):
        I.inferred_from_models_endpoint(payload, "missing", declared)
    # without a declared fingerprint the identity is still well-formed, unattested and named as such
    got = I.inferred_from_models_endpoint(payload, "ornith", {"precision": "other", "reasoning_mode": "on"})
    I.validate(got)
    assert got["attested"] is False and got["engine"]["name"] == "unknown"
    assert json.dumps(got)  # serialisable for evidence
