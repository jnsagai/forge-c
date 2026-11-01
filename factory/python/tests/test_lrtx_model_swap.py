"""In-run model swap (owner 2026-10-31: "use the hf.co pin name, go ahead with the swap"): Ornith authors, Qwen3.8
inspects, one model served at a time; serve nodes swap the stack's llama-server, the gateway refuses a request for a
model that is not the one served, and a failed swap ends the run closed. No GPU, no processes."""
import copy
import hashlib
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as gw
from forge_factory.lrtx import profile as lp
from forge_factory.lrtx import stack

PID = "local-rtx-v2-omniverse2-ornith-author-q38-inspector"
ORN = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"
QWEN = "qwen3.8:27b-q8_0"
IDENT = {"boot_id": "b", "start_ticks": "100", "netns": "net:[1]", "uid": 1000}


def _root(tmp_path):
    """Both pinned models as small fake files with the profile's digests rebound to them."""
    r = tmp_path / "lrtx"
    prof = copy.deepcopy(lp.load(PID))
    for model, rel in ((QWEN, "registry.ollama.ai/library/qwen3.8/27b-q8_0"),
                       (ORN, "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF/Q8_0")):
        blob = model.encode() * 3
        layer = "sha256:" + hashlib.sha256(blob).hexdigest()
        man = r / "ollama-models/manifests" / rel
        man.parent.mkdir(parents=True)
        man.write_text(json.dumps({"layers": [{"mediaType": "application/vnd.ollama.image.model", "digest": layer,
                                               "size": len(blob)}]}))
        (r / "ollama-models/blobs").mkdir(exist_ok=True)
        (r / "ollama-models/blobs" / layer.replace(":", "-")).write_bytes(blob)
        prof["models"]["allowed"][model]["digest"] = hashlib.sha256(man.read_bytes()).hexdigest()
        if model == ORN:
            prof["runtime"]["llama_server_alternates"][ORN]["model_blob_sha256"] = layer.split(":")[1]
    return r, prof


def test_registry_qualified_pin_resolves_its_manifest_and_refuses_traversal(tmp_path):
    m = tmp_path / "m"
    assert stack._manifest(m, ORN) == m / "manifests/hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF/Q8_0"
    assert stack._manifest(m, QWEN) == m / "manifests/registry.ollama.ai/library/qwen3.8/27b-q8_0"
    with pytest.raises(RuntimeError, match="MODEL_NAME_INVALID"):
        stack._manifest(m, "hf.co/../x:Q8_0")


def test_the_profile_serves_both_pinned_models_one_at_a_time():
    prof = lp.load(PID)
    assert stack.served_models(prof) == [QWEN, ORN]
    assert lp.role_models(prof) == {"author": ORN, "inspector": QWEN}
    assert lp.selection_issues(prof, model=QWEN, provider=prof["provider"], code_model=None, acp_authors=None,
                               acp_inspectors=None) == []
    bad = copy.deepcopy(prof)
    bad["structured"]["role_models"]["author"] = "unpinned:latest"
    assert "PROFILE_SERVED_MODEL_NOT_ALLOWED:unpinned:latest" in lp.selection_issues(
        bad, model=QWEN, provider=prof["provider"], code_model=None, acp_authors=None, acp_inspectors=None)


