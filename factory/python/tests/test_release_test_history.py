"""Synthetic package fixtures preserve failed test history; these are not model trials."""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from forge_factory.inspection.defects import INTEGRITY_LOG, SNAPSHOTS, code_hash
from forge_factory.release import finalize as F
from test_m7_governance_release import complete_workspace


@pytest.fixture
def history_ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "archives"))
    ws = tmp_path / "ws"
    ws.mkdir()
    complete_workspace(ws)
    after = (ws / "software/tests/unit/t.c").read_bytes()
    before = b"/* synthetic earlier metadata failure, not a runtime repair */\n" + after
    records = []
    snapshots = ws / SNAPSHOTS
    snapshots.mkdir(parents=True)
    for number, status, data in ((1, "FAIL", before), (2, "PASS", after)):
        digest = hashlib.sha256(data).hexdigest()
        (snapshots / digest).write_bytes(data)
        records.append({"ts_utc": f"2026-10-30T00:00:0{number}Z", "phase": "SWE.4", "op": "run_unit",
                        "status": status, "code_sha": code_hash(ws),
                        "files": {"software/tests/unit/t.c": digest}, "assert_failed": []})
    (ws / INTEGRITY_LOG).parent.mkdir(exist_ok=True)
    (ws / INTEGRITY_LOG).write_text("".join(json.dumps(r) + "\n" for r in records))
    return ws, records


def test_final_package_retains_failed_and_passed_test_versions(history_ws):
    ws, records = history_ws
    raw_log = (ws / INTEGRITY_LOG).read_bytes()
    result = F.finalize(ws, "WO-HISTORY-FIXTURE")
    assert result["package_status"] == "READY_FOR_OFFLINE_REVIEW", result["gaps"]
    with zipfile.ZipFile(result["archive"]) as archive:
        root = "evidence/verification/test-history/"
        assert archive.read(root + "integrity.jsonl") == raw_log
        for record in records:
            digest = record["files"]["software/tests/unit/t.c"]
            assert hashlib.sha256(archive.read(root + "snapshots/" + digest)).hexdigest() == digest
        index = json.loads(archive.read(root + "index.json"))
        assert index["status"] == "COMPLETE" and index["snapshots"] == 2
        assert index["records"] == 2
    assert F.verify_archive(Path(result["archive"]))["integrity"] == "PASS"


@pytest.mark.parametrize("fault", ["missing", "corrupt", "symlink", "malformed_log", "invalid_digest"])
def test_incomplete_or_unsafe_test_history_blocks_without_losing_package(history_ws, tmp_path, fault):
    ws, records = history_ws
    source = ws / SNAPSHOTS / records[0]["files"]["software/tests/unit/t.c"]
    secret = b"DO_NOT_COPY_OUTSIDE_HISTORY_FIXTURE"
    if fault == "missing":
        source.unlink()
    elif fault == "corrupt":
        source.write_bytes(b"changed after the recorded hash")
    elif fault == "symlink":
        external = tmp_path / "external-fixture"
        external.write_bytes(secret)
        source.unlink()
        source.symlink_to(external)
    elif fault == "malformed_log":
        with (ws / INTEGRITY_LOG).open("a") as log:
            log.write("incomplete json record\n")
    else:
        records[0]["files"]["software/tests/unit/t.c"] = "../../external-fixture"
        (ws / INTEGRITY_LOG).write_text("".join(json.dumps(r) + "\n" for r in records))
    result = F.finalize(ws, "WO-HISTORY-FAULT-FIXTURE")
    assert result["package_status"] == "BLOCKED"
    assert "unresolved_finding:TEST_HISTORY_INTEGRITY" in result["gaps"]
    with zipfile.ZipFile(result["archive"]) as archive:
        index = json.loads(archive.read("evidence/verification/test-history/index.json"))
        assert index["status"] == "INCOMPLETE" and index["issues"]
        assert all(secret not in archive.read(name) for name in archive.namelist())
    assert F.verify_archive(Path(result["archive"]))["integrity"] == "PASS"
