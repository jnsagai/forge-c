"""Source-bound comparison inspection capacity; no retroactive refill or author/role authority expansion."""
import copy
import json

import pytest
from forge_factory.lrtx import profile as P
from forge_factory.policy import governor as G


def workspace(tmp_path, *, bound=True):
    p = P.load("cloud-bridge-terra-author-sol-inspector")
    ws = tmp_path / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    m = {"purpose": "ASPICE_ONLY", "local_profile": {"id": p["id"], "config_sha256": p["_sha256"]}}
    if bound:
        m["profile_inspector_budget"] = G.profile_inspector_capacity_binding(p)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    return ws, m


def test_inspector_can_read_past_16_but_verdict_reservation_and_finite_ceiling_remain(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, _ = workspace(tmp_path)
    for _ in range(30):
        allowed, count, limit, reserved = G.count_tool_call("capacity", "run", "inspector", "swe2-inspector",
                                                         "read_file", str(ws))
        assert allowed and not reserved
    assert (count, limit) == (30, 64)
    G._update("capacity", lambda st: st.update({"run:inspector": 60}))
    assert G.count_tool_call("capacity", "run", "inspector", "swe2-inspector", "read_file", str(ws)) == (False, 60, 64, True)
    close = "mcp__forge_evidence_mcp__check_inspection"
    assert G.count_tool_call("capacity", "run", "inspector", "swe2-inspector", close, str(ws))[:3] == (True, 61, 64)
    G._update("capacity", lambda st: st.update({"run:inspector": 64}))
    assert not G.count_tool_call("capacity", "run", "inspector", "swe2-inspector", close, str(ws))[0]
    G.reset_node("capacity", "run", "inspector")
    assert G.count_tool_call("capacity", "run", "inspector", "swe2-inspector", "read_file", str(ws))[1] == 1


def test_old_jobs_authors_and_local_profile_retain_existing_limits(tmp_path):
    ws, _ = workspace(tmp_path, bound=False)
    assert G.turn_limit("swe2-inspector", str(ws)) == 20
    ws, _ = workspace(tmp_path / "new")
    assert G.turn_limit("swe2-author", str(ws)) == 35
    assert G.profile_inspector_capacity_binding(P.load("local-rtx-v2-omniverse2-ornith-think-author-q38-inspector")) is None


def test_workorder_intake_seals_selected_capacity_before_any_model_launch(tmp_path, monkeypatch):
    from forge_factory import workorder as W

    p = P.load("cloud-bridge-terra-author-sol-inspector")
    selected = {"id": p["id"], "version": p["version"], "config": p["_path"],
                "config_sha256": p["_sha256"], "status": p["status"], "timeout_scale": 1}
    monkeypatch.setattr(P, "select", lambda *a, **k: selected)
    monkeypatch.setattr(W, "suspension", lambda provider: None)
    example = tmp_path / "example"
    example.mkdir()
    (example / "workorder.json").write_text('{}')
    ws = tmp_path / "prepared"
    (ws / ".forge-run").mkdir(parents=True)
    manifest = {"purpose": "ASPICE_ONLY"}
    monkeypatch.setattr(W, "prepare", lambda *a, **k: (ws, manifest))
    W.run(example, "WO-CAPACITY", intake_only=True, profile=p["id"], model="gpt-6.1-terra", purpose="ASPICE_ONLY")
    saved = json.loads((ws / ".forge-run/manifest.json").read_text())
    assert saved["profile_inspector_budget"] == G.profile_inspector_capacity_binding(p)
    assert G.turn_limit("swe2-inspector", str(ws)) == 64
    assert not (ws / ".forge-run/fabro_run_id").exists()


@pytest.mark.parametrize("mutation", ["limit", "profile_hash", "id", "purpose"])
def test_modified_binding_is_refused(tmp_path, mutation):
    ws, m = workspace(tmp_path)
    if mutation == "limit":
        m["profile_inspector_budget"]["inspector_calls_per_visit"] += 1
    elif mutation == "profile_hash":
        m["local_profile"]["config_sha256"] = "0" * 64
    elif mutation == "id":
        m["local_profile"]["id"] = "../../untrusted"
    else:
        m["purpose"] = "DEVELOPMENT"
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError, match="PROFILE_INSPECTOR_TOOL_BUDGET_BINDING_CHANGED"):
        G.turn_limit("swe2-inspector", str(ws))


@pytest.mark.parametrize("limit", [True, 0, 4, -1, 257, "64"])
def test_invalid_capacity_is_not_clamped(limit):
    p = copy.deepcopy(P.load("cloud-bridge-terra-author-sol-inspector"))
    p["structured"]["native_inspector_tool_calls_per_visit"] = limit
    with pytest.raises(ValueError, match="PROFILE_INSPECTOR_TOOL_BUDGET_INVALID"):
        G.profile_inspector_capacity_binding(p)
