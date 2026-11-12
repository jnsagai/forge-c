"""Read-only terminal-result/hash/privacy-pattern replay; no live telemetry claim."""
import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "factory/python"))
from forge_factory.events import redact  # noqa: E402


def raw(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        assert stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "publication must be a regular file"
        data = stream.read(131073)
    assert len(data) <= 131072, "publication file bound"
    return data


def verify(root):
    summary = json.loads(raw(root / "summary.json"))
    report = json.loads(raw(root / "publication-recheck-20261027.json"))
    assert report["native_terminal_ref"]["path"] == "terminal-recheck-20261027.json"
    terminal_path = root / report["native_terminal_ref"]["path"]
    terminal_bytes = raw(terminal_path)
    assert hashlib.sha256(terminal_bytes).hexdigest() == report["native_terminal_ref"]["sha256"]
    terminal = json.loads(terminal_bytes)
    assert terminal["source_summary_sha256"] == summary["source_summary_sha256"]
    assert terminal["matching_running_artifacts"] == []
    assert terminal["status_text"].endswith("end 2026-10-27T08:19:24Z exit=0\n")
    assert report["live_status_scorecard_capture"] == "NOT_RUN_JOB_ALREADY_TERMINAL"
    assert report["DA_T018"] == "NOT_RUN_UNTICKED"
    by_run = {row["run"]: row for row in summary["rows"]}
    assert len(by_run) == len(terminal["rows"]) == 3
    for row in terminal["rows"]:
        old = by_run[row["run"]]
        assert row["artifact_facts"] == old["artifact_facts"]
        assert row["package_status"] == old["package_status"] == "BLOCKED"
        assert row["gap_count"] == old["gap_count"] == 59
        assert row["archive_sha256"] == old["package"]["archive_sha256"]
        assert old["classification"]["blocked_phase"] == "SWE.1"
    assert sum(row["metrics"]["calls"]["count"] for row in summary["rows"]) == summary["requests"] == 76
    assert sum(row["metrics"]["calls"]["prompt_tokens"]["sum"] for row in summary["rows"]) == summary["prompt_tokens"] == 324810
    assert sum(row["metrics"]["calls"]["output_tokens"] for row in summary["rows"]) == summary["output_tokens"] == 51810
    assert hashlib.sha256(Path(redact.__file__).read_bytes()).hexdigest() == report["privacy_scan"]["redactor_sha256"]
    names = {entry["path"] for entry in report["privacy_scan"]["files"]}
    assert names == {"README.md", "summary.json", "author-diagnostics.json"}
    assert len(report["privacy_scan"]["files"]) == 3
    for entry in report["privacy_scan"]["files"]:
        data = raw(root / entry["path"])
        assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert redact.redact_text(data.decode())[1] is False
        if entry["path"].endswith(".json"):
            assert redact.redact_obj(json.loads(data))[1] is False
    assert redact.redact_obj(terminal)[1] is False
    return {"status": "PASS_TERMINAL_PUBLICATION_ONLY", "ready": 0, "blocked": 3,
            "DA_T018": "NOT_RUN_UNTICKED", "new_model_requests": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    print(json.dumps(verify(parser.parse_args().root), sort_keys=True))
