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
    workspace = tmp_path / "workspace"
    owner_input = workspace / "inputs/owner.txt"
    owner_input.parent.mkdir(parents=True)
    owner_input.write_text("owner fixture")
    inputs = [{"path": "inputs/owner.txt", "role": "datasheet", "sha256": checker.digest(owner_input)}]
    snapshot = {"inputs": inputs, "texts": {"prompt": {"cover": {"text": "fixture", "from": "template:fixture"}}}}
    package_hash = checker.facts.canonical_hash(snapshot)
    key = tmp_path / "throwaway"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    allowed = tmp_path / "allowed"
    allowed.write_text("tester " + key.with_suffix(".pub").read_text())
    decisions = tmp_path / "decisions"
    signed = decisions / "OA-fixture" / "approval.json"
    signed.parent.mkdir(parents=True)
    approval = {"approval_id": "OA-fixture", "package_sha256": package_hash, "decided_by": "tester"}
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
    marker = workspace / ".forge-run/package.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps(outcome))
    (workspace / ".forge-run/manifest.json").write_text(json.dumps({"inputs": inputs, "delivered": []}))
    baseline = workspace / "baseline.json"
    baseline.write_text(json.dumps({"onboarding_sha256": package_hash}))
    attempt = {"fabro_run_id": "fixture", "factory_revision": "f" * 40, "workspace": str(workspace),
               "onboarding": {"sha256": package_hash, "approval_id": "OA-fixture"},
               "inputs": inputs, "delivered_code": [],
               "baselines": [{"onboarding_sha256": package_hash, "path": str(baseline),
                              "sha256": checker.digest(baseline)}], "package_record": outcome,
               "package_record_sha256": checker.digest(marker)}
    return {"schema": "forge-c/st-hal-onboarding-acceptance/0.2", "packages": {"gpio": {
        "canonical_hash_ok": True, "approval_code": "APPROVAL_OK", "sha256": package_hash, "approval": approval,
        "package_snapshot": snapshot, "inputs": inputs,
        "approval_sha256": checker.digest(signed), "signature_sha256": checker.digest(Path(str(signed) + ".sig")),
        "prompt_origins": [{"section": "prompt", "key": "cover", "from": "template:fixture"}]}},
        "orders": [{"peripheral": "gpio", "state": "BLOCKED", "attempts": [attempt]}]}


def test_terminal_blocked_fixture_is_reported_without_a_ready_or_sc005_claim(record, capsys):
    checker.check(record, ("gpio",))
    assert "BLOCKED" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["not_run", "running", "binding", "signature", "archive", "marker",
                                     "facts", "input_bytes", "input_binding", "baseline_bytes", "text_origin"])
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
    elif failure == "marker":
        record["orders"][0]["attempts"][0]["package_record"]["gap_count"] = 0
    elif failure == "facts":
        record["packages"]["gpio"]["package_snapshot"]["texts"]["prompt"]["cover"]["text"] = "tampered"
    elif failure == "input_bytes":
        (Path(record["orders"][0]["attempts"][0]["workspace"]) / "inputs/owner.txt").write_text("tampered")
    elif failure == "input_binding":
        record["orders"][0]["attempts"][0]["inputs"] = []
    elif failure == "baseline_bytes":
        Path(record["orders"][0]["attempts"][0]["baselines"][0]["path"]).write_text("tampered")
    else:
        record["packages"]["gpio"]["prompt_origins"][0]["from"] = "template:wrong"
    with pytest.raises(AssertionError):
        checker.check(record, ("gpio",))
