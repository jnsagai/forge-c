"""Owner 2026-11-02 ("Claude API/Account mode"): the floor's only control switches the cloud line's Claude calls between
the Anthropic API and the owner's Claude account. Two values only, a control header (a cross-site page would need a CORS
preflight, never granted), every switch and every refusal logged; account calls are shown without an API charge."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from forge_factory.lrtx import floor_api as F
from forge_factory.lrtx import progress_api as P


def _serve():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), P.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _post(url, body, headers=None):
    h = {"Content-Type": "application/json", "X-Forge-Control": "claude-mode", **(headers or {})}
    req = urllib.request.Request(url + "/claude-mode", data=json.dumps(body).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, None


def test_the_floor_switches_the_claude_mode_and_logs_it(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    srv, url = _serve()
    try:
        assert _post(url, {"mode": "account"})[0] == 409  # no cloud line on this floor
        (tmp_path / "cloud-bridge").mkdir()
        assert F.claude_mode()["mode"] == "account"  # owner 2026-11-02: account is the default
        assert _post(url, {"mode": "api"})[0] == 200
        code, body = _post(url, {"mode": "account"}, {"Origin": url})
        assert code == 200 and body["mode"] == "account" and body["since"]
        assert json.loads((tmp_path / "cloud-bridge/claude-mode.json").read_text())["mode"] == "account"
        assert _post(url, {"mode": "free"})[0] == 400
        assert _post(url, {"mode": "api"}, {"X-Forge-Control": "x"})[0] == 403
        pre = urllib.request.Request(url + "/claude-mode", method="OPTIONS", headers={
            "Origin": "http://evil.example", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-forge-control, content-type"})
        try:
            with urllib.request.urlopen(pre, timeout=10) as r:
                assert "Access-Control-Allow-Origin" not in r.headers
        except urllib.error.HTTPError as exc:
            assert "Access-Control-Allow-Origin" not in exc.headers  # no preflight is granted
        assert _post(url, {"mode": "api"}, {"Origin": "http://100.87.10.79:8788", "Host": "127.0.0.1:1"})[0] == 200
        log = [json.loads(x) for x in (tmp_path / "cloud-bridge/claude-mode-changes.jsonl").read_text().splitlines()]
        assert [(r["from"], r["to"]) for r in log if "to" in r] == [("account", "api"), ("api", "account"), ("account", "api")]
        assert [(r["refused"], r["why"]) for r in log if "refused" in r] == [
            (400, "mode must be api or account"), (403, "control header missing")]  # no cloud line: nothing to log into
        assert all(r["client"] == "127.0.0.1" for r in log)
    finally:
        srv.shutdown()


def test_the_cloud_station_shows_the_mode_and_account_calls_without_api_cost(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    import time
    now = time.time()
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 60))
    (tmp_path / "cloud-bridge").mkdir()
    rows = [{"ts": ts, "model": "claude-opus-5-5", "backend": "anthropic", "ok": True,
             "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost_usd": 0.5}},
            {"ts": ts, "model": "claude-opus-5-5", "backend": "claude-cli", "ok": True, "claude_mode": "account",
             "usage": {"prompt_tokens": 100, "completion_tokens": 10, "billing": "account", "list_cost_usd": 0.25}}]
    (tmp_path / "cloud-bridge/calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    F.set_claude_mode("account", "test")
    st = F.cloud_station(now)
    m = st["models"][0]
    assert st["claude_mode"]["mode"] == "account" and st["cost_today_usd"] == 0.5
    assert m["today"]["calls"] == 2 and m["today"]["account_calls"] == 1 and m["today"]["list_cost_usd"] == 0.25


def test_the_inspector_has_its_own_mode_switch_and_account_calls_are_not_priced(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("FORGE_FLOOR_API_PRICES", json.dumps({"gpt-6.1-sol": {"input": 2.0, "cached": 0.1, "output": 10.0}}))
    (tmp_path / "cloud-bridge").mkdir()
    srv, url = _serve()
    try:
        req = urllib.request.Request(url + "/inspector-mode", data=b'{"mode": "account"}', method="POST", headers={
            "Content-Type": "application/json", "X-Forge-Control": "inspector-mode"})
        with urllib.request.urlopen(req, timeout=10) as r:
            assert json.loads(r.read())["mode"] == "account"
        assert _post(url, {"mode": "account"}, {"X-Forge-Control": "inspector-mode"})[0] == 403  # header names its target
    finally:
        srv.shutdown()
    assert F.claude_mode("inspector")["mode"] == "account" and F.claude_mode()["mode"] == "account"  # default
    import time
    now = time.time()
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 60))
    rows = [{"ts": ts, "model": "gpt-6.1-sol", "backend": "openai", "ok": True, "usage": {"prompt_tokens": 1000000, "completion_tokens": 0}},
            {"ts": ts, "model": "gpt-6.1-sol", "backend": "codex", "ok": True,
             "usage": {"prompt_tokens": 1000000, "completion_tokens": 0, "billing": "account"}}]
    (tmp_path / "cloud-bridge/calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    st = F.cloud_station(now)
    assert st["inspector_mode"]["mode"] == "account" and st["models"][0]["today"]["account_calls"] == 1
    assert st["cost_today_usd"] == 2.0  # only the API call is priced at the display rate


def test_cell_labels_follow_the_line_and_default_to_the_local_models(monkeypatch):
    monkeypatch.delenv("FORGE_FLOOR_CELL_TAGS", raising=False)
    assert F.cell_tags()["inspector"] == "Qwen3.8 27B" and F.cell_tags()["author"] == "Ornith 35B, thinking on"
    monkeypatch.setenv("FORGE_FLOOR_CELL_TAGS", json.dumps({"author": "Claude Opus 5.5", "inspector": "gpt-6.1-sol",
                                                            "tool": "no model swap (cloud APIs)", "tool_what": ""}))
    t = F.cell_tags()
    assert t["author"] == "Claude Opus 5.5" and t["inspector"] == "gpt-6.1-sol" and t["tool"] == "no model swap (cloud APIs)"
    assert t["tool_what"].startswith("Loads")  # an empty override keeps the default
