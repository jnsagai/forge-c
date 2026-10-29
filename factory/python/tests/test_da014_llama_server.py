"""F014 serving runtime (owner 2026-10-26: "install a new runtime on Omniverse2 to allow parallel model calls"): the
pinned model file served by the llama.cpp server bundled with Ollama 0.34.0 with N request slots, and the gateway
routing only that model's chat requests to it."""
import copy
import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as gw
from forge_factory.lrtx import profile as lp
from forge_factory.lrtx import stack

LS = "local-rtx-v2-omniverse2-q36-noreason-ls"
MODEL = "qwen3.6:35b-a3b"


def _root(tmp_path, size=11):
    r = tmp_path / "lrtx"
    blob = b"g" * size
    layer = "sha256:" + hashlib.sha256(blob).hexdigest()
    man = r / "ollama-models/manifests/registry.ollama.ai/library/qwen3.6/35b-a3b"
    man.parent.mkdir(parents=True)
    man.write_text(json.dumps({"layers": [{"mediaType": "application/vnd.ollama.image.model", "digest": layer,
                                           "size": len(blob)}]}))
    (r / "ollama-models/blobs").mkdir()
    (r / "ollama-models/blobs" / layer.replace(":", "-")).write_bytes(blob)
    prof = copy.deepcopy(lp.load(LS))
    prof["models"]["allowed"][MODEL]["digest"] = hashlib.sha256(man.read_bytes()).hexdigest()
    return r, prof


def test_the_variant_profile_serves_the_pinned_model_with_two_slots():
    prof = lp.load(LS)
    assert prof["runtime"]["llama_server"] == {"model": MODEL, "slots": 2} and prof["admission"]["max_inflight"] == 2
    base = lp.load("local-rtx-v2-omniverse2-q36-noreason")
    assert prof["models"] == base["models"] and prof["structured"] == base["structured"]  # one serving factor only
    assert prof["deployment"]["ports"]["llama"] not in prof["deployment"]["forbidden_ports"]

@pytest.mark.parametrize("profile_id,context", [
    ("local-rtx-v2-omniverse2-q38-aspice-mtp", 131072),
    ("local-rtx-v2-omniverse2-q38-afo-repair-mtp", 131072),
    ("local-rtx-v2-omniverse2-q38-afo-max-mtp", 262144),
])
def test_q38_mtp_keeps_xhigh_one_slot_and_verified_q8_blob(tmp_path, profile_id, context):
    r, old = _root(tmp_path)
    source = r / "ollama-models/manifests/registry.ollama.ai/library/qwen3.6/35b-a3b"
    target = source.parents[1] / "qwen3.8/27b-q8_0"
    target.parent.mkdir()
    target.write_bytes(source.read_bytes())
    p = copy.deepcopy(lp.load(profile_id))
    model = "qwen3.8:27b-q8_0"
    p["models"]["allowed"][model]["digest"] = old["models"]["allowed"][MODEL]["digest"]
    assert p["admission"]["max_inflight"] == 1
    argv, _, _, models = stack.llama_server_spec(r, p, p["deployment"]["ports"], {})
    assert models == [model]
    assert argv[argv.index("-np") + 1] == "1"
    assert argv[argv.index("-c") + 1] == str(context)
    config = stack.fabro_config({"root": r, "profile": p, "ports": p["deployment"]["ports"]})
    assert f"context_tokens = {context}" in config and "max_output_tokens = 16384" in config
    assert argv[argv.index("--reasoning") + 1] == "on"
    assert argv[argv.index("--reasoning-effort") + 1] == "xhigh"
    assert argv[argv.index("--reasoning-format") + 1] == "deepseek"
    assert argv[argv.index("--spec-type") + 1] == "draft-mtp"
    assert argv[argv.index("--spec-draft-n-max") + 1] == "3"
    assert argv[argv.index("--gpu-layers") + 1] == "all"
    for wrong in (True, 0, 9, "3"):
        p["runtime"]["llama_server"]["mtp_draft"] = wrong
        with pytest.raises(RuntimeError, match="MTP_CONFIGURATION_INVALID"):
            stack.llama_server_spec(r, p, p["deployment"]["ports"], {})


