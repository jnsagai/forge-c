"""Owner 2026-11-01 ("yes, proceed with answer tokens only"): the gateway relays answer tokens to a display-only socket.
Reasoning never reaches it, nothing is written to disk, no viewer / a slow viewer never affects the call, and it is off
unless the profile opts in."""
from __future__ import annotations

import asyncio
import json
import socket
import time

import httpx
from fastapi.testclient import TestClient
from forge_factory import live_tap as LT
from forge_factory import llm_gateway as gw


def upstream(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if body.get("stream"):
        lines = [
            {"choices": [{"delta": {"reasoning_content": "SECRET-THOUGHT", "content": "{\"requirements\""}}]},
            {"choices": [{"delta": {"reasoning": "MORE-SECRET", "content": ": []}"}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 5, "completion_tokens": 7}},
        ]
        text = "".join("data: " + json.dumps(x) + "\n\n" for x in lines) + "data: [DONE]\n\n"
        return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})
    return httpx.Response(200, json={"choices": [{"message": {"content": "OK", "reasoning": "SECRET-THOUGHT"},
                                                  "finish_reason": "stop"}],
                                     "usage": {"prompt_tokens": 7, "completion_tokens": 1}})


def _read(sock: socket.socket, until: str, timeout: float = 5.0) -> str:
    sock.settimeout(0.2)
    buf, end = b"", time.time() + timeout
    while time.time() < end and until.encode() not in buf:
        try:
            chunk = sock.recv(65536)
        except TimeoutError:
            continue
        if not chunk:
            break
        buf += chunk
    return buf.decode()


def test_a_viewer_sees_the_answer_tokens_and_never_the_reasoning(tmp_path, monkeypatch):
    path = tmp_path / "run/gateway-live.sock"
    monkeypatch.setenv("FORGE_GATEWAY_LIVE_TAP", str(path))
    with TestClient(gw.create_app("http://up", tmp_path / "usage.jsonl",
                                  transport=httpx.MockTransport(upstream))) as c:  # one event loop, as under uvicorn
        _viewer_sees_answers(c, tmp_path, path)


def _viewer_sees_answers(c, tmp_path, path):
    req = {"model": "m", "stream": True, "messages": []}
    assert c.post("/v1/chat/completions", json=req).status_code == 200  # first call starts listening
    assert path.is_socket() and oct(path.stat().st_mode & 0o777) == "0o600"
    v = socket.socket(socket.AF_UNIX)
    v.connect(str(path))
    time.sleep(0.2)
    r = c.post("/v1/chat/completions", json=req)
    assert "SECRET" not in r.text  # the response itself is unchanged by the tap
    seen = _read(v, '"t":"end"')
    events = [json.loads(x) for x in seen.splitlines()]
    assert [e["t"] for e in events] == ["start", "d", "d", "end"]
    assert "".join(e["c"] for e in events if e["t"] == "d") == '{"requirements": []}'
    assert events[-1]["finish"] == "stop" and events[-1]["out"] == 7
    assert "SECRET" not in seen and "THOUGHT" not in seen
    c.post("/v1/chat/completions", json={"model": "m", "messages": []})  # non-streaming: the whole answer at once
    seen = _read(v, '"t":"end"')
    assert '"c":"OK"' in seen and "SECRET" not in seen
    v.close()
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["usage.jsonl"]  # nothing else on disk


def test_without_the_variable_there_is_no_socket_and_the_gateway_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_GATEWAY_LIVE_TAP", raising=False)
    c = TestClient(gw.create_app("http://up", tmp_path / "usage.jsonl", transport=httpx.MockTransport(upstream)))
    r = c.post("/v1/chat/completions", json={"model": "m", "stream": True, "messages": []})
    assert r.status_code == 200 and '{\\"requirements\\"' in r.text
    assert not list(tmp_path.rglob("*.sock"))


def test_a_full_viewer_buffer_drops_pieces_instead_of_waiting():
    class Transport:
        def get_write_buffer_size(self):
            return LT.MAX_BUFFER + 1

    class Writer:
        transport = Transport()
        written = 0

        def is_closing(self):
            return False

        def write(self, _b):
            Writer.written += 1

    tap = LT.LiveTap(None)
    tap.viewers.append(Writer())
    n = asyncio.run(tap.begin("m", None))
    tap.piece(n, "abc")
    assert Writer.written == 0 and tap.dropped == 2


def test_only_a_profile_that_opts_in_gets_the_tap(monkeypatch, tmp_path):
    from forge_factory.lrtx import profile, stack

    assert stack.live_tap_path(tmp_path) == tmp_path / "run/gateway-live.sock"
    assert profile.load("local-rtx-v2-omniverse2-ornith-think-author-q38-inspector")["gateway"]["live_tap"] is True
    assert "live_tap" not in profile.load("local-rtx-v2-omniverse2-ornith-author-q38-inspector").get("gateway", {})


def test_the_admitted_local_path_feeds_the_viewer_too(tmp_path, monkeypatch):
    """Local stacks run the gateway with admission (FORGE_GATEWAY_MAX_INFLIGHT): the _timed stream path."""
    from forge_factory.lrtx import admission as la

    monkeypatch.setattr(la, "loaded", lambda url, m: True)
    monkeypatch.setattr(la, "resources", lambda url=None: {"gpu": {"status": "UNKNOWN"}})
    path = tmp_path / "gateway-live.sock"
    monkeypatch.setenv("FORGE_GATEWAY_LIVE_TAP", str(path))
    with TestClient(gw.create_app("http://up", tmp_path / "u.jsonl", transport=httpx.MockTransport(upstream),
                                  admission=la.Admission(1, 2, 10))) as c:
        req = {"model": "m", "stream": True, "messages": []}
        c.post("/v1/chat/completions", json=req)
        v = socket.socket(socket.AF_UNIX)
        v.connect(str(path))
        time.sleep(0.2)
        assert c.post("/v1/chat/completions", json=req).status_code == 200
        seen = _read(v, '"t":"end"')
        v.close()
    assert '{\\"requirements\\"' in seen and "SECRET" not in seen and '"out":7' in seen
