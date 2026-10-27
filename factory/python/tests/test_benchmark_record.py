"""Feature 015 (FR-006, F015-T070): the benchmark record is built from recorded evidence only (AFO database read-only,
work-order manifests, gate logs, packages, ACP proxy usage) and keeps BLOCKED outcomes as recorded."""
import json
import sqlite3

import pytest
from forge_factory.benchmark import record as R


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path / "state"


def _ws(state, wo, rows, pkg=None):
    fr = state / "workorders" / wo / "workspace/.forge-run"
    (fr / "gates").mkdir(parents=True)
    (fr / "acp").mkdir()
    (fr / "manifest.json").write_text(json.dumps({
        "peripheral": "spi", "code_mode": "FROZEN", "created_at": "2026-10-25T10:00:00Z",
        "factory_revision": {"commit": "abc1234def", "dirty": False},
        "inputs": [{"path": "inputs/rm.md", "sha256": "11"}],
        "delivered": [{"path": "software/ll/x.h", "sha256": "22", "role": "delivered_code"},
                      {"path": "inputs/vendor/include/y.h", "sha256": "33", "role": "dependency"}]}))
    (fr / "gates/gate-log.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (fr / "fabro_run_id").write_text("01RUN\n")
    (fr / "acp/swe1_author.proxy.jsonl").write_text(
        json.dumps({"event": "usage", "model": "gpt-6.1-sol", "input": 10, "output": 5, "cache_read": 100}) + "\n")
    (fr / "acp/swe1_inspector.proxy.jsonl").write_text(
        json.dumps({"event": "usage", "model": "claude-opus-5-5", "input": 7, "output": 3}) + "\n" + "not json\n")
    if pkg:
        (fr / "package.json").write_text(json.dumps(pkg))


def _db(state, request_id="BENCH-SPI-ST-R2", oid="afo-0756", state_="BLOCKED"):
    db = state / "conductor/conductor.sqlite3"
    db.parent.mkdir(parents=True)
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE afo_work_orders (order_id TEXT, state TEXT, envelope TEXT, created_epoch REAL)")
    c.execute("CREATE TABLE afo_attempts (attempt_id TEXT, order_id TEXT, state TEXT, seq INTEGER, record TEXT)")
    c.execute("INSERT INTO afo_work_orders VALUES (?,?,?,1)", (oid, state_, json.dumps(
        {"request_id": request_id, "model_profile": "codex-claude", "git_revision": "abc1234def"})))
    c.execute("INSERT INTO afo_work_orders VALUES ('afo-other','DONE',?,2)", (json.dumps({"request_id": "X-1"}),))
    c.execute("INSERT INTO afo_attempts VALUES (?,?,?,1,'{}')", (oid + "-a1", oid, "FAILED"))
    c.commit()
    c.close()


def test_a_blocked_afo_attempt_is_recorded_with_phases_package_usage_and_hashes(env):
    rows = [{"phase": "SWE.1", "step": "route", "gate": {"decision": "REWORK"}},
            {"phase": "SWE.1", "step": "inspect", "gate": {"decision": "PASS"}},
            {"phase": "SWE.4", "step": "author", "issues": ["x"]},
            {"phase": "SWE.4", "step": "route", "gate": {"decision": "BLOCKED", "reason": "STUCK: twice"}},
            {"phase": "SWE.5", "step": "author"}]
    _ws(env, "WO-AFO-0756-a1", rows, {"package_status": "BLOCKED", "gap_count": 2, "gaps": ["a", "b"],
                                      "finalized_at": "2026-10-25T10:30:00Z"})
    _db(env)
    rec = R.collect()
    (e,) = rec["entries"]
    assert (e["route"], e["request_id"], e["work_order"], e["fabro_run_id"]) == (
        "AFO", "BENCH-SPI-ST-R2", "WO-AFO-0756-a1", "01RUN")
    assert e["phases"]["SWE.1"]["final"] == "PASS" and e["phases"]["SWE.1"]["reworks"] == 1
    assert e["phases"]["SWE.4"]["final"] == "BLOCKED" and e["phases"]["SWE.5"]["final"] == "INCOMPLETE"
    assert e["package"]["status"] == "BLOCKED" and e["package"]["gaps"] == ["a", "b"] and e["duration_s"] == 1800
    assert e["delivered_code"] == [{"path": "software/ll/x.h", "sha256": "22"}] and e["inputs"][0]["sha256"] == "11"
    assert e["usage"]["per_role"]["author"] == {"calls": 1, "input": 10, "output": 5, "cache_read": 100,
                                                "cache_write": 0}
    assert e["usage"]["per_model"]["claude-opus-5-5"]["input"] == 7
    assert "| WO-AFO-0756-a1 | AFO | spi | abc1234 |" in R.markdown(rec)


def test_a_running_attempt_has_no_package_and_the_database_is_only_read(env):
    _ws(env, "WO-AFO-0756-a1", [{"phase": "SWE.1", "step": "author"}])
    _db(env, state_="RUNNING")
    db = env / "conductor/conductor.sqlite3"
    before = db.read_bytes()
    (e,) = R.collect()["entries"]
    assert e["package"] is None and e["duration_s"] is None and e["phases"]["SWE.1"]["final"] == "INCOMPLETE"
    assert db.read_bytes() == before and "NO_PACKAGE" in R.markdown(R.collect())