def test_alternate_spec_is_the_standalone_ornith_server_and_the_primary_is_unchanged(tmp_path):
    r, prof = _root(tmp_path)
    ports = prof["deployment"]["ports"]
    argv, _env, health, models = stack.llama_server_spec(r, prof, ports, {}, ORN)
    assert models == [ORN] and argv[argv.index("--alias") + 1] == ORN and health.endswith(f":{ports['llama']}/health")
    assert argv[argv.index("-c") + 1] == "65536" and argv[argv.index("--reasoning") + 1] == "off"
    assert argv[argv.index("--spec-type") + 1] == "none" and argv[argv.index("--fit") + 1] == "off"
    assert argv[argv.index("-b") + 1] == "2048" and "--reasoning-effort" not in argv
    primary, *_ = stack.llama_server_spec(r, prof, ports, {})
    base = copy.deepcopy(lp.load("local-rtx-v2-omniverse2-q38-aspice-stepwise-medium"))
    base["models"]["allowed"][QWEN]["digest"] = prof["models"]["allowed"][QWEN]["digest"]
    assert primary == stack.llama_server_spec(r, base, ports, {})[0]  # the Qwen server is the stepwise profile's
    prof["runtime"]["llama_server_alternates"][ORN]["model_blob_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="BLOB_PIN_MISMATCH"):
        stack.llama_server_spec(r, prof, ports, {}, ORN)
    with pytest.raises(RuntimeError, match="NOT_SERVED"):
        stack.llama_server_spec(r, prof, ports, {}, "qwen3-coder:30b")


def test_gateway_refuses_a_request_for_a_model_that_is_not_served(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("FORGE_GATEWAY_MAX_INFLIGHT", raising=False)
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({QWEN: "http://llama:1", ORN: "http://llama:1"}))
    monkeypatch.setenv("FORGE_GATEWAY_VERIFY_SERVED", "1")
    served, chats = [ORN], []

    def upstream(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": m} for m in served]})
        chats.append(json.loads(req.content)["model"])
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "{}"},
                                                      "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 3, "completion_tokens": 1}})

    c = TestClient(gw.create_app("http://up", tmp_path / "usage.jsonl", transport=httpx.MockTransport(upstream)))
    ask = lambda m: c.post("/v1/chat/completions", json={"model": m, "messages": [{"role": "user", "content": "x"}]})  # noqa: E731
    assert ask(ORN).status_code == 200
    r = ask(QWEN)
    assert r.status_code == 503 and r.json()["error"]["type"] == "served_model_mismatch"
    assert chats == [ORN]  # the mismatched request never reached the model
    served[:] = [QWEN]
    assert ask(QWEN).status_code == 200 and chats == [ORN, QWEN]


def test_packet_identity_and_context_follow_the_served_model(tmp_path):
    from forge_factory.lrtx import structured as S

    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"local_profile": {"id": PID}}))
    o, q = S.packet_identity(ws, ORN, "swe1-author"), S.packet_identity(ws, QWEN, "swe1-inspector")
    assert o["context_tokens"] == 65536 and o["reasoning"]["served"] == {"reasoning": "off"}
    assert o["reasoning"]["effort"] == "none" and o["precision"] == "Q8_0"
    assert q["context_tokens"] == 262144 and q["reasoning"]["effort"] == "medium"
    assert o["model_digest"] != q["model_digest"]


class _Stack:
    """A fake running stack for `serve`: services.json, a holder in this namespace, scripted HTTP and processes."""

    def __init__(self, tmp_path, monkeypatch, current=QWEN, busy=False, comes_up=True):
        self.r, self.prof = _root(tmp_path)
        (self.r / "run").mkdir(parents=True)
        (self.r / "logs").mkdir()
        self.served, self.killed, self.started = [current] if current else [], [], []
        self.s = {"profile": self.prof, "root": self.r, "ports": self.prof["deployment"]["ports"]}
        argv = ["llama-server", "--alias", current] if current else []
        rec = {"processes": {"llama_server": {"pid": 4242, "argv": argv, "identity": IDENT}} if current else {}}
        (self.r / "run/services.json").write_text(json.dumps(rec))
        mp = monkeypatch
        mp.setattr(stack, "_holder", lambda s: 1)
        mp.setattr(stack.os, "readlink", lambda p: "net:[1]")
        mp.setattr(stack, "envmap", lambda s: {})
        mp.setattr(stack, "managed_serving", lambda: False)
        mp.setattr(stack, "_alive", lambda pid, marker: pid in (4242, 5151) and pid not in self.killed)
        mp.setattr(stack, "process_identity", lambda pid: {**IDENT, "uid": 0})  # seen from inside the userns
        mp.setattr(stack, "_vram_free_mib", lambda: 48000)
        mp.setattr(stack.os, "kill", lambda pid, sig: (self.killed.append(pid), self.served.clear()))
        mp.setattr(stack.time, "sleep", lambda s: None)

        def get(url, holder, env, inside):
            if url.endswith("/health"):
                return json.dumps({"status": "ok", "admission": {"inflight": 1 if busy else 0, "waiting": 0}}) \
                    if ":" + str(self.s["ports"]["gateway"]) in url else ("ok" if self.served else None)
            return json.dumps({"data": [{"id": m} for m in self.served]})
        mp.setattr(stack, "_get", get)
        outer = self

        class P:
            pid = 5151

            def __init__(self, argv, **_k):
                outer.started.append(argv)
                if comes_up:
                    outer.served[:] = [argv[argv.index("--alias") + 1]]
                self.dead = False

            def poll(self):
                return None if not self.dead and comes_up else 1

            def kill(self):
                self.dead = True
        mp.setattr(stack.subprocess, "Popen", P)

    def swaps(self):
        return [json.loads(x) for x in (self.r / "run/model-swaps.jsonl").read_text().splitlines()]


