"""CRE-T002 — baseline runner records exit codes/hashes, classifies failures, restores regenerated evidence."""
import json
import subprocess
import sys

from forge_factory.reliability import baseline as B


def _repo(tmp_path):
    r = tmp_path / "repo"
    (r / "evidence").mkdir(parents=True)
    (r / "evidence/status.json").write_text('{"generated":"original"}\n')
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    subprocess.run(["git", "add", "-A"], cwd=r, check=True)
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "base"], cwd=r, check=True)
    return r


def test_failures_are_recorded_and_classified_and_regenerated_evidence_is_restored(tmp_path):
    r = _repo(tmp_path)
    regen = [sys.executable, "-c", "open('evidence/status.json','w').write('{\"generated\":\"by tests\"}')"]
    suites = [{"id": "ok", "argv": [sys.executable, "-c", "print('fine')"]},
              {"id": "regenerates", "argv": regen},
              {"id": "verify-bundle", "argv": [sys.executable, "-c", "import sys; sys.exit(1)"]}]
    rec = B.run(r, suites, r / "evidence/cre/baseline")
    by = {x["id"]: x for x in rec["results"]}
    assert by["ok"]["result"] == "PASS" and by["ok"]["tail"] == "fine" and len(by["ok"]["stdout_sha256"]) == 64
    assert by["verify-bundle"]["result"] == "KNOWN_CONSTRAINT" and by["verify-bundle"]["exit_code"] == 1
    assert rec["status"] == "PASS"  # a documented pre-existing constraint is recorded, not hidden, not a CRE failure
    assert rec["restored_regenerated_evidence"] == ["evidence/status.json"]
    assert (r / "evidence/status.json").read_text() == '{"generated":"original"}\n'
    assert json.loads((r / "evidence/cre/baseline/baseline-latest.json").read_text())["task"] == "CRE-T002"


def test_an_unexplained_failure_fails_the_baseline(tmp_path):
    r = _repo(tmp_path)
    rec = B.run(r, [{"id": "unit", "argv": [sys.executable, "-c", "raise SystemExit(3)"]}], tmp_path / "out")
    assert rec["status"] == "FAIL" and rec["results"][0]["result"] == "FAIL" and rec["results"][0]["exit_code"] == 3


def test_recorded_repository_baseline_is_complete():
    rec = json.loads((B.REPO_ROOT / "evidence/cre/baseline/baseline-latest.json").read_text())
    assert {r["id"] for r in rec["results"]} == {s["id"] for s in B.SUITES}
    assert rec["status"] == "PASS" and all(r["result"] in ("PASS", "KNOWN_CONSTRAINT") for r in rec["results"])
    assert all(len(r["stdout_sha256"]) == 64 for r in rec["results"]) and rec["tool_versions"]["python"]
