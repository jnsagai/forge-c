"""Normal owner-loop integration with a real private guardian and existing Placer."""

# ruff: noqa: F811 - imported pytest fixture
import json
from pathlib import Path

from forge_factory.afo import controller_escalation as E
from test_owner_supervised_development import supervised  # noqa: F401
from test_owner_supervised_development import test_owner_development_uses_existing_placer_but_never_production_feed as run_main


def test_export_refusal_is_audited_without_poisoning_production_feed_or_guardian_lifetime(supervised, monkeypatch, tmp_path):
    def failed(*a, **kw):
        raise OSError("PRIVATE_FAILURE_NO_RAW_DIAGNOSTIC")

    monkeypatch.setattr(E, "cycle", failed)
    run_main(supervised, monkeypatch, tmp_path)
    record = json.loads(next(Path(supervised["ref"]["path"]).parent.glob("*.audit.jsonl")).read_text())
    assert record["controller_escalation"] == dict(status="CAPTURE_FAILED", code="OSError", exports=[], model_calls=0)
    assert record["placement"]["actions"] == []
    assert "PRIVATE_FAILURE_NO_RAW_DIAGNOSTIC" not in json.dumps(record)
