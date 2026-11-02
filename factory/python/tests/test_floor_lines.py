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
