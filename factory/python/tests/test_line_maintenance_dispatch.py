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


def test_omniverse_maintainer_uses_qwen_and_its_own_approved_trial():
    from forge_factory.afo.owner_supervised_development import MAINTAINER_MODEL, PROFILE, RUN_MODEL
    from forge_factory.lrtx.profile import load
    from forge_factory.modelservice import maintenance

    assert MAINTAINER_MODEL == "qwen3.8:27b-q8_0"
    assert MAINTAINER_MODEL in load(PROFILE)["models"]["allowed"]
    assert L.role_model(PROFILE, "afo-factory-maintainer", RUN_MODEL) == MAINTAINER_MODEL
    assert L.role_model(PROFILE, "afo-recovery-planner", RUN_MODEL) == RUN_MODEL
    assert L.role_model("a-different-profile", "afo-factory-maintainer", "fixture") == "fixture"
    assert maintenance.DEFAULT_MODEL == MAINTAINER_MODEL

    ornith_reference = {"path": "/ornith.json", "sha256": "1" * 64}
    qwen_reference = {"path": "/qwen.json", "sha256": "2" * 64}
    control = {"product_role_trial": ornith_reference,
               "product_role_trials": {RUN_MODEL: ornith_reference, MAINTAINER_MODEL: qwen_reference}}
    assert L.control_model_trial(control, MAINTAINER_MODEL) == qwen_reference
    assert L.control_model_trial(control, RUN_MODEL) == ornith_reference
    with pytest.raises(QueueError, match="LOCAL_RECOVERY_MODEL_TRIAL_REQUIRED"):
        L.control_model_trial(control, "unbound-model")
    assert L.control_model_trial({"product_role_trial": ornith_reference}, RUN_MODEL) == ornith_reference
