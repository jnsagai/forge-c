"""LRTX-T025: deployment preservation check against the T003 snapshot, and the profile rollback plan (dry run)."""
from pathlib import Path

from forge_factory.common import sha256_file
from forge_factory.lrtx import hostcheck
from forge_factory.lrtx import profile as lp


def _snap(tmp_path: Path) -> dict:
    dr = tmp_path / "forge-c"
    for wo, body in (("WO-A", b"a"), ("WO-B", b"b")):
        (dr / "archives" / wo).mkdir(parents=True)
        (dr / "archives" / wo / f"{wo}.zip").write_bytes(body)
    rows = [{"work_order": wo, "archive": f"{wo}.zip", "original_sha256": sha256_file(dr / "archives" / wo / f"{wo}.zip")}
            for wo in ("WO-A", "WO-B")]
    return {"data_root": str(dr), "archives": {"source": str(dr / "archives")}, "archive_rows": rows,
            "checkouts": [{"path": str(tmp_path / "checkout"), "head": "x"}]}


def test_archives_missing_changed_and_profile_archives_are_detected(tmp_path):
    snap = _snap(tmp_path)
    assert hostcheck.archives(snap)["ok"]
    src = Path(snap["archives"]["source"])
    (src / "WO-A/WO-A.zip").write_bytes(b"tampered")
    (src / "WO-B/WO-B.zip").unlink()
    (src / "WO-X-lrtx9").mkdir()
    r = hostcheck.archives(snap)
    assert (r["changed"], r["missing"], r["profile_archives_in_deployment"], r["ok"]) == (["WO-A"], ["WO-B"],
                                                                                         ["WO-X-lrtx9"], False)


def test_deployment_state_with_a_profile_work_order_fails(tmp_path):
    dr = tmp_path / "forge-c"
    assert hostcheck.deployment_state(dr)["ok"]
    (dr / "state/workorders/WO-1-lrtx3").mkdir(parents=True)
    assert hostcheck.deployment_state(dr) == {"profile_work_orders_in_deployment_state": ["WO-1-lrtx3"], "ok": False}


def test_rollback_plan_never_removes_a_deployment_root(tmp_path, monkeypatch):
    snap = _snap(tmp_path)
    prof = lp.load("local-rtx-v1")
    monkeypatch.setenv(prof["deployment"]["root_env"], str(tmp_path / "forge-c-lrtx"))
    ok = hostcheck.rollback_plan(prof, snap, [tmp_path / "forge-c/repos/forge-c-run-lrtx1"], None)
    assert ok["ok"] and ok["dry_run"] and ok["conflicts"] == []
    bad = hostcheck.rollback_plan(prof, snap, [tmp_path / "forge-c"], None)  # would delete the whole data root
    assert not bad["ok"] and bad["conflicts"]
    monkeypatch.setenv(prof["deployment"]["root_env"], str(tmp_path / "forge-c/state/x"))  # root inside state
    assert not hostcheck.rollback_plan(prof, snap, [], None)["ok"]


def test_rollback_lists_every_profile_run_worktree_and_no_main_line_run(tmp_path):
    import subprocess

    def git(*a, cwd):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd, check=True,
                       capture_output=True)

    dep = tmp_path / "forge-c"
    dep.mkdir()
    git("init", "-q", cwd=dep)
    (dep / "a.txt").write_text("a")
    git("add", ".", cwd=dep)
    git("commit", "-qm", "A", cwd=dep)
    old = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dep, capture_output=True, text=True).stdout.strip()
    (dep / hostcheck.PROFILE_FILE).parent.mkdir(parents=True)
    (dep / hostcheck.PROFILE_FILE).write_text("id: local-rtx-v1\n")
    git("add", ".", cwd=dep)
    git("commit", "-qm", "B (merged profile)", cwd=dep)
    repos = tmp_path / "repos"
    for name in ("forge-c-run-t023", "forge-c-run-rc1", "forge-c-run-main"):
        git("clone", "-q", str(dep), str(repos / name), cwd=tmp_path)
    git("checkout", "-q", old, cwd=repos / "forge-c-run-rc1")  # main-line run from before the profile
    (repos / "forge-c-run-t023/x.txt").write_text("x")  # a profile measurement worktree on the feature line
    git("add", ".", cwd=repos / "forge-c-run-t023")
    git("commit", "-qm", "C", cwd=repos / "forge-c-run-t023")
    snap = {"checkouts": [{"path": str(dep), "head": old}]}
    assert hostcheck.profile_worktrees(repos / "forge-c-010", snap) == [repos / "forge-c-run-t023"]
