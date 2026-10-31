"""Deployment-owned CRE selection reaches the existing recovery authority."""
import copy
import os

import pytest
import yaml
from forge_factory.afo import operations
from forge_factory.reliability import policy as P


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    policy = copy.deepcopy(yaml.safe_load(P.POLICY_PATH.read_text()))
    policy["mode"] = "ACTIVE"
    policy["authorization"] = {"runbook_ref": "synthetic-fixture-only", "approved_by": "test-owner", "approved_on": "2026-10-27"}
    policy["promotion"]["allowed_automatic_operational_actions"] = ["restart_conductor", "restart_local_stack"]
    path = tmp_path / "deployment-cre.yaml"
    path.write_text(yaml.safe_dump(policy))
    monkeypatch.setenv("FORGE_CRE_POLICY", str(path))
    return path, policy


def test_operational_recipe_uses_explicit_deployment_policy(configured):
    path, _ = configured
    assert P.load().path == str(path)
    assert operations.operational_authorized("restart_conductor")
    assert operations.operational_authorized("restart_local_stack")
    assert not operations.operational_authorized("restart_dashboard")


def test_explicit_argument_has_precedence_and_repository_defaults_stay_observe(configured):
    assert P.load(P.POLICY_PATH).mode == "OBSERVE_ONLY"


def test_holder_uses_and_reloads_the_deployment_file(configured):
    path, value = configured
    holder = P.PolicyHolder()
    assert holder.path == path and holder.current().mode == "ACTIVE"
    before = path.stat().st_mtime_ns
    value["promotion"]["allowed_automatic_operational_actions"] = ["restart_conductor"]
    path.write_text(yaml.safe_dump(value))
    os.utime(path, ns=(before + 10000000, before + 10000000))
    assert not holder.current().automatic_action_allowed("restart_local_stack")


def test_malformed_live_override_keeps_the_last_valid_holder_policy(configured):
    path, _ = configured
    holder = P.PolicyHolder()
    before = holder.current().sha256
    stamp = path.stat().st_mtime_ns + 10000000
    path.write_text("not: [valid")
    os.utime(path, ns=(stamp, stamp))
    assert holder.current().sha256 == before
    assert holder.rejections and holder.rejections[0][0].startswith("POLICY_UNREADABLE:")


@pytest.mark.parametrize("change", ["missing", "malformed", "weakened"])
def test_invalid_override_never_falls_back_or_grants_a_recipe(configured, change):
    path, value = configured
    if change == "missing":
        path.unlink()
    elif change == "malformed":
        path.write_text("not: [valid")
    else:
        value["promotion"]["auto_promote_persistent_code"] = True
        path.write_text(yaml.safe_dump(value))
    assert not operations.operational_authorized("restart_conductor")
    with pytest.raises((OSError, ValueError, yaml.YAMLError)):
        P.load()


def test_no_override_preserves_repository_policy(monkeypatch):
    monkeypatch.delenv("FORGE_CRE_POLICY", raising=False)
    assert P.load().path == str(P.POLICY_PATH)
    assert P.load().mode == "OBSERVE_ONLY"
