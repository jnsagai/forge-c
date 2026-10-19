"""CRE-T004 — reliability policy: default OBSERVE_ONLY, hard invariants, floors, budgets, live reload (AT-001, AT-020)."""
import copy
import os
import time

import pytest
import yaml
from forge_factory.reliability import policy as P


@pytest.fixture(autouse=True)
def _events(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))


def base():
    return yaml.safe_load(P.POLICY_PATH.read_text())


def test_repository_policy_is_valid_observe_only_with_no_auto_promotion_at001():
    pol = P.load()
    assert pol.mode == "OBSERVE_ONLY"
    assert pol.get("promotion.auto_promote_persistent_code") is False
    assert pol.get("supervisor.invoke_model_on_healthy_poll") is False
    assert pol.get("promotion.allowed_automatic_operational_actions") == []
    assert not pol.automatic_action_allowed("restart_dashboard")
    assert len(pol.sha256) == 64


@pytest.mark.parametrize("path,value,code", [
    ("recovery.max_transient_retries_per_operation", -1, "SCHEMA:recovery/max_transient_retries_per_operation"),
    ("recovery.max_repair_attempts_per_incident", 50, "SCHEMA:recovery/max_repair_attempts_per_incident"),
    ("security.audit_channel_min_level", "OFF", "AUDIT_CAPTURE_WEAKENED"),
    ("promotion.allow_auto_mutation_of_safety_rules", True, "HARD_INVARIANT_WEAKENED:promotion.allow_auto_mutation"),
    ("promotion.auto_promote_persistent_code", True, "HARD_INVARIANT_WEAKENED:promotion.auto_promote"),
    ("readiness.safety_approval_by_ai", True, "HARD_INVARIANT_WEAKENED:readiness.safety_approval_by_ai"),
    ("statistics.unknown_is_success", True, "HARD_INVARIANT_WEAKENED:statistics.unknown_is_success"),
    ("supervisor.invoke_model_on_healthy_poll", True, "HARD_INVARIANT_WEAKENED:supervisor.invoke_model"),
    ("promotion.forbid_test_oracle_edits", False, "HARD_INVARIANT_WEAKENED:promotion.forbid_test_oracle_edits"),
])
def test_weakened_or_invalid_policy_is_rejected_before_execution_at001(path, value, code):
    pol = base()
    cur = pol
    *head, last = path.split(".")
    for k in head:
        cur = cur[k]
    cur[last] = value
    issues = P.issues_of(pol)
    assert any(i.startswith(code) for i in issues), issues


def test_floors_cannot_be_removed_and_budgets_cannot_exceed_the_supervisor():
    pol = base()
    pol["recovery"]["non_replayable_operation_classes"] = ["hardware_flash"]
    pol["security"]["protected_path_globs"] = ["evidence/**"]
    pol["recovery"]["max_repairs_per_hour"] = 5
    issues = P.issues_of(pol, {"repair": {"max_attempts_per_incident": 2, "max_attempts_per_hour": 3}})
    assert any(i.startswith("NON_REPLAYABLE_FLOOR_REMOVED:baselined_evidence_mutation") for i in issues)
    assert any(i.startswith("PROTECTED_PATH_FLOOR_REMOVED") for i in issues)
    assert "EXCEEDS_SUPERVISOR_BUDGET:recovery.max_repairs_per_hour=5>3" in issues
    more = base()
    more["recovery"]["non_replayable_operation_classes"].append("bootloader_write")  # adding is allowed
    more["security"]["protected_path_globs"].append("docs/adr/**")
    assert P.issues_of(more) == []


def test_active_mode_needs_authorization_and_only_reversible_actions_at020():
    pol = base()
    pol["mode"] = "ACTIVE"
    assert "MODE_ACTIVE_REQUIRES_AUTHORIZATION" in P.issues_of(pol)
    pol["authorization"] = {"runbook_ref": "docs/runbook.md", "approved_by": "<owner>", "approved_on": "2026-10-16"}
    assert "AUTHORIZATION_PLACEHOLDER" in P.issues_of(pol)
    pol["authorization"]["approved_by"] = "owner"
    pol["promotion"]["allowed_automatic_operational_actions"] = ["restart_dashboard", "promote_candidate_code"]
    assert "ACTION_NOT_REVERSIBLE_CATALOGUE:promote_candidate_code" in P.issues_of(pol)
    pol["promotion"]["allowed_automatic_operational_actions"] = ["restart_dashboard"]
    assert P.issues_of(pol) == []
    obs = base()
    obs["promotion"]["allowed_automatic_operational_actions"] = ["restart_dashboard"]
    assert "AUTOMATIC_ACTIONS_REQUIRE_ACTIVE_MODE" in P.issues_of(obs)


def test_invalid_live_edit_keeps_the_last_good_policy(tmp_path):
    f = tmp_path / "reliability-policy.yaml"
    f.write_text(P.POLICY_PATH.read_text())
    holder = P.PolicyHolder(f)
    good = holder.current().sha256
    bad = copy.deepcopy(base())
    bad["promotion"]["auto_promote_persistent_code"] = True
    time.sleep(0.01)
    f.write_text(yaml.safe_dump(bad))
    os.utime(f, (time.time() + 5, time.time() + 5))
    assert holder.current().sha256 == good and holder.current().get("promotion.auto_promote_persistent_code") is False
    assert holder.rejections and any("auto_promote" in i for i in holder.rejections[0])
