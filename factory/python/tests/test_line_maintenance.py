"""Existing isolated case/broker with unit authority fixtures, not a production model qualification."""
import json
import time
from pathlib import Path

import pytest
from forge_factory.afo import line_maintenance as M
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import QueueError
from test_afo_local_autonomy import local, order  # noqa: F401
from test_afo_m5_maintainer import factory, _head  # noqa: F401


@pytest.fixture
def terminal(local, factory, monkeypatch, tmp_path):
    s, o, b, eff, ws, _ = local
    from forge_factory.reliability import isolation
    monkeypatch.setattr(isolation, "available", lambda: True)  # unit fixture, no production isolation claim
    monkeypatch.setattr(isolation, "base", lambda: tmp_path / "isolated-case-fixture")
    s.attempt_transition(b["attempt_id"], "FAILED")
    context = {"source_revision": _head(factory), "generation": 1}
    monkeypatch.setattr(M.line_recovery, "context", lambda *a: dict(context))
    incident = dict(b, failure_class="FACTORY_CODE_DEFECT")
    monkeypatch.setattr(M.bundle, "build", lambda *a, **kw: dict(incident))
    ledger = MissionLedger(s)
    ledger.register("line-maintenance-fixture", "line-maintenance-fixture", {
        "max_attempts": 0, "max_jobs": 1, "max_requests": 1, "max_tokens": 131072,
        "max_tools": 10, "max_corrections": 0, "deadline": time.time() + 600,
    }, "FIXTURE_ONLY", authorize=lambda *a: True)
    ledger.link("line-maintenance-fixture", o["order_id"])
    args = (s, o["order_id"], b["attempt_id"], ws, {"campaign_path": "/approved/campaign"})
    return args, eff, factory, context, incident


def prepare(terminal):
    args, eff, repo, _, _ = terminal
    return M.prepare(*args, eff=eff, repo=repo)


def test_case_uses_existing_protected_isolated_broker_and_is_restart_idempotent(terminal):
    case = prepare(terminal)
    assert prepare(terminal) == case
    assert Path(case["src"]) != terminal[2]
    assert case["line_binding"]["mission_id"] == "line-maintenance-fixture"
    assert case["base"] == terminal[3]["source_revision"]
    path = Path(case["src"]) / "tests/reliability/reproducers/manifest.yaml"
    assert path.stat().st_mode & 0o222 == 0
    assert case["incident"]["failure_class"] == "FACTORY_CODE_DEFECT"


def test_changed_context_does_not_rewrite_an_existing_case(terminal):
    case = prepare(terminal)
    path = M.maintainer.case_dir(case["proposal_id"]) / "case.json"
    original = path.read_bytes()
    terminal[3]["generation"] = 2
    with pytest.raises(QueueError, match="CASE_REBOUND"):
        prepare(terminal)
    assert path.read_bytes() == original


def test_no_role_authority_no_sandbox_or_nonfactory_defect_never_creates_a_case(terminal, monkeypatch):
    terminal[1].policy["maintenance"]["enable_factory_maintainer"] = False
    with pytest.raises(QueueError, match="NOT_AUTHORIZED"):
        prepare(terminal)
    terminal[1].policy["maintenance"]["enable_factory_maintainer"] = True
    terminal[4]["failure_class"] = "PRODUCT_QUALITY"
    with pytest.raises(QueueError, match="REQUIRES_FACTORY_DEFECT"):
        prepare(terminal)
    terminal[4]["failure_class"] = "FACTORY_CODE_DEFECT"
    from forge_factory.reliability import isolation
    monkeypatch.setattr(isolation, "available", lambda: False)
    with pytest.raises(QueueError, match="SANDBOX_UNAVAILABLE"):
        prepare(terminal)
    assert not list(Path(terminal[0][3]).parent.glob("mnt-*/case.json"))


def test_foreign_attempt_cannot_prepare_maintenance(terminal):
    args, eff, repo, _, _ = terminal
    with pytest.raises(QueueError, match="TERMINAL_SOURCE"):
        M.prepare(*(args[:2] + ("foreign",) + args[3:]), eff=eff, repo=repo)
