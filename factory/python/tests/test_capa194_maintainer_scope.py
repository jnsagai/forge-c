"""CAPA-194 (owner 2026-11-08 "do 2 too"): afo/ is open to the factory maintainer except its trust anchors, so a factory
isolated from the network and from Claude can repair its own guardian/line code. The anchors stay denied."""
from pathlib import Path

import pytest
from forge_factory.afo import maintainer as M

AFO = "factory/python/forge_factory/afo/"
REPO = Path(__file__).resolve().parents[3]
OPEN = ["line_orders.py", "owner_supervised_development.py", "queue.py", "line_stack_lifecycle.py", "bundle.py",
        "execution_lifecycle.py", "line_recovery_worker.py", "conductor.py"]
ANCHORS = ["maintainer.py", "line_maintenance_coordinator.py", "line_maintenance.py", "maintenance_binding.py",
           "maintenance_rework.py", "verification_job.py", "line_verifier_guard.py", "authz.py", "authority.py",
           "policy.py", "owner_launch_guard.py", "owner_launch_guard.sh", "owner_development_allowance.py",
           "mission_ledger.py", "mission_capacity.py", "mission_deadline.py", "mission_admin.py", "acceptance.py",
           "durable.py", "product_role_trial.py", "owner_bootstrap_history.py", "history_qualification.py",
           "qualification.py", "qualification_audit.py"]


@pytest.mark.parametrize("name", OPEN)
def test_guardian_and_line_code_is_open_to_the_maintainer(name):
    assert (REPO / AFO / name).is_file()
    assert M.path_issue(AFO + name, []) is None


@pytest.mark.parametrize("name", ANCHORS)
def test_trust_anchors_stay_denied(name):
    assert (REPO / AFO / name).is_file(), "anchor named in the test must exist"
    assert M.path_issue(AFO + name, []) == "MAINTAINER_DENIED_PATH"


@pytest.mark.parametrize("rel", ["factory/python/forge_factory/reliability/promotion.py",
                                 "factory/python/forge_factory/registry/agents.py",
                                 "factory/python/forge_factory/policy/x.py",
                                 "factory/python/forge_factory/supervisor/x.py",
                                 "factory/python/forge_factory/release/x.py",
                                 "factory/python/forge_factory/repair/x.py",
                                 "factory/python/forge_factory/mcp/sdk.py",
                                 "factory/python/forge_factory/mcp/servers/maintainer.py"])
def test_other_guarded_trees_unchanged(rel):
    assert M.path_issue(rel, []) == "MAINTAINER_DENIED_PATH"


def test_every_existing_afo_anchor_file_is_denied_and_nothing_else_is():
    denied = sorted(p.name for p in (REPO / AFO).iterdir() if p.is_file() and M.path_issue(AFO + p.name, []))
    assert set(ANCHORS) <= set(denied)
    assert not set(OPEN) & set(denied)
