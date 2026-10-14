"""M4 (T025–T029): isolated autonomous repair with deterministic promotion/rollback (scripted model)."""
import json
import os
import subprocess

import pytest
from forge_factory.repair import infra as I
from forge_factory.repair import promotion as PR
from forge_factory.repair import worker as W
from forge_factory.supervisor.store import IncidentStore


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_INFRA_REPO", str(tmp_path / "infra"))
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path))
    infra = I.ensure_infra()
    # induced, reversible service fault on the live infra main branch
    cfg = infra / "runtime/llm-gateway.json"
    cfg.write_text(json.dumps({"bind": "127.0.0.1", "port": 9999, "upstream": "http://127.0.0.1:11435"}))
    I.git(infra, "commit", "-qam", "induced fault: wrong gateway port")
    store = IncidentStore()
    inc, _ = store.open_or_dedup("llm-gateway:CONFIG_INVALID:-:0.4", "llm-gateway", "CONFIG_INVALID",
                                 last_error="UNEXPECTED_PORT:runtime/llm-gateway.json:9999")
    store.transition(inc["incident_id"], "TRIAGED")
    store.transition(inc["incident_id"], "REPAIRING", attempts=1)
    product = tmp_path / "state/workorders/WO-X/workspace"
    (product / "software/src").mkdir(parents=True)
    (product / "software/src/rcc.c").write_text("int x;\n")
    (product / "evidence").mkdir()
    (product / "evidence/e.json").write_text("{}")
    return {"infra": infra, "store": store, "inc": inc["incident_id"], "product": product, "tmp": tmp_path}


def scripted(*turns):
    """Fake model: returns the given assistant turns in order, with reported usage."""
    it = iter(turns)

    def chat_fn(messages, tools, max_tokens=700):
        assert {t["function"]["name"] for t in tools} == {"read_file", "write_file", "validate_runtime_config"}
        assert all("shell" not in json.dumps(t) for t in tools)
        msg = next(it)
        return {"choices": [{"message": {"role": "assistant", **msg}}], "usage": {"prompt_tokens": 300,
                                                                                    "completion_tokens": 40}}
    return chat_fn


