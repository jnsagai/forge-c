"""CAPA-234 (017 smoke window 20261111T093853Z-23268f): every swap to the author model
hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0 failed LOAD_FAILED FileNotFoundError within 0.7 s, 10 of 10, while qwen3.8
loaded. ProcessEngine.load opened its engine log at log_dir/<model id>.log: the slashes of a Hugging Face model id made
that a path into directories that do not exist, so the engine was never spawned. The log file uses the model's
file-system-safe stage name."""
import asyncio
import hashlib
import sys

import httpx
from model_tier.catalog import Model
from model_tier.engines import ProcessEngine, stage_name

ID = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"


def test_a_model_id_with_slashes_loads_and_logs_under_its_stage_name(tmp_path):
    blob = tmp_path / "ornith.gguf"
    blob.write_bytes(b"gguf")
    script = tmp_path / "server.py"
    script.write_text("import time\nprint('engine up', flush=True)\ntime.sleep(60)\n")
    m = Model(model=ID, engine="llama.cpp", launch_kind="process", engine_url="http://eng", vram_mib=40000,
              full_capacity={"context_per_sequence": 65536, "sequences": 1}, reasoning_mode="on",
              identity={"name": ID, "revision_fingerprint": "a" * 64, "precision": "other", "reasoning_mode": "on",
                        "context_limit": 65536, "engine": {"name": "llama.cpp", "version": "1"}, "attested": True},
              load_timeout_s=5, warm_strategy="ram_staged_file", ram_gib=38, compose_service=None,
              process={"binary": sys.executable, "args": [str(script), "{model_path}"], "model_path": str(blob),
                       "model_sha256": hashlib.sha256(b"gguf").hexdigest()})
    healthy = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))

    async def go():
        e = ProcessEngine(m, None, http=healthy, log_dir=tmp_path / "logs")
        load = await e.load()
        await e.unload()
        return load
    assert asyncio.run(go())["warm"] is False
    assert (tmp_path / "logs" / f"{stage_name(ID)}.log").is_file()
    assert [p.name for p in (tmp_path / "logs").iterdir()] == [f"{stage_name(ID)}.log"]
