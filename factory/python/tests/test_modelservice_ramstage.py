"""Feature 017 T032: RAM staging of model files (FR-031, research R3c)."""
from __future__ import annotations

import hashlib
import os
import stat

import pytest
from model_tier import ramstage as R

GIB_KB = 1024 * 1024


def meminfo(tmp_path, avail_gib: float):
    p = tmp_path / "meminfo"
    p.write_text(f"MemTotal:       {128 * GIB_KB} kB\nMemFree:        1000 kB\nMemAvailable:   {int(avail_gib * GIB_KB)} kB\n")
    return p


def blob(tmp_path, name="model.gguf", data=b"weights" * 1000):
    src = tmp_path / "disk" / name
    src.parent.mkdir(exist_ok=True)
    src.write_bytes(data)
    return src, hashlib.sha256(data).hexdigest()


@pytest.fixture
def rs(tmp_path):
    return R.RamStage(tmp_path / "shm" / "forge-model-tier", budget_gib=80, reserve_gib=24, meminfo=meminfo(tmp_path, 120),
                      residency=lambda p: 1.0)


def test_stage_copies_and_verifies(rs, tmp_path):
    src, sha = blob(tmp_path)
    s = rs.stage("ornith", src, sha.upper())
    assert s.path == rs.stage_dir / "ornith" / "model.gguf"
    assert s.path.read_bytes() == src.read_bytes() and s.sha256 == sha and s.size == src.stat().st_size
    assert s.inode == s.path.stat().st_ino
    assert not list(s.path.parent.glob("*.part"))
    assert rs.check(s) == (True, "")
    assert rs.findings() == []


def test_wrong_hash_refused_and_cleaned(rs, tmp_path):
    src, _ = blob(tmp_path)
    with pytest.raises(R.RamStageError, match=r"^SHA256_MISMATCH:ornith"):
        rs.stage("ornith", src, "0" * 64)
    assert not [p for p in (rs.stage_dir / "ornith").iterdir()]
    assert "ornith" not in rs.staged()
    assert rs.findings()[-1]["code"] == "STAGE_REFUSED"


