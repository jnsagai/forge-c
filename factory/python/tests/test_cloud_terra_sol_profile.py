"""The resumed cloud line keeps the engineering runner and uses both requested account models."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.lrtx import cloud_bridge as CB, profile as P


PROFILE = "cloud-bridge-terra-author-sol-inspector"


def test_floor_reports_the_account_roles_without_charging_account_usage(tmp_path, monkeypatch):
    import time
    from forge_factory.lrtx.floor_api import cloud_station

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    roles = P.role_models(P.load(PROFILE))
    monkeypatch.setenv("FORGE_FLOOR_ACCOUNT_MODELS", json.dumps(roles))
    meter = tmp_path / "cloud-bridge/calls.jsonl"
    meter.parent.mkdir()
    meter.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "model": roles["author"], "backend": "codex", "ok": True,
                                "usage": {"billing": "account", "prompt_tokens": 10}}) + "\n")
    station = cloud_station(time.time())
    assert station["account_models"] == roles and station["cost_today_usd"] == 0
    assert station["models"][0]["today"]["account_calls"] == 1
    monkeypatch.setenv("FORGE_FLOOR_ACCOUNT_MODELS", '[]')
    assert cloud_station(time.time())["account_models"] == {}


def test_model_switch_preserves_the_comparison_runner_and_host_isolation():
    old = P.load("cloud-bridge-claude-author-codex-inspector")
    new = P.load(PROFILE)
    assert P.role_models(new) == {"author": "gpt-6.1-terra", "inspector": "gpt-6.1-sol"}
    for key in ("gateway", "admission", "deployment", "network", "work_order_purpose"):
        assert new[key] == old[key]
    assert {k: v for k, v in new["structured"].items() if k != "role_models"} == {
        k: v for k, v in old["structured"].items() if k != "role_models"}


@pytest.mark.parametrize("model", ["gpt-6.1-terra", "gpt-6.1-sol"])
def test_both_roles_reach_the_requested_cli_model_and_never_an_api(tmp_path, monkeypatch, model):
    cfg = P.load(PROFILE)["runtime"]["cloud_bridge"]["models"]
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-worker")
    seen = []

    def run(argv, **kw):
        seen.append((argv, kw))
        Path(argv[argv.index("-o") + 1]).write_text('{"status":"PASS"}')
        return SimpleNamespace(returncode=0, stdout=json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 10, "output_tokens": 5}}), stderr="")

    # An API mode selection cannot override an explicitly account-only profile.
    mode = tmp_path / "mode.json"
    mode.write_text('{"mode":"api"}')
    bridge = CB.Bridge(cfg, {"codex": CB.CodexBackend(str(tmp_path), run=run)},
                       tmp_path / "calls.jsonl", mode, mode)
    result = bridge.complete({"model": model, "messages": [{"role": "user", "content": "Return status JSON"}]})
    argv, kw = seen[0]
    assert argv[argv.index("-m") + 1] == model
    assert "OPENAI_API_KEY" not in kw["env"]
    assert "--ephemeral" in argv and argv[argv.index("--sandbox") + 1] == "read-only"
    assert result["text"] == '{"status":"PASS"}'
    meter = json.loads((tmp_path / "calls.jsonl").read_text())
    assert meter["model"] == model and meter["backend"] == "codex" and meter["usage"]["billing"] == "account"