def test_serve_is_a_no_op_when_the_model_is_already_served(tmp_path, monkeypatch):
    st = _Stack(tmp_path, monkeypatch, current=ORN)
    assert stack.serve(st.s, ORN)["result"] == "ALREADY_SERVED" and st.killed == [] and st.started == []


def test_serve_swaps_stop_then_start_and_records_it(tmp_path, monkeypatch):
    st = _Stack(tmp_path, monkeypatch, current=QWEN)
    ws = tmp_path / "ws"
    out = stack.serve(st.s, ORN, ws)
    assert out["result"] == "SWAPPED" and out["from"] == QWEN and out["to"] == ORN and st.killed == [4242]
    assert st.started and st.started[0][st.started[0].index("--alias") + 1] == ORN
    rec = json.loads((st.r / "run/services.json").read_text())["processes"]["llama_server"]
    assert rec["model"] == ORN and rec["pid"] == 5151
    assert (ws / ".forge-run/lrtx/serving/model-swaps.jsonl").is_file() and st.swaps()[-1]["result"] == "SWAPPED"


def test_serve_refuses_while_the_gateway_is_busy(tmp_path, monkeypatch):
    st = _Stack(tmp_path, monkeypatch, current=QWEN, busy=True)
    with pytest.raises(RuntimeError, match="GATEWAY_BUSY"):
        stack.serve(st.s, ORN)
    assert st.killed == [] and st.swaps()[-1]["result"] == "REFUSED"


def test_a_failed_swap_leaves_no_server_and_fails_closed(tmp_path, monkeypatch):
    st = _Stack(tmp_path, monkeypatch, current=QWEN, comes_up=False)
    monkeypatch.setitem(st.prof["runtime"]["llama_server_swap"], "health_timeout_s", 0.01)
    with pytest.raises(RuntimeError, match="MODEL_SWAP_NOT_SERVED"):
        stack.serve(st.s, ORN)
    assert "llama_server" not in json.loads((st.r / "run/services.json").read_text())["processes"]
    assert st.swaps()[-1]["result"] == "FAILED"


def test_serve_refuses_a_model_the_profile_does_not_serve(tmp_path, monkeypatch):
    st = _Stack(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="MODEL_NOT_SERVED"):
        stack.serve(st.s, "qwen3-coder:30b")