def test_permissions(rs, tmp_path):
    src, sha = blob(tmp_path)
    s = rs.stage("ornith", src, sha)
    assert stat.S_IMODE(rs.stage_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(s.path.parent.stat().st_mode) == 0o700
    for f in s.path.parent.iterdir():
        assert stat.S_IMODE(f.stat().st_mode) == 0o600, f.name


def test_warm_when_budget_and_reserve_allow(rs):
    assert rs.decide(37.8) == ("warm", "")
    assert rs.findings() == []


def test_budget_exhausted_goes_cold_with_finding(rs, tmp_path):
    rs.reserve("qwen36", 35)
    assert rs.decide(37.8) == ("warm", "")
    rs.reserve("other", 10)
    mode, reason = rs.decide(37.8)
    assert mode == "cold" and reason.startswith("RAM_BUDGET:")
    f = rs.findings()[-1]
    assert f["kind"] == "infrastructure" and f["code"] == "RAM_WARM_UNAVAILABLE" and f["reason"] == reason


def test_staged_files_count_against_budget(tmp_path):
    src, sha = blob(tmp_path, data=b"x" * 4096)
    rs = R.RamStage(tmp_path / "stage", budget_gib=8 * 4096 / 1024**3, reserve_gib=0, meminfo=meminfo(tmp_path, 120))
    assert rs.decide(8 * 4096 / 1024**3)[0] == "warm"
    rs.stage("a", src, sha)
    assert rs.decide(8 * 4096 / 1024**3)[0] == "cold"
    assert rs.decide(6 * 4096 / 1024**3)[0] == "warm"


def test_host_reserve_leads_to_cold(tmp_path):
    rs = R.RamStage(tmp_path / "stage", budget_gib=80, reserve_gib=24, meminfo=meminfo(tmp_path, 50))
    mode, reason = rs.decide(37.8)
    assert mode == "cold" and reason.startswith("RAM_RESERVE:")
    assert rs.findings()[-1]["code"] == "RAM_WARM_UNAVAILABLE"
    assert not (tmp_path / "stage").exists()  # deciding never stages


def test_unreadable_meminfo_is_cold(tmp_path):
    rs = R.RamStage(tmp_path / "stage", budget_gib=80, reserve_gib=24, meminfo=tmp_path / "nope")
    assert rs.decide(1) == ("cold", "MEMINFO_UNREADABLE")


def test_residency_below_threshold_not_ok(tmp_path):
    frac = {"v": 0.5}
    rs = R.RamStage(tmp_path / "stage", 80, 24, meminfo(tmp_path, 120), residency=lambda p: frac["v"])
    src, sha = blob(tmp_path)
    s = rs.stage("ornith", src, sha)
    assert rs.check(s) == (False, "NOT_RESIDENT:0.500")
    assert rs.findings()[-1] == {**rs.findings()[-1], "code": "STAGED_COPY_NOT_READY", "name": "ornith"}
    frac["v"] = 0.96
    assert rs.check(s) == (True, "")
    assert rs.check(s, min_residency=0.99)[0] is False


def test_changed_size_inode_and_missing(rs, tmp_path):
    src, sha = blob(tmp_path)
    s = rs.stage("ornith", src, sha)
    with s.path.open("ab") as f:
        f.write(b"!")
    assert rs.check(s) == (False, "CHANGED")
    s = rs.stage("ornith", src, sha)  # sidecar size no longer matches -> re-staged
    assert rs.check(s) == (True, "")
    replacement = s.path.with_name("x")
    replacement.write_bytes(s.path.read_bytes())
    os.replace(replacement, s.path)  # same size, new inode
    assert rs.check(s) == (False, "CHANGED")
    s.path.unlink()
    assert rs.check(s) == (False, "MISSING")


def test_idempotent_restage(rs, tmp_path):
    src, sha = blob(tmp_path)
    a = rs.stage("ornith", src, sha)
    mtime = a.path.stat().st_mtime_ns
    b = rs.stage("ornith", src, sha)
    assert a == b and b.path.stat().st_mtime_ns == mtime
    again = R.RamStage(rs.stage_dir, 80, 24, rs.meminfo, residency=lambda p: 1.0)  # survives a restart
    assert again.staged()["ornith"] == a
    assert again.used_gib() == pytest.approx(a.size / 1024**3)


def test_unstage_removes_only_own_files(rs, tmp_path):
    src, sha = blob(tmp_path)
    rs.stage("ornith", src, sha)
    rs.stage("other", src, sha)
    foreign = rs.stage_dir.parent / "someone-else.bin"
    foreign.write_bytes(b"keep")
    rs.unstage("ornith")
    assert not (rs.stage_dir / "ornith").exists()
    assert (rs.stage_dir / "other" / "model.gguf").exists() and foreign.read_bytes() == b"keep"
    assert "ornith" not in rs.staged() and "other" in rs.staged()
    rs.unstage("ornith")  # already gone: no error


@pytest.mark.parametrize("bad", ["..", ".", "../x", "a/b", "/etc", "", ".hidden", "a\x00b"])
def test_bad_names_refused(rs, tmp_path, bad):
    src, sha = blob(tmp_path)
    with pytest.raises(R.RamStageError, match=r"^BAD_NAME:"):
        rs.unstage(bad)
    with pytest.raises(R.RamStageError, match=r"^BAD_NAME:"):
        rs.stage(bad, src, sha)


def test_symlinked_entry_refused(rs, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_text("keep")
    rs.stage_dir.mkdir(parents=True)
    (rs.stage_dir / "evil").symlink_to(outside)
    with pytest.raises(R.RamStageError, match=r"^BAD_NAME:"):
        rs.unstage("evil")
    assert (outside / "keep").exists()


def test_real_residency(tmp_path):
    p = tmp_path / "small.bin"
    p.write_bytes(os.urandom(64 * 1024))
    p.read_bytes()
    r = R.residency(p)
    assert isinstance(r, float) and 0.0 <= r <= 1.0
    assert R.residency(tmp_path / "missing") == 0.0
