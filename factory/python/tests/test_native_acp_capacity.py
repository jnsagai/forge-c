"""Explicit native controls use a finite, source-bound budget; ACP visits do not inherit exhausted counters."""
import json

import pytest
from forge_factory.acp import proxy
from forge_factory.policy import governor as G
from forge_factory.policy.authz import Binding


def native_ws(tmp_path):
    ws = tmp_path / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    manifest = {"purpose": "ASPICE_ONLY", "native_aspice_backends": {
        "authors": "codex", "inspectors": "claude", "tool_budget": G.native_capacity_binding()}}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    return ws, manifest


def test_native_author_can_pass_the_observed_35_call_boundary_without_granting_inspector_capacity(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, _ = native_ws(tmp_path)
    for _ in range(40):
        allowed, count, limit, reserved = G.count_tool_call("capacity", "run", "author", "swe1-author", "read_file", str(ws))
        assert allowed and not reserved
    assert count == 40 and limit == 4096
    assert G.turn_limit("swe1-inspector", str(ws)) == 20
    # Reach the finite boundary without performing thousands of artificial file writes.
    G._update("capacity", lambda st: st.update({"run:author": 4095}))
    assert G.count_tool_call("capacity", "run", "author", "swe1-author", "read_file", str(ws))[:3] == (True, 4096, 4096)
    assert G.count_tool_call("capacity", "run", "author", "swe1-author", "read_file", str(ws))[:3] == (False, 4097, 4096)


@pytest.mark.parametrize("mutation", ["limit", "purpose", "backend"])
def test_modified_budget_binding_cannot_expand_authority(tmp_path, mutation):
    ws, manifest = native_ws(tmp_path)
    if mutation == "limit":
        manifest["native_aspice_backends"]["tool_budget"]["author_calls_per_visit"] += 1
    elif mutation == "purpose":
        manifest["purpose"] = "DEVELOPMENT"
    else:
        manifest["native_aspice_backends"]["authors"] = "unregistered"
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="NATIVE_ASPICE_TOOL_BUDGET_BINDING_CHANGED"):
        G.turn_limit("swe1-author", str(ws))


def test_legacy_and_qwen_jobs_keep_their_existing_governor_selection(tmp_path):
    ws, manifest = native_ws(tmp_path)
    manifest.pop("native_aspice_backends")
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    assert G.turn_limit("swe1-author", str(ws)) == 35


def test_first_prompt_starts_one_visit_and_subsequent_prompts_do_not_refill_it(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, _ = native_ws(tmp_path)
    path = ws / ".forge-run/binding.json"
    Binding("visit", str(ws), {"author": {"role": "swe1-author", "phase": "SWE.1"}}).dump(path)
    (ws / ".forge-run/fabro_run_id").write_text("run")
    G._update("visit", lambda st: st.update({"run:author": 35}))

    def visit():
        p = proxy.Proxy.__new__(proxy.Proxy)
        p.binding_path, p.node, p.kind, p.ws = path, "author", "codex", ws
        p.visit_budget_started = False
        p.prompts = set()
        p._log = lambda _: None
        return p

    def prompt(p, ident):
        p.from_client({"jsonrpc": "2.0", "id": ident, "method": "session/prompt",
                       "params": {"sessionId": "S", "prompt": []}})

    first = visit()
    prompt(first, 1)
    assert G.count_tool_call("visit", "run", "author", "swe1-author", "read_file", str(ws))[1] == 1
    prompt(first, 2)
    assert G.count_tool_call("visit", "run", "author", "swe1-author", "read_file", str(ws))[1] == 2
    second = visit()
    prompt(second, 3)
    assert G.count_tool_call("visit", "run", "author", "swe1-author", "read_file", str(ws))[1] == 1