def test_graph_serves_each_model_before_the_node_that_uses_it(monkeypatch):
    from forge_factory.workflow.builder import build
    from forge_factory.workorder import local_profile_structured

    monkeypatch.setenv("FORGE_LRTX_ROOT", "/x/lrtx")
    st = local_profile_structured({"id": PID}, {"layer": "LL"}, QWEN)
    assert st["author_model"] == ORN and st["inspector_model"] == QWEN
    dot, _nodes = build("WO-X", layer="LL", trace=True, peripheral="crc", structured=st, stop_after="SWE.1")
    edges = re.findall(r'^  (\w+) -> (\w+)(?: \[condition="([^"]+)"\])?$', dot, re.M)
    serve = {n: re.search(rf'^  {n}_serve \[.*?--model (\S+) --workspace', dot, re.M) for n in
             ("swe1_author", "swe1_author_more", "swe1_inspector", "swe1_inspector_more", "swe1_triage",
              "release_manager")}
    assert {n: m.group(1) for n, m in serve.items()} == {
        "swe1_author": ORN, "swe1_author_more": ORN, "swe1_inspector": QWEN, "swe1_inspector_more": QWEN,
        "swe1_triage": QWEN, "release_manager": QWEN}
    for n in serve:  # every way into a model node passes its serve node; a failed swap ends at the finalizer
        assert not [a for a, b, _c in edges if b == n and a != f"{n}_serve"], n
        assert (f"{n}_serve", n, "outcome=succeeded") in edges and (f"{n}_serve", "finalize", "") in edges
    assert ("start", "swe1_author_serve", "") in edges
    assert f"--model {ORN} --time-budget" in next(x for x in dot.splitlines() if x.startswith("  swe1_author ["))
    assert f"--model {QWEN} --time-budget" in next(x for x in dot.splitlines() if x.startswith("  swe1_inspector ["))
    monkeypatch.delenv("FORGE_LRTX_ROOT")
    with pytest.raises(ValueError, match="MODEL_SWAP_REQUIRES_LRTX_ROOT"):
        build("WO-X", layer="LL", trace=True, peripheral="crc", structured=st, stop_after="SWE.1")


def test_process_ownership_ignores_only_the_user_namespace_view_of_the_uid():
    rec = {"boot_id": "b", "start_ticks": "100", "netns": "net:[1]", "uid": 1000}
    assert stack._same_process({**rec, "uid": 0}, rec)  # the same process seen from inside the stack's user namespace
    assert not stack._same_process({**rec, "start_ticks": "101"}, rec)  # another process under a reused PID
    assert not stack._same_process({**rec, "netns": "net:[2]"}, rec)
    assert not stack._same_process(None, rec) and not stack._same_process(rec, {"uid": 1000})


def test_identity_accepts_the_reported_quantization_label_but_still_pins_the_digest(monkeypatch):
    prof = lp.load(PID)
    want = prof["models"]["allowed"][ORN]
    assert want["quantization"] == "Q8_0" and want["reported_quantization"] == "unknown"
    tags = {"models": [{"name": ORN, "digest": want["digest"], "details": {"quantization_level": "unknown"}}]}

    class R:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self.body).encode()
    monkeypatch.setattr(lp.urllib.request, "urlopen", lambda *a, **k: R(tags))
    assert lp.model_identity(prof, ORN, "http://o")["status"] == "MATCH"
    tags["models"][0]["digest"] = "0" * 64
    assert lp.model_identity(prof, ORN, "http://o")["status"] == "MISMATCH"
    tags["models"][0]["digest"] = prof["models"]["allowed"][QWEN]["digest"]
    tags["models"][0]["name"] = QWEN
    tags["models"][0]["details"]["quantization_level"] = "unknown"
    assert lp.model_identity(prof, QWEN, "http://o")["status"] == "MISMATCH"  # Qwen keeps its strict Q8_0 label


def test_selection_waits_for_the_recorded_model_server_and_refuses_if_it_never_answers(tmp_path, monkeypatch):
    """CAPA-081 (run -01): the work order started before llama-server was healthy."""
    import http.server
    import socket
    import threading

    prof = lp.load(PID)
    root = tmp_path / "lrtx"
    (root / "run").mkdir(parents=True)
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    (root / "run/services.json").write_text(json.dumps({"processes": {"llama_server": {
        "pid": 1, "health": f"http://127.0.0.1:{port}/health"}}}))
    env = {"FORGE_LRTX_ROOT": str(root)}
    issues = lp.served_model_issues(prof, env, wait_s=0.5)
    assert issues == [f"MODEL_SERVER_NOT_READY:http://127.0.0.1:{port}/health"]
    srv = http.server.HTTPServer(("127.0.0.1", port), type("H", (http.server.BaseHTTPRequestHandler,), {
        "do_GET": lambda self: (self.send_response(200), self.end_headers(), self.wfile.write(b"{}")),
        "log_message": lambda *a: None}))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert lp.served_model_issues(prof, env, wait_s=5) == []
    finally:
        srv.shutdown()
    assert lp.served_model_issues(prof, {}, wait_s=0) == []  # no stack record: nothing to check