def test_the_server_command_comes_from_the_profile_and_the_verified_model_file(tmp_path):
    r, prof = _root(tmp_path)
    argv, env, health, models = stack.llama_server_spec(r, prof, prof["deployment"]["ports"], {"PATH": "/usr/bin"})
    blob = next((r / "ollama-models/blobs").iterdir())
    assert argv[0].endswith("ollama-0.34.0/lib/ollama/llama-server") and argv[argv.index("--model") + 1] == str(blob)
    assert argv[argv.index("-np") + 1] == "2" and argv[argv.index("-c") + 1] == str(2 * 65536)
    assert argv[argv.index("--port") + 1] == "11457" and "--jinja" in argv and argv[argv.index("--reasoning") + 1] == "off"
    assert "--spec-type" not in argv and env["GGML_BACKEND_PATH"].endswith("cuda_v13/libggml-cuda.so")
    assert health == "http://127.0.0.1:11457/health" and models == [MODEL]
    prof["runtime"]["llama_server"]["mtp_draft"] = 2
    argv, *_ = stack.llama_server_spec(r, prof, prof["deployment"]["ports"], {})
    assert argv[argv.index("--spec-type") + 1] == "draft-mtp"
    assert stack.llama_server_spec(r, lp.load("local-rtx-v2-omniverse2-q36-noreason"), {}, {}) is None


def test_larger_context_uses_bound_batches_without_changing_precision_or_legacy_defaults(tmp_path):
    r, prof = _root(tmp_path)
    before, *_ = stack.llama_server_spec(r, prof, prof["deployment"]["ports"], {})
    assert before[before.index("-b") + 1] == before[before.index("-ub") + 1] == "2048"
    prof["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"] = "262144"
    prof["runtime"]["llama_server"].update(slots=1, batch_tokens=1024, microbatch_tokens=512)
    argv, *_ = stack.llama_server_spec(r, prof, prof["deployment"]["ports"], {})
    assert argv[argv.index("-c") + 1] == "262144" and argv[argv.index("-np") + 1] == "1"
    assert argv[argv.index("-b") + 1] == "1024" and argv[argv.index("-ub") + 1] == "512"
    assert argv[argv.index("--cache-type-k") + 1] == before[before.index("--cache-type-k") + 1]
    assert argv[argv.index("--cache-type-v") + 1] == before[before.index("--cache-type-v") + 1]
    for values in ({"batch_tokens": True}, {"microbatch_tokens": 2048}, {"batch_tokens": 65537},
                   {"microbatch_tokens": 0}):
        invalid = copy.deepcopy(prof)
        invalid["runtime"]["llama_server"].update(values)
        with pytest.raises(RuntimeError, match="BATCH_CONFIGURATION_INVALID"):
            stack.llama_server_spec(r, invalid, invalid["deployment"]["ports"], {})


def test_another_model_file_or_a_truncated_blob_is_refused(tmp_path):
    r, prof = _root(tmp_path)
    bad = copy.deepcopy(prof)
    bad["models"]["allowed"][MODEL]["digest"] = "0" * 64
    with pytest.raises(RuntimeError, match="LLAMA_SERVER_MODEL_DIGEST_MISMATCH"):
        stack.llama_server_spec(r, bad, bad["deployment"]["ports"], {})
    blob = next((r / "ollama-models/blobs").iterdir())
    blob.write_bytes(b"g" * 5)
    with pytest.raises(RuntimeError, match="LLAMA_SERVER_MODEL_BLOB_MISSING"):
        stack.llama_server_spec(r, prof, prof["deployment"]["ports"], {})


def test_the_gateway_routes_only_the_served_model_to_the_llama_server(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("FORGE_GATEWAY_MAX_INFLIGHT", raising=False)
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({MODEL: "http://llama:11457"}))
    seen = []

    def upstream(req: httpx.Request) -> httpx.Response:
        seen.append(f"{req.url.host}:{req.url.port or 80}{req.url.path}")
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "{}"},
                                                      "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 3, "completion_tokens": 1}})

    c = TestClient(gw.create_app("http://up", tmp_path / "usage.jsonl", transport=httpx.MockTransport(upstream)))
    for model in (MODEL, "qwen3-coder:30b"):
        r = c.post("/v1/chat/completions", json={"model": model, "messages": [{"role": "user", "content": "x"}]})
        assert r.status_code == 200
    assert seen == ["llama:11457/v1/chat/completions", "up:80/v1/chat/completions"]
