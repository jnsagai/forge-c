"""Autonomous line M1 (owner 2026-11-03): the floor's supervisor station - read-only and model-free, from the Line
Conductor's issues feed forge-c/supervisor-issues/1; a missing, stale or malformed feed never hides the floor, the
line=local passthrough carries it, the payload has no reasoning/prompt/completion or free agent text, no new POST route."""
# ruff: noqa: F811 - the shared `line` fixture is imported from test_line_conductor_m1
from __future__ import annotations

import ast
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from forge_factory.afo import line_conductor as LC
from forge_factory.lrtx import floor_api as F
from forge_factory.lrtx import progress_api as P
from test_line_conductor_m1 import IWDG, PROSE, T0, _iso, _serve, by_wo, conductor, line  # noqa: F401 - shared fixture

pytestmark = pytest.mark.skipif(not LC.SCHEMA_PATH.is_file(), reason="supervisor-issues contract not in this checkout")

# --------------------------------------------------------------------------------------- the floor station
def test_the_floor_survives_a_missing_stale_or_malformed_feed(line, monkeypatch):
    assert F.supervisor_station()["reason"] == "NO_SUPERVISOR_ON_THIS_LINE"
    feed_file = line["tmp"] / "feed/issues.json"
    monkeypatch.setenv("FORGE_FLOOR_SUPERVISOR_FEED", str(feed_file))
    assert F.supervisor_station() == {"available": False, "reason": "FEED_MISSING"}
    feed_file.parent.mkdir()
    feed_file.write_text("{not json")
    assert F.supervisor_station()["reason"] == "FEED_MALFORMED"
    good = conductor(line).cycle()
    feed_file.write_text(json.dumps({**good, "issues": [{**good["issues"][0], "summary": "<script>x</script>!"}]}))
    assert F.supervisor_station()["reason"] == "FEED_MALFORMED"  # schema-invalid is not shown
    feed_file.write_text(json.dumps({**good, "generated_at": "2026-01-01T00:00:00Z"}))
    st = F.supervisor_station()
    assert st["available"] is False and st["reason"] == "FEED_STALE" and "issues" not in st
    for body in ("{not json", json.dumps({**good, "generated_at": "2026-01-01T00:00:00Z"})):
        feed_file.write_text(body)
        fl = F.floor()
        assert fl["supervisor"]["available"] is False and "halls" in fl and fl["orders"]
    feed_file.write_text(json.dumps(good))
    shutil.copy(LC.journal_path(), feed_file.with_name("issues.jsonl"))
    st = F.supervisor_station()
    assert st["available"] is True and len(st["issues"]) == len(good["issues"]) and st["log"]
    assert set(st["log"][0]) == {"at", "event", "issue_id", "status", "class", "error_code", "wo", "phase"}


def test_the_line_local_passthrough_carries_the_supervisor(line, monkeypatch):
    conductor(line).cycle()
    monkeypatch.setenv("FORGE_FLOOR_SUPERVISOR_FEED", str(LC.feed_path()))
    up, up_port = _serve(P.Handler)  # the Omniverse2 floor
    monkeypatch.setenv("FORGE_FLOOR_LINES", json.dumps([{"id": "local", "label": "Local", "url": f"http://127.0.0.1:{up_port}"},
                                                        {"id": "cloud", "label": "Cloud"}]))
    me, me_port = _serve(P.Handler)  # the loop10 two-line floor
    try:
        get = lambda p: json.loads(urllib.request.urlopen(f"http://127.0.0.1:{me_port}{p}", timeout=20).read())  # noqa: E731
        local = get("/floor.json?line=local")["supervisor"]
        assert local["available"] is True and any(i["wo"] == IWDG.format(n=6, l=22) for i in local["issues"])
        assert get("/supervisor.json?line=local")["issues"] == local["issues"]
        assert get("/supervisor.json")["available"] is True
    finally:
        up.shutdown()
        me.shutdown()


def test_the_cloud_line_has_no_supervisor(line, monkeypatch):
    monkeypatch.delenv("FORGE_FLOOR_SUPERVISOR_FEED", raising=False)
    assert F.floor()["supervisor"] == {"available": False, "reason": "NO_SUPERVISOR_ON_THIS_LINE"}
    page = Path(P.FLOOR_PAGE).read_text()
    assert "NO_SUPERVISOR_ON_THIS_LINE" in page and "No supervisor on this line." in page


FORBIDDEN_KEYS = {"reasoning", "reasoning_content", "thinking", "prompt", "prompts", "completion", "completions", "messages",
                  "content", "response", "raw", "chain_of_thought", "detail", "excerpt", "redacted_summary"}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def test_no_reasoning_prompt_completion_or_free_agent_text(line, monkeypatch):
    ws = line["state"] / "workorders" / IWDG.format(n=6, l=22) / "workspace"
    with (ws / ".forge-run/gates/gate-log.jsonl").open("a") as f:  # an agent-reported (non-deterministic) prose issue
        f.write(json.dumps({"phase": "SWE.6", "step": "author", "result": "REJECTED", "issues": [PROSE],
                            "ts": _iso(T0 + 4300)}) + "\n")
    feed = conductor(line).cycle()
    monkeypatch.setenv("FORGE_FLOOR_SUPERVISOR_FEED", str(LC.feed_path()))
    station = F.supervisor_station()
    for payload in (feed, station, F.floor()["supervisor"]):
        text = json.dumps(payload)
        assert "MARKER-PROSE" not in text and "flaky" not in text
        assert not FORBIDDEN_KEYS & set(_keys(payload))
    for i in feed["issues"]:  # every summary is a fixed template over codes
        assert i["summary"].split(" ", 1)[0] in ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6", "-", "002", "AFO")


def test_no_new_post_route_in_progress_api(line):
    tree = ast.parse(Path(P.__file__).read_text())
    handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Handler")
    assert {f.name for f in handler.body if isinstance(f, ast.FunctionDef) and f.name.startswith("do_")} == {"do_GET", "do_POST"}
    post = next(f for f in handler.body if isinstance(f, ast.FunctionDef) and f.name == "do_POST")
    routes = {c.value for c in ast.walk(post) if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value[:1] == "/" and len(c.value) > 1}
    assert routes == {"/claude-mode", "/inspector-mode"}
    srv, port = _serve(P.Handler)
    try:
        for path in ("/supervisor.json", "/supervisor/ack", "/floor.json"):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json"})
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req, timeout=10)
            assert e.value.code == 404
    finally:
        srv.shutdown()


def test_the_page_ports_the_mockup_read_only():
    page = Path(P.FLOOR_PAGE).read_text()
    for s in ('id="sup-bot"', "m-patrol", "m-diagnose", "m-repair", "m-owner", "t-glass", "t-wrench", "t-flag",
              "prefers-reduced-motion", "function supMode", "supLane", "Supervisor log",
              "supervisor ack"):
        assert s in page, s
    assert "data-answer" not in page and "mode-pick" not in page  # no decision buttons (decision 10)
    assert page.count('method: "POST"') == 1  # only the existing cloud-mode control posts
