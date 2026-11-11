"""CAPA-237 (owner lane 2026-11-11, WWDG LL SWE.2 L44B): the workorder refused at validated_resume, before the native
launch hook, so no PRODUCT_NATIVE_ADMISSION_REFUSAL evidence existed; the line worker classified WORKORDER_LAUNCH_FAILED as
an unknown native outcome, the inference lease stayed HELD (liveness UNKNOWN) and the guardian restarted a supervision
worker every cycle, which also blocked every deploy (LINE_KEEPS_QUEUEING). A refusal the workorder CLI raises before
native submission now records that evidence through the durable launch's own callback."""
import json

import pytest
from forge_factory import workorder as W
from forge_factory.brownfield.resume import ResumeRefused


@pytest.fixture
def cli(tmp_path, monkeypatch):
    seen = []
    from forge_factory.afo import line_recovery_product as P

    monkeypatch.setattr(P, "native_parameters", lambda path, sha, expected: {
        "recovery_plan": None, "durable_binding": {}, "labels": {}, "before_native_launch": lambda: None,
        "refused_before_native": seen.append})
    argv = ["--example", str(tmp_path), "--wo", "WO-T", "--resume-from", "WO-S", "--stop-after", "SWE.2",
            "--durable-launch", str(tmp_path / "d.json"), "--durable-launch-sha256", "a" * 64]
    return seen, argv


def test_a_pre_native_resume_refusal_is_recorded(cli, monkeypatch, capsys):
    seen, argv = cli

    def run(*a, **kw):
        assert "refused_before_native" not in kw  # the hook never reaches run()
        raise ResumeRefused("RESUME_CONTRACT_OR_RUNTIME_CHANGED")
    monkeypatch.setattr(W, "run", run)
    assert W.main(argv) == 2
    assert seen == ["validated_resume"] and json.loads(capsys.readouterr().out)["stage"] == "validated_resume"


def test_a_successful_launch_records_no_refusal(cli, monkeypatch):
    seen, argv = cli
    monkeypatch.setattr(W, "run", lambda *a, **kw: {"work_order": "WO-T", "fabro_run_id": "R"})
    assert W.main(argv) == 0 and seen == []


def test_the_callback_never_overrides_a_submit_intent():
    from forge_factory.afo import line_recovery_product as P

    saved = []

    class Ex:
        def __init__(self, store):
            pass

        def _evidence(self, job_id, kind):
            return {"x": 1} if kind == "PRODUCT_NATIVE_SUBMIT_INTENT" and job_id == "submitted" else None

        def _save_evidence(self, job_id, kind, value):
            saved.append((job_id, kind, value["failure_type"]))

    P.record_pre_native_refusal(None, {"job_id": "submitted", "nonce": "n"}, "validated_resume", executions=Ex)
    P.record_pre_native_refusal(None, {"job_id": "fresh", "nonce": "n"}, "validated_resume", executions=Ex)
    assert saved == [("fresh", "PRODUCT_NATIVE_ADMISSION_REFUSAL", "validated_resume")]
