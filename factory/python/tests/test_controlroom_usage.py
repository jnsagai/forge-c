"""CR-T028: usage merge (Fabro native + ACP proxy), not reported never counted as zero, cost only from a price."""
import json

from controlroom_fixtures import workspace
from forge_factory.controlroom.usage import cost, records, summary


def _ev(t, payload, attempt="WO-U-r1"):
    return {"type": t, "payload": payload, "attempt_id": attempt, "order_id": "WO-U", "ts_utc": "2026-10-19T10:00:00Z"}


def _ws(tmp_path):
    prof = {"default": "deepseek-flash", "provider": "deepseek", "nodes": [],
            "acp_authors": {"nodes": ["swe1_author"], "model": "gpt-6.1-sol", "provider": "openai-codex"},
            "acp_inspectors": {"nodes": ["swe1_inspector", "release_manager"], "model": "claude-opus-5-5",
                               "provider": "anthropic-claude"}}
    ws = workspace(tmp_path, "WO-U-r1", [], profile=prof)
    (ws / ".forge-run/acp").mkdir()
    (ws / ".forge-run/acp/swe1_inspector.proxy.jsonl").write_text(
        json.dumps({"event": "session"}) + "\n" +
        json.dumps({"event": "usage", "model": "claude-opus-5-5", "input": 10, "output": 90, "cache_read": 500}) + "\n")
    return ws


def test_native_and_acp_records_and_not_reported(tmp_path):
    ws = _ws(tmp_path)
    evs = [_ev("agent.usage_recorded", {"stage": "swe2_inspector", "model": "deepseek-v4-flash", "tokens_new": 1000,
                                        "cache_read": 50}),
           _ev("stage.completed", {"node": "swe1_author"}), _ev("stage.completed", {"node": "swe1_author"}),
           _ev("stage.completed", {"node": "swe1_inspector"}), _ev("stage.completed", {"node": "swe1_inspector"})]
    recs = records(ws, evs)
    by = {(r["node"], r["basis"]) for r in recs}
    assert ("swe2_inspector", "reported:fabro") in by and ("swe1_inspector", "reported:acp-proxy") in by
    assert sum(1 for r in recs if r["node"] == "swe1_author" and r["basis"] == "not_reported") == 2
    assert sum(1 for r in recs if r["node"] == "swe1_inspector" and r["basis"] == "not_reported") == 1
    s = summary(recs, ready_packages=0, prices={})
    assert s["tokens_new_reported"] == 1100 and s["stages"] == 5 and s["not_reported_share"] == 0.6
    assert s["tokens_per_ready_package"]["status"] == "NOT_MEASURED"
    codex = next(m for m in s["by_model"] if m["model"] == "gpt-6.1-sol")
    assert codex["tokens_new"] is None and codex["not_reported_stages"] == 2          # not zero
    assert codex["cost"]["reason"] == "subscription; no per-token price"
    ds = next(m for m in s["by_model"] if m["model"] == "deepseek-v4-flash")
    assert ds["cost"]["status"] == "NOT_MEASURED" and "price" in ds["cost"]["reason"]
    roles = {r["role"]: r for r in s["by_role"]}
    assert roles["author"]["complete"] is False and roles["inspector"]["reported_stages"] == 2


def test_cost_only_from_a_configured_price():
    prices = {"claude-opus-5-5": {"input_per_mtok": 5.0, "output_per_mtok": 25.0, "currency": "USD"}}
    assert cost("claude-opus-5-5", 1_000_000, 100_000, prices, acp=True) == {
        "status": "MEASURED", "value": 7.5, "currency": "USD", "source": "config price table"}
    assert cost("claude-opus-5-5", None, None, prices, acp=True)["status"] == "NOT_MEASURED"


def test_tokens_per_ready_package_when_ready_exists(tmp_path):
    recs = records(_ws(tmp_path), [_ev("agent.usage_recorded", {"stage": "swe2_author", "model": "m", "tokens_new": 900,
                                                                 "cache_read": 0})])
    assert summary(recs, ready_packages=3, prices={})["tokens_per_ready_package"] == {
        "status": "MEASURED", "value": 300.0, "complete": True}


def test_token_usage_tolerates_acp_stages(monkeypatch):
    from forge_factory.release import finalize as F

    class C:
        def usage(self, rid):
            return {"stages": [
                {"stage": {"id": "swe1_author"}, "model": None, "usage": {"tokens": {"input": 0, "output": 0}}},
                {"stage": {"id": "swe1_inspector"}, "model": {"model_id": "deepseek-v4-flash", "provider": "deepseek"},
                 "usage": {"tokens": {"input": 10, "output": 2}}, "state": "succeeded"}]}
    import forge_factory.fabro.client as FC

    monkeypatch.setattr(FC, "client_for_workspace", lambda ws, timeout=10: C())
    u = F.token_usage("RUN", ws=__import__("pathlib").Path("/x"))
    assert u["basis"] == "reported" and u["total_input"] == 10 and u["not_reported_stages"] == ["swe1_author"]
