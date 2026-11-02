"""Owner 2026-11-02 ("why not in the very same port?"): one floor page for two production lines - a line with a url is
another floor server (passed through read-only), a line without one is this process's own state; unset = unchanged."""
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from forge_factory.lrtx import progress_api as P


class Upstream(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        data = json.dumps({"halls": [], "orders": [{"wo": "WO-REMOTE"}], "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_a):
        pass


def _serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def test_two_lines_on_one_page(tmp_path, monkeypatch):
    up, up_url = _serve(Upstream)
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("FORGE_FLOOR_LINES", json.dumps([
        {"id": "local", "label": "Local", "sub": "Ornith/Qwen", "url": up_url},
        {"id": "cloud", "label": "Cloud", "sub": "Claude/gpt-6.1-sol"}]))
    me, me_url = _serve(P.Handler)
    try:
        assert _get(me_url + "/lines.json")["lines"] == [{"id": "local", "label": "Local", "sub": "Ornith/Qwen"},
                                                          {"id": "cloud", "label": "Cloud", "sub": "Claude/gpt-6.1-sol"}]
        remote = _get(me_url + "/floor.json?line=local&order=WO-X")
        assert remote["orders"] == [{"wo": "WO-REMOTE"}] and remote["path"] == "/floor.json?order=WO-X"
        own = _get(me_url + "/floor.json?line=cloud")
        assert "halls" in own and own.get("orders") is not None
        try:
            urllib.request.urlopen(me_url + "/floor.json?line=nope", timeout=10)
            raise AssertionError("unknown line served")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        up.shutdown()
        me.shutdown()


def test_without_lines_the_floor_is_unchanged(monkeypatch):
    monkeypatch.delenv("FORGE_FLOOR_LINES", raising=False)
    assert P.floor_lines() == []


def test_the_cloud_line_shows_an_api_station_instead_of_the_gpu(tmp_path, monkeypatch):
    import time as _t

    from forge_factory.lrtx import floor_api as F

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    now = _t.time()
    day = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(now - 60))
    old = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(now - 2 * 86400))
    (tmp_path / "cloud-bridge").mkdir()
    rows = [{"ts": day, "model": "claude-opus-5-5", "backend": "anthropic", "ok": True,
             "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cache_read_tokens": 100, "cost_usd": 0.008}},
            {"ts": day, "model": "gpt-6.1-sol", "backend": "openai", "ok": True,
             "usage": {"prompt_tokens": 500, "completion_tokens": 80, "reasoning_tokens": 40}},
            {"ts": day, "model": "gpt-6.1-sol", "backend": "openai", "ok": False, "usage": None},
            {"ts": old, "model": "claude-opus-5-5", "backend": "anthropic", "ok": True, "usage": {"cost_usd": 9.0}}]
    (tmp_path / "cloud-bridge/calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    st = F.station(now)
    assert st["kind"] == "cloud_api" and st["cost_today_usd"] == 0.01
    claude, gpt = st["models"]
    assert claude["model"] == "claude-opus-5-5" and claude["priced"] and claude["today"]["calls"] == 1
    assert claude["today"]["cached"] == 100 and claude["hour"]["prompt"] == 1000 and claude["last_s"] < 120
    assert gpt["priced"] is False and gpt["today"]["calls"] == 2 and gpt["today"]["failed"] == 1 and gpt["today"]["reasoning"] == 40
    (tmp_path / "cloud-bridge/calls.jsonl").unlink()
    assert F.station(now).get("kind") != "cloud_api"  # no meter: the GPU station as before


def test_a_display_rate_prices_an_unpriced_model_and_is_labelled(tmp_path, monkeypatch):
    import time as _t

    from forge_factory.lrtx import floor_api as F

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("FORGE_FLOOR_API_PRICES", json.dumps({"gpt-6.1-sol": {"input": 2, "cached": 0.1, "output": 10,
                                                                              "source": "public pricing pages"}}))
    (tmp_path / "cloud-bridge").mkdir()
    ts = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
    (tmp_path / "cloud-bridge/calls.jsonl").write_text(json.dumps({"ts": ts, "model": "gpt-6.1-sol", "backend": "openai", "ok": True,
        "usage": {"prompt_tokens": 1_000_000, "cached_prompt_tokens": 500_000, "completion_tokens": 100_000}}) + "\n")
    m = F.station(_t.time())["models"][0]
    assert m["priced"] and m["price_source"] == "public pricing pages" and m["today"]["cost_usd"] == 2.05
