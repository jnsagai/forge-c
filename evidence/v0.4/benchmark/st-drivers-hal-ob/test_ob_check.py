"""Negative controls for the offline acceptance-record checker; all keys and packages are disposable fixtures."""
import copy
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("ob_check", Path(__file__).with_name("ob_check.py"))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def record(tmp_path, monkeypatch):
    key = tmp_path / "throwaway"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    allowed = tmp_path / "allowed"
    allowed.write_text("tester " + key.with_suffix(".pub").read_text())
    decisions = tmp_path / "decisions"
    signed = decisions / "OA-fixture" / "approval.json"
    signed.parent.mkdir(parents=True)
    approval = {"approval_id": "OA-fixture", "package_sha256": "a" * 64, "decided_by": "tester"}
    signed.write_text(json.dumps(approval))
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", "forge-onboarding-approval", "-f", str(key), str(signed)],
                   capture_output=True, check=True)
    monkeypatch.setattr(checker, "ALLOWED_SIGNERS", allowed)
    monkeypatch.setattr(checker, "DECISIONS", decisions)
    archive = tmp_path / "review.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("manifest.json", '{"status":"BLOCKED"}')
    outcome = {"package_status": "BLOCKED", "archive": str(archive), "archive_sha256": checker.digest(archive),
               "gap_count": 1, "gaps": ["UPSTREAM_NOT_PROVIDED"]}
    workspace = tmp_path / "workspace"
    marker = workspace / ".forge-run/package.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps(outcome))
    attempt = {"fabro_run_id": "fixture", "factory_revision": "f" * 40, "workspace": str(workspace),
               "onboarding": {"sha256": "a" * 64, "approval_id": "OA-fixture"},
               "baselines": [{"onboarding_sha256": "a" * 64}], "package_record": outcome,
               "package_record_sha256": checker.digest(marker)}
    return {"schema": "forge-c/st-hal-onboarding-acceptance/0.1", "packages": {"gpio": {
        "canonical_hash_ok": True, "approval_code": "APPROVAL_OK", "sha256": "a" * 64, "approval": approval,
        "approval_sha256": checker.digest(signed), "signature_sha256": checker.digest(Path(str(signed) + ".sig")),
        "prompt_origins": [{"from": "template:fixture"}]}},
        "orders": [{"peripheral": "gpio", "state": "BLOCKED", "attempts": [attempt]}]}


def test_terminal_blocked_fixture_is_reported_without_a_ready_or_sc005_claim(record, capsys):
    checker.check(record, ("gpio",))
    assert "BLOCKED" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["not_run", "running", "binding", "signature", "archive", "marker"])
def test_incomplete_tampered_or_wrongly_bound_records_are_refused(record, failure):
    record = copy.deepcopy(record)
    if failure == "not_run":
        record["orders"] = []
    elif failure == "running":
        record["orders"][0]["state"] = "RUNNING"
    elif failure == "binding":
        record["orders"][0]["attempts"][0]["onboarding"]["sha256"] = "b" * 64
    elif failure == "signature":
        record["packages"]["gpio"]["signature_sha256"] = "b" * 64
    elif failure == "archive":
        Path(record["orders"][0]["attempts"][0]["package_record"]["archive"]).write_bytes(b"tampered")
    else:
        record["orders"][0]["attempts"][0]["package_record"]["gap_count"] = 0
    with pytest.raises(AssertionError):
        checker.check(record, ("gpio",))
