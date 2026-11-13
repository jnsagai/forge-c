"""Feature 017 T030/T032: engines keep models warm in RAM and swap without disk reads (FR-031)."""
import asyncio
import hashlib
import sys

import httpx
from model_tier.catalog import Model
from model_tier.engines import ProcessEngine, VllmComposeEngine


def _model(**kw):
    base = dict(model="m", engine="vllm", launch_kind="compose", engine_url="http://eng", vram_mib=40000,
                full_capacity={"context_per_sequence": 65536, "sequences": 2}, reasoning_mode="off",
                identity={"name": "m", "revision_fingerprint": "a" * 64, "precision": "fp8", "reasoning_mode": "off",
                          "context_limit": 65536, "engine": {"name": "vllm", "version": "1"}, "attested": True},
                load_timeout_s=5, warm_strategy="vllm_sleep", ram_gib=35, compose_service="engine-m")
    base.update(kw)
    return Model(**base)


class Ram:
    def __init__(self, warm=True, resident=True):
        self.warm, self.resident, self.reserved, self.staged_from = warm, resident, {}, []

    def decide(self, gib):
        return ("warm", "") if self.warm else ("cold", "RAM_BUDGET")

    def reserve(self, name, gib):
        self.reserved[name] = gib

    def stage(self, name, src, sha):
        self.staged_from.append(src)

        class S:
            path = src.with_name("staged-" + src.name)
        return S()

    def check(self, staged):
        return (True, "") if self.resident else (False, "NOT_RESIDENT:0.40")


def _vllm_http(calls, models_len=65536):
    def h(req):
        calls.append((req.method, req.url.path + (("?" + req.url.query.decode()) if req.url.query else ""),
                      req.headers.get("authorization")))
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "m", "max_model_len": models_len}]})
        return httpx.Response(200, json={})
    return httpx.AsyncClient(transport=httpx.MockTransport(h))


def test_vllm_sleep_keeps_weights_in_ram_and_wakes_without_restart():
    calls, cmds = [], []

    async def cmd(argv):
        cmds.append(argv[-3:])
        return 0, ""

    async def go():
        e = VllmComposeEngine(_model(), "compose.yaml", "p", "ENGINE-KEY", Ram(), http=_vllm_http(calls), cmd=cmd)
        prep = await e.prepare()
        load = await e.load()
        await e.unload()
        load2 = await e.load()
        ident = await e.identity()
        return prep, load, load2, ident, e
    prep, load, load2, ident, e = asyncio.run(go())
    assert prep["warm"] and load["warm"] and load2["warm"] and ident["name"] == "m"
    assert cmds == [["up", "-d", "engine-m"]]  # started exactly once; swaps are sleep/wake only
    paths = [c[1] for c in calls if c[0] == "POST"]
    assert paths == ["/sleep?level=1", "/wake_up", "/sleep?level=1", "/wake_up"]
    assert all(c[2] == "Bearer ENGINE-KEY" for c in calls)


def test_vllm_cold_when_ram_budget_is_short():
    calls, cmds = [], []

    async def cmd(argv):
        cmds.append(argv[-3:])
        return 0, ""

    async def go():
        e = VllmComposeEngine(_model(), "compose.yaml", "p", None, Ram(warm=False), http=_vllm_http(calls), cmd=cmd)
        prep = await e.prepare()
        load = await e.load()
        await e.unload()
        return prep, load
    prep, load = asyncio.run(go())
    assert not prep["warm"] and prep["reason"] == "RAM_BUDGET" and not load["warm"]
    assert cmds == [["up", "-d", "engine-m"], ["stop", "engine-m"][-3:]] or cmds[-1][-2:] == ["stop", "engine-m"]


def test_identity_reports_a_different_context_or_a_missing_model():
    async def go():
        e = VllmComposeEngine(_model(), "c", "p", None, Ram(), http=_vllm_http([], models_len=32768),
                              cmd=lambda a: asyncio.sleep(0, (0, "")))
        return await e.identity()
    assert asyncio.run(go())["context_limit"] == 32768


def test_process_engine_starts_on_the_staged_copy_and_stops_cleanly(tmp_path):
    blob = tmp_path / "ornith.gguf"
    blob.write_bytes(b"gguf")
    script = tmp_path / "server.py"
    script.write_text("import sys,time\nopen(sys.argv[2],'w').write(sys.argv[1])\ntime.sleep(60)\n")
    out = tmp_path / "argv.txt"
    m = _model(model="ornith", engine="llama.cpp", launch_kind="process", compose_service=None, warm_strategy="ram_staged_file",
               ram_gib=38, process={"binary": sys.executable, "args": [str(script), "{model_path}", str(out)],
                                    "model_path": str(blob), "model_sha256": hashlib.sha256(b"gguf").hexdigest()})
    healthy = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))

    async def go(resident):
        ram = Ram(resident=resident)
        e = ProcessEngine(m, ram, http=healthy, log_dir=tmp_path / "logs")
        prep = await e.prepare()
        load = await e.load()
        for _ in range(100):
            if out.exists() and out.read_text():
                break
            await asyncio.sleep(0.05)
        used = out.read_text()
        out.unlink()
        pid = e.proc.pid
        await e.unload()
        return prep, load, used, pid, ram
    prep, load, used, pid, ram = asyncio.run(go(True))
    assert prep["warm"] and load["warm"] and used.endswith("staged-ornith.gguf") and ram.staged_from == [blob]
    import os
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    assert not alive
    # evicted from RAM: this load reads from disk and says why
    prep, load, used, _, _ = asyncio.run(go(False))
    assert not load["warm"] and load["reason"].startswith("NOT_RESIDENT") and used == str(blob)


def test_page_cache_strategy_uses_the_original_file_and_rewarms_when_evicted(tmp_path):
    from model_tier.ramstage import RamStage

    blob = tmp_path / "qwen38.gguf"
    blob.write_bytes(b"g" * 4096)
    script = tmp_path / "server.py"
    script.write_text("import sys,time\nopen(sys.argv[2],'w').write(sys.argv[1])\ntime.sleep(60)\n")
    out = tmp_path / "argv.txt"
    m = _model(model="qwen3.8:27b-q8_0", engine="llama.cpp", launch_kind="process", compose_service=None,
               warm_strategy="page_cache", ram_gib=0.001,
               process={"binary": sys.executable, "args": [str(script), "{model_path}", str(out)], "model_path": str(blob),
                        "model_sha256": "2" * 64})
    healthy = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable:   104857600 kB\n")
    resident = {"v": 1.0}
    ram = RamStage(tmp_path / "stage", budget_gib=1, reserve_gib=0, meminfo=meminfo, residency=lambda p: resident["v"])

    async def go():
        e = ProcessEngine(m, ram, http=healthy, log_dir=tmp_path / "logs")
        prep = await e.prepare()
        load = await e.load()
        for _ in range(100):
            if out.exists() and out.read_text():
                break
            await asyncio.sleep(0.05)
        used = out.read_text()
        out.unlink()
        await e.unload()
        resident["v"] = 0.2  # the host evicted it: this load still works, from disk, and says why
        load2 = await e.load()
        await e.unload()
        return prep, load, used, load2
    prep, load, used, load2 = asyncio.run(go())
    assert prep["warm"] and load["warm"] and used == str(blob)  # no copy: the original file, resident in the page cache
    assert not load2["warm"] and load2["reason"].startswith("NOT_RESIDENT")
    assert not (tmp_path / "stage" / "qwen3.8_27b-q8_0").exists()  # nothing staged into tmpfs
