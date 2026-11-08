"""Feature 017 T035: the catalog is generated from the owner lane's profile and the recipe lock, never hand-typed."""
import json

import pytest
import yaml
from forge_factory.modelservice import catalog_gen as G
from model_tier import catalog as C

LIVE = ["/srv/lrtx/ollama-0.34.0/lib/ollama/llama-server", "--model", "/srv/lrtx/ollama-models/blobs/sha256-" + "d" * 64,
        "--alias", "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0", "--host", "127.0.0.1", "--port", "11457", "--no-webui",
        "--offline", "-c", "262144", "-np", "1", "--jinja", "--reasoning", "on", "--cache-type-k", "f16", "--cache-type-v",
        "f16", "--flash-attn", "on", "-b", "2048", "-ub", "2048", "--spec-type", "none", "--gpu-layers", "all", "--fit", "off"]


def spec(root, prof, ports, env, model=None):
    argv = list(LIVE)
    argv[argv.index("--port") + 1] = str(ports["llama"])
    return argv, {"LD_LIBRARY_PATH": "/srv/lib", "OTHER": "x"}, "http://h/health", ["hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"]


def _inputs(tmp_path, with_qwen=True):
    lock = {"images": {"vllm-openai": "sha256:" + "e" * 64}, "model_files": {}}
    if with_qwen:
        lock["model_files"][G.QWEN] = {"files": [{"path": "config.json", "sha256": "1" * 64, "bytes": 10},
                                                 {"path": "model.safetensors", "sha256": "2" * 64, "bytes": 37 * 2**30}]}
    (tmp_path / "lock.json").write_text(json.dumps(lock))
    params = {"site": "omniverse2", "parameters": {k: {"value": v, "description": k} for k, v in {
        "gpu_vram_mib": 49140, "reference_context": 65536, "reference_sequences": 2, "ram_budget_gib": 80,
        "ram_reserve_gib": 24}.items()}, "not_proven_here": []}
    (tmp_path / "params.yaml").write_text(yaml.safe_dump(params))
    return tmp_path / "lock.json", tmp_path / "params.yaml"


def test_ornith_keeps_todays_full_capacity_arguments(tmp_path):
    lock, params = _inputs(tmp_path)
    doc = G.generate(prof={}, root=tmp_path, lock_path=lock, params_path=params, out=tmp_path / "catalog.yaml", spec=spec)
    orn = next(m for m in doc["models"] if m["engine"] == "llama.cpp")
    args = orn["process"]["args"]
    # identical to the live command line except the staged model path and the internal port
    expect = list(LIVE[1:])
    expect[expect.index("--model") + 1] = "{model_path}"
    expect[expect.index("--port") + 1] = str(G.ORNITH_PORT)
    assert args == expect and orn["process"]["binary"] == LIVE[0]
    assert orn["full_capacity"] == {"context_per_sequence": 262144, "sequences": 1, "kv_cache_type": "f16",
                                    "batch_tokens": 2048, "microbatch_tokens": 2048}
    assert orn["reasoning_mode"] == "on" and orn["warm_strategy"] == "ram_staged_file"
    assert orn["process"]["env"] == {"LD_LIBRARY_PATH": "/srv/lib"} and orn["process"]["model_sha256"] == "d" * 64
    assert orn["model"] == "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"  # the name the factory already requests


def test_catalog_validates_and_pins_identities_in_the_lock(tmp_path):
    lock, params = _inputs(tmp_path)
    G.generate(prof={}, root=tmp_path, lock_path=lock, params_path=params, out=tmp_path / "catalog.yaml", spec=spec)
    cat = C.load(tmp_path / "catalog.yaml", lock)
    assert list(cat.models) == [G.QWEN, "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"]  # vLLM first: it needs a free GPU
    q = cat.models[G.QWEN]
    assert q.warm_strategy == "vllm_sleep" and q.reasoning_mode == "off" and q.context == 65536 and q.sequences == 2
    assert q.identity["engine"]["image_digest"] == "sha256:" + "e" * 64 and q.ram_gib > 37
    assert set(json.loads(lock.read_text())["identities"]) == set(cat.models)


def test_reference_model_must_be_pinned_first(tmp_path):
    lock, params = _inputs(tmp_path, with_qwen=False)
    with pytest.raises(RuntimeError, match="NOT_PINNED_YET"):
        G.generate(prof={}, root=tmp_path, lock_path=lock, params_path=params, out=tmp_path / "c.yaml", spec=spec)
    assert not (tmp_path / "c.yaml").exists()
