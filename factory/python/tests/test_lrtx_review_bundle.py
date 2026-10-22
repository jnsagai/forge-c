"""LRTX-T025: the offline review bundle is deterministic, complete per its file list and copies task states."""
import hashlib
import zipfile

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import review_bundle as RB


def test_file_list_and_task_states_come_from_the_repository():
    fl = RB.files(REPO_ROOT)
    assert "specs/010-local-rtx-optimization/tasks.md" in fl and "LOCAL_RTX_START.md" in fl
    assert any(f.startswith("evidence/v0.4/runs/LRTX-T004/") for f in fl)
    ts = {t["task"]: t for t in RB.tasks(REPO_ROOT)}
    assert len(ts) == 25 and ts["LRTX-T003"]["ticked"] and ts["LRTX-T003"]["evidence_status"] == "PASS"
    assert not ts["LRTX-T024"]["ticked"]


def test_bundle_is_byte_identical_for_the_same_revision(tmp_path, monkeypatch):
    if RB._git("status", "--porcelain", "--", *RB.INCLUDE, "evidence/v0.4/runs", "evidence/cre/decisions",
               repo=REPO_ROOT):
        pytest.skip("feature files have uncommitted changes (the bundle refuses them by design)")
    a = RB.build(tmp_path / "a")
    b = RB.build(tmp_path / "b")
    assert a["sha256"] == b["sha256"]
    with zipfile.ZipFile(a["zip"]) as zf:
        names = zf.namelist()
        sums = dict(reversed(x.split("  ", 1)) for x in zf.read("SHA256SUMS.txt").decode().splitlines())
        for f, h in sums.items():
            assert hashlib.sha256(zf.read(f"files/{f}")).hexdigest() == h
    assert {"README.md", "MANIFEST.json", "SHA256SUMS.txt"} <= set(names)
    assert "not a release" in zipfile.ZipFile(a["zip"]).read("README.md").decode()


def test_out_dir_inside_the_repository_is_refused():
    with pytest.raises(SystemExit, match="OUT_DIR_INSIDE_REPOSITORY"):
        RB.main(["--out-dir", str(REPO_ROOT / "build/x")])


def test_task_states_follow_the_evidence_each_tick_cites(tmp_path):
    import json

    runs = tmp_path / "evidence/v0.4/runs"
    for name, st in (("LRTX-T016-REPLAY", "PASS"), ("LRTX-T016-SWE2", "PASS"), ("LRTX-T021", "FAIL")):
        (runs / name).mkdir(parents=True)
        (runs / name / "latest.json").write_text(json.dumps({"status": st}))
    (tmp_path / RB.FEATURE).mkdir(parents=True)
    (tmp_path / RB.FEATURE / "tasks.md").write_text(
        "- [x] LRTX-T001 Record the SHA. Reference: `baseline.json` and ADR-0013.\n"
        "- [X] LRTX-T016 Trials. ✅ Evidence: `evidence/v0.4/runs/LRTX-T016-REPLAY/latest.json`, "
        "`evidence/v0.4/runs/LRTX-T016-SWE2/latest.json`\n"
        "- [X] LRTX-T021 Seeded. ✅ Evidence: `evidence/v0.4/runs/LRTX-T021/latest.json`\n"
        "- [ ] LRTX-T024 Campaign.\n")
    ts = {t["task"]: t for t in RB.tasks(tmp_path)}
    assert ts["LRTX-T016"]["evidence_status"] == "PASS" and len(ts["LRTX-T016"]["evidence"]) == 2
    assert ts["LRTX-T001"]["evidence_status"] == "NO_EVIDENCE_RUN (cites baseline.json)"
    assert ts["LRTX-T021"]["evidence_status"] == "NOT_PASS"  # a cited record that did not pass is never PASS
    assert not ts["LRTX-T024"]["ticked"] and ts["LRTX-T024"]["evidence_status"] == "NO_EVIDENCE_RUN"