def call(name, **args):
    return {"tool_calls": [{"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


GOOD = json.dumps({"bind": "127.0.0.1", "port": 11436, "upstream": "http://127.0.0.1:11435"})
DONE = {"content": '{"status":"PASS","artifacts":["runtime/llm-gateway.json"],"issues":[],"next_action":"next"}'}


def test_t025_bounded_context_tools_and_budget(env, monkeypatch):
    b = W.incident_bundle(env["store"], env["inc"], env["infra"])
    assert len(json.dumps(b)) < 6000 and b["runtime_contract_issues"]
    res = W.run_agent(env["inc"], "att-t025", env["store"], scripted(call("read_file", file_path="runtime/llm-gateway.json"), DONE))
    assert res["status"] == "PASS" and res["tokens"] == 680 and res["turns"] == 2

    def hungry(messages, tools, max_tokens=700):
        return {"choices": [{"message": {"role": "assistant", "content": "x"}}], "usage": {"prompt_tokens": 20000,
                                                                                           "completion_tokens": 1}}
    assert W.run_agent(env["inc"], "att-t025b", env["store"], hungry)["status"] == "TOKEN_BUDGET_EXHAUSTED"


def test_t026_protected_paths_denied_by_policy_and_os(env):
    res = W.run_agent(env["inc"], "att-t026", env["store"], scripted(
        call("write_file", file_path="policies/supervisor-protected.json", content="{}"),
        call("write_file", file_path="safety/README.md", content="hacked"), DONE))
    wt = env["tmp"] / "state/repair/worktrees/att-t026"
    assert "hacked" not in (wt / "safety/README.md").read_text()
    with pytest.raises(PermissionError):  # OS-level protection independent of the agent/policy
        (wt / "policies/supervisor-protected.json").write_text("{}")
    assert res["status"] == "PASS"


def test_t027_successful_fix_promoted_atomically(env):
    old = I.git(env["infra"], "rev-parse", "main")
    res = W.run_agent(env["inc"], "att-ok", env["store"], scripted(
        call("write_file", file_path="runtime/llm-gateway.json", content=GOOD), call("validate_runtime_config"), DONE))
    PR.commit_worktree(__import__("pathlib").Path(res["worktree"]), "fix port")
    out = PR.promote("att-ok", env["inc"], env["store"], W.gateway_health, protected_roots=[env["product"]],
                     token_usage={"total": res["tokens"], "basis": "reported"})
    assert out["status"] == "PROMOTED" and all(t["status"] == "PASS" for t in out["tests"])
    assert I.git(env["infra"], "rev-parse", "main") != old and not I.validate_runtime(env["infra"])
    assert env["store"].must(env["inc"])["state"] == "RESOLVED"
    assert env["store"].must(env["inc"])["patch_hash"] == out["patch_sha256"]


def test_t027_failed_tests_roll_back(env):
    old = I.git(env["infra"], "rev-parse", "main")
    res = W.run_agent(env["inc"], "att-bad", env["store"], scripted(
        call("write_file", file_path="runtime/llm-gateway.json", content='{"bind":"0.0.0.0","port":11436}'), DONE))
    PR.commit_worktree(__import__("pathlib").Path(res["worktree"]), "bad fix")
    out = PR.promote("att-bad", env["inc"], env["store"], W.gateway_health)
    assert out["status"] == "ROLLED_BACK" and I.git(env["infra"], "rev-parse", "main") == old
    assert env["store"].must(env["inc"])["state"] == "TRIAGED"  # bounded retry still available (1 of 2 used)


def test_t028_unfixable_requires_offline_attention_and_blocks_package(env, monkeypatch):
    st = env["store"]
    for n in ("a1", "a2"):
        if n == "a2":
            st.transition(env["inc"], "REPAIRING", attempts=2)
        PR.create_repair_worktree(f"att-{n}")
        out = PR.promote(f"att-{n}", env["inc"], st, W.gateway_health)  # no candidate commit = no fix
        assert out["status"] == "FAILED"
    inc = st.must(env["inc"])
    assert inc["state"] == "REQUIRES_OFFLINE_ATTENTION"
    assert len(st.attempts(env["inc"])) >= 2
    # a run whose provenance is affected by the unresolved incident packages BLOCKED with the gap
    ws = env["product"]
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    (ws / ".forge-run").mkdir()
    import sqlite3
    sqlite3.connect(st.path).execute("UPDATE incidents SET run_id='RUN-1' WHERE incident_id=?", (env["inc"],)).connection.commit()
    (ws / ".forge-run/fabro_run_id").write_text("RUN-1")
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(env["tmp"] / "archives"))
    from forge_factory.release.finalize import finalize
    pkg = finalize(ws, "WO-T028")
    assert pkg["package_status"] == "BLOCKED"
    q = json.loads((env["tmp"] / "archives/staging/WO-T028/quality/final-gates.json").read_text())
    assert any(f["id"] == f"INCIDENT:{env['inc']}" for f in q["open_findings"])


def test_t029_product_and_evidence_unchanged_by_infra_repair(env):
    before = PR.tree_hash(env["product"])
    res = W.run_agent(env["inc"], "att-t029", env["store"], scripted(
        call("write_file", file_path=str(env["product"] / "software/src/rcc.c"), content="evil"),
        call("read_file", file_path=str(env["product"] / "evidence/e.json")),
        call("write_file", file_path="runtime/llm-gateway.json", content=GOOD), DONE))
    PR.commit_worktree(__import__("pathlib").Path(res["worktree"]), "fix")
    out = PR.promote("att-t029", env["inc"], env["store"], W.gateway_health, protected_roots=[env["product"]])
    assert out["status"] == "PROMOTED"
    assert PR.tree_hash(env["product"]) == before and (env["product"] / "software/src/rcc.c").read_text() == "int x;\n"
    assert os.path.exists(env["product"] / "evidence/e.json")


def test_t027_protected_change_in_candidate_never_promoted(env):
    wt = PR.create_repair_worktree("att-sneaky")
    import stat
    p = wt / "policies/supervisor-protected.json"
    p.parent.chmod(p.parent.stat().st_mode | stat.S_IWUSR)
    p.chmod(p.stat().st_mode | stat.S_IWUSR)  # simulate an agent that escaped OS protection
    p.write_text('{"weakened": true}')
    PR.commit_worktree(wt, "sneaky")
    old = I.git(env["infra"], "rev-parse", "main")
    out = PR.promote("att-sneaky", env["inc"], env["store"], W.gateway_health)
    assert out["status"] == "ROLLED_BACK" and I.git(env["infra"], "rev-parse", "main") == old
    assert env["store"].must(env["inc"])["state"] == "REQUIRES_OFFLINE_ATTENTION"
