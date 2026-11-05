"""Native maintenance admission reuses isolated cases and existing durable ownership; zero inference."""
import json
from pathlib import Path

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.afo.queue import QueueError
from test_line_maintenance import terminal, local, order, factory, prepare  # noqa: F401


def case_path(case):
    from forge_factory.afo.maintainer import case_dir
    return case_dir(case["proposal_id"]) / "case.json"


def prepare_job(terminal, case):
    args, eff, _, _, _ = terminal
    s, oid, aid, workspace, origin = args
    return L.prepare(s, s.order(oid), aid, "afo-factory-maintainer", case_path(case), workspace, eff, line_origin=origin)


def test_line_maintainer_uses_own_durable_protocol_and_finite_existing_mission(terminal, monkeypatch):
    case = prepare(terminal)
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    result = prepare_job(terminal, case)
    assert result["durable_native"] == "maintenance-1" and not result.get("durable_protocol")
    assert result["work_class"] == "MAINTENANCE" and result["line_context_sha256"]
    assert result["mission_id"] == case["line_binding"]["mission_id"]
    assert result["native_context"]["FORGE_AFO_QUEUE_SCOPE"] == "line-local"
    assert prepare_job(terminal, case) == result


def test_no_legacy_protocol_fallback_and_no_changed_case_binding(terminal, monkeypatch):
    case = prepare(terminal)
    monkeypatch.delenv("FORGE_DURABLE_AUTONOMY", raising=False)
    with pytest.raises(QueueError, match="DURABLE_PROTOCOL_REQUIRED"):
        prepare_job(terminal, case)
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    path = case_path(case)
    changed = json.loads(path.read_text())
    changed["line_binding"]["context_sha256"] = "0" * 64
    path.chmod(0o600)
    path.write_text(json.dumps(changed))
    with pytest.raises(QueueError, match="CASE_BINDING_MISMATCH"):
        prepare_job(terminal, case)
