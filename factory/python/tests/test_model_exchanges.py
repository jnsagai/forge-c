"""Per-node model exchange log (owner 2026-11-08): read-only export from the Fabro store and order workspaces."""
import json
import sqlite3
import stat

from forge_factory.lrtx import model_exchanges as M

RUN = "01M6V4HV3ZNPDZ1NJPPA11KQWW"
WO = "WO-F014-SWE1-GPIOL-20261107-L40F"


def _event(seq, name, node, stage, session, props, ts):
    return (RUN, seq, name, node, stage, session, json.dumps({"ts": ts, "event": name, "properties": props}))


def _fabro(tmp_path):
    db = tmp_path / "lrtx/fabro/storage/db/fabro.sqlite3"
    db.parent.mkdir(parents=True)
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE runs (id, title, workflow_name, status, created_at_ms, completed_at_ms, input_tokens, output_tokens, "
              "reasoning_tokens, cache_read_tokens)")
    c.execute("CREATE TABLE run_events (run_id, seq, event_name, node_id, stage_id, session_id, event_json)")
    c.execute("INSERT INTO runs VALUES (?, ?, 'wf', 'succeeded', 1, 2, 0, 0, 0, 0)", (RUN, WO + " GPIO driver"))
    s, st = "ses_1", "swe1_inspector@2"
    ctx = {"input_tokens": 9000, "breakdown": [{"category": "system_prompt", "tokens": 1000}, {"category": "mcp_tools", "tokens": 3000},
                                               {"category": "conversation", "tokens": 5000}]}
    rows = [
        _event(1, "stage.started", "swe1_inspector", st, None, {}, "2026-11-08T10:00:00Z"),
        _event(2, "agent.input", "swe1_inspector", st, s, {"event": {"UserInput": {"text": "Inspect the requirements. token=abcd1234secret"}}},
               "2026-11-08T10:00:00Z"),
        _event(3, "agent.tools.available", "swe1_inspector", st, None,
               {"tools": [{"name": "read_file", "description": "read"}, {"name": "cbmc_verify", "description": "never used"}]},
               "2026-11-08T10:00:00Z"),
        _event(4, "agent.llm.started", "swe1_inspector", st, s, {"event": {"LlmRequestStarted": {"requested_model": "ornith"}}},
               "2026-11-08T10:00:01Z"),
        _event(5, "agent.message", "swe1_inspector", st, s, {"event": {"AssistantMessage": {
            "text": "I will read the file.", "reasoning": "HIDDEN CHAIN OF THOUGHT", "usage": {"tokens": {"input": 9000, "output": 40, "reasoning": 30}},
            "context_window": ctx}}}, "2026-11-08T10:00:05Z"),
        _event(6, "agent.tool.started", "swe1_inspector", st, s, {"event": {"ToolCallStarted": {
            "tool_name": "read_file", "tool_call_id": "t1", "arguments": {"path": "a.md"}}}}, "2026-11-08T10:00:05Z"),
        _event(7, "agent.tool.completed", "swe1_inspector", st, s, {"event": {"ToolCallCompleted": {
            "tool_name": "read_file", "tool_call_id": "t1", "output": "x" * 4000, "is_error": False,
            "output_bytes_retained": 4000, "output_bytes_omitted": 0}}}, "2026-11-08T10:00:06Z"),
        _event(8, "agent.llm.started", "swe1_inspector", st, s, {"event": {}}, "2026-11-08T10:00:06Z"),
        _event(9, "agent.message", "swe1_inspector", st, s, {"event": {"AssistantMessage": {
            "text": "Done.", "usage": {"tokens": {"input": 1200, "output": 10}}, "context_window": {**ctx, "input_tokens": 10200}}}},
               "2026-11-08T10:00:10Z"),
        _event(10, "stage.completed", "swe1_inspector", st, None, {"status": "succeeded"}, "2026-11-08T10:00:11Z"),
        _event(11, "stage.completed", "swe1_gate", "swe1_gate@1", None, {"status": "succeeded"}, "2026-11-08T10:00:12Z"),
    ]
    c.executemany("INSERT INTO run_events VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    c.commit()
    c.close()
    ws = tmp_path / "lrtx/state/workorders" / WO / "workspace/.forge-run/lrtx/SWE.1"
    (ws / "packets").mkdir(parents=True)
    (ws / "development-execution.json").write_text(json.dumps({"calls": {"swe1-author:requirements:GPIO_AFRH_1": 2}}))
    (ws / "packets/requirements__GPIO_AFRH_1.json").write_text(json.dumps({
        "task": "requirements:GPIO_AFRH_1", "status": "VALID", "errors": [], "doc": {"requirements": [{"id": "R1"}]},
        "history": [{"usage": {"prompt_tokens": 12794, "completion_tokens": 29589, "prompt_tokens_details": {"cached_tokens": 241}},
                     "finish_reason": "stop", "errors": ["field not in index"], "wall_ms": 219000.0}],
        "attempts": [{"usage": {"prompt_tokens": 14442, "completion_tokens": 14110, "prompt_tokens_details": {"cached_tokens": 10746}},
                      "finish_reason": "stop", "errors": [], "wall_ms": 103000.0,
                      "accounting": {"complete_serialized_request": {"serialized_bytes": 52633, "sha256": "ab" * 32}}}]}))
    return db


def test_export_groups_every_ai_node_per_run_and_visit(tmp_path):
    db = _fabro(tmp_path)
    out = tmp_path / "out"
    r = M.export(db, out)
    assert r["runs_exported"] == 1 and r["nodes"] == 2  # the agent inspector and the structured author; the gate made no model call
    assert stat.S_IMODE(out.stat().st_mode) == 0o700
    rdir = next((out / "runs").iterdir())
    calls = [json.loads(x) for x in (rdir / "swe1_inspector/visit-2.jsonl").read_text().splitlines()]
    visit, turns = calls[0], [x for x in calls if x["kind"] == "call"]
    assert visit["visit"] == 2 and visit["stats"]["turns"] == 2
    assert turns[0]["prompt_tokens"] == 9000 and turns[1]["prompt_tokens"] == 10200 and turns[1]["usage"]["input"] == 1200
    assert visit["stats"]["cache_reused_tokens"] == 19200 - 10200 and turns[0]["tool_calls"][0]["output"] == "x" * 4000
    text = (rdir / "swe1_inspector/visit-2.jsonl").read_text() + (rdir / "swe1_inspector/visit-2.md").read_text()
    assert "HIDDEN CHAIN OF THOUGHT" not in text and "abcd1234secret" not in text  # FR-025 and secret redaction
    report = (out / "by-node/swe1_inspector.md").read_text()
    assert "cbmc_verify" in report and "Fixed part of every prompt" in report and "Prompt cache" in report
    author = (out / "by-node/swe1-author.md").read_text()
    assert "(structured)" in author and "retries of the same task" in author and "hidden reasoning" in author
    t = (rdir / "swe1-author/visit-1.md").read_text()
    assert "requirements:GPIO_AFRH_1" in t and "field not in index" in t and '"R1"' in t and "not recorded" in t
    index = (out / "index.md").read_text()
    assert index.index("swe1_inspector") > index.index("swe1-author")  # sorted by prompt tokens (27,236 > 19,200)
    assert "swe1_gate" not in index and (out / "nodes.csv").read_text().startswith("node,kind,")


def test_incremental_skips_finished_runs_and_never_writes_the_store(tmp_path):
    db = _fabro(tmp_path)
    before = db.read_bytes()
    out = tmp_path / "out"
    assert M.export(db, out, incremental=True)["runs_exported"] == 1
    # the newest run of an order is re-read every time (its structured nodes and captures keep growing) ...
    assert M.export(db, out, incremental=True)["runs_exported"] == 1
    c = sqlite3.connect(db)  # ... an older finished run of the same order is skipped once exported
    c.execute("INSERT INTO runs VALUES ('01NEWERRUN0000000000000000', ?, 'wf', 'running', 5, NULL, 0, 0, 0, 0)", (WO + " retry",))
    c.commit()
    c.close()
    before = db.read_bytes()
    # the old finished run is skipped; the order's structured records move to its newest run and are counted once
    assert M.export(db, out, incremental=True)["runs_exported"] == 1
    rows = {r.split(",")[0]: r.split(",") for r in (out / "nodes.csv").read_text().splitlines()[1:]}
    assert rows["swe1-author"][2] == "1" and rows["swe1_inspector"][2] == "1"  # visits
    assert M.export(db, out, wo="SPIL")["runs_selected"] == 0
    assert db.read_bytes() == before


def test_structured_capture_is_off_by_default_and_complete_when_switched_on(tmp_path, monkeypatch):
    """Owner 2026-11-08 "capture the structured node prompts too": full request + reply, behind the owner's switch."""
    from forge_factory.lrtx import structured as S

    state, ws = tmp_path / "state", tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": WO}))
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    monkeypatch.chdir(ws)
    p = {"phase": "SWE.1", "task": "requirements:GPIO_AFRH_1", "role": "swe1-author", "input_hash": "h"}
    body = {"model": "ornith", "messages": [{"role": "system", "content": "Write requirements. api_key=SECRETVALUE99"},
                                            {"role": "user", "content": "RM0486 excerpt"}],
            "max_tokens": 4096, "forge_execution": {"job_id": "j", "nonce": "NONCE-MUST-NOT-LEAK", "request_id": "r", "role": "x"}}
    result = {"usage": {"prompt_tokens": 100, "completion_tokens": 50}, "finish_reason": "stop", "wall_ms": 12.0, "errors": []}
    S._capture(p, body, result, '{"requirements": []}')
    assert not (state / "model-exchanges/structured").exists()  # no switch file: nothing written
    (state / "model-exchanges").mkdir(parents=True)
    (state / "model-exchanges/capture.json").write_text(json.dumps({"structured": True}))
    S._capture(p, body, result, '{"requirements": []}')
    files = list((state / "model-exchanges/structured" / WO / "SWE.1").glob("*.json"))
    assert len(files) == 1 and stat.S_IMODE(files[0].stat().st_mode) == 0o600
    rec = json.loads(files[0].read_text())
    assert rec["request"]["messages"][1]["content"] == "RM0486 excerpt" and rec["reply"]["text"] == '{"requirements": []}'
    assert "NONCE-MUST-NOT-LEAK" not in files[0].read_text() and "SECRETVALUE99" not in files[0].read_text()
    monkeypatch.setattr(S, "RECOVERY_WORKSPACE", None)  # a broken environment never fails the call
    S._capture(p, body, result, "x")

    # the exporter attaches the captured call to its task, once per order (newest run)
    db = _fabro(tmp_path)
    capdir = tmp_path / "lrtx/state/model-exchanges/structured" / WO / "SWE.1"
    capdir.mkdir(parents=True)
    (capdir / files[0].name).write_text(files[0].read_text())
    out = tmp_path / "out"
    M.export(db, out)
    t = next((out / "runs").iterdir()) / "swe1-author/visit-1.md"
    text = t.read_text()
    assert "1 calls captured" in text and "RM0486 excerpt" in text and "### Captured call" in text
