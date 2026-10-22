"""Feature 010 P0: host preservation snapshot helpers (LRTX-T003) and the frozen compatibility fixtures (LRTX-T004)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import compat, hostsnap

FIXTURE = REPO_ROOT / "tests/compat/lrtx/baseline-86f1f40.json.gz"
RCC_RM = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/RM0486-rev4-ch14-rcc.md"  # owner input, git-ignored


def test_secret_like_environment_names_are_redacted_and_others_dropped():
    env = {"FORGE_STATE_DIR": "/s", "FORGE_DASHBOARD_TOKEN": "x", "OLLAMA_KV_CACHE_TYPE": "q8_0", "HOME": "/h",
           "DEEPSEEK_API_KEY": "k", "FORGE_GATEWAY_PRICE_OUT_PER_M": "1"}
    out = hostsnap.redact_env(env)
    assert out == {"FORGE_DASHBOARD_TOKEN": "<redacted>", "FORGE_GATEWAY_PRICE_OUT_PER_M": "1",
                   "FORGE_STATE_DIR": "/s", "OLLAMA_KV_CACHE_TYPE": "q8_0"}


def _archive(tmp: Path, tamper: bool = False) -> Path:
    z = tmp / "WO-X" / "forge-c-WO-X-review.zip"
    z.parent.mkdir(parents=True)
    body = b'{"status": "READY_FOR_OFFLINE_REVIEW", "gap_count": 0}'
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("manifest.json", body)
        zf.writestr("SHA256SUMS.txt", f"{hashlib.sha256(b'x' if tamper else body).hexdigest()}  manifest.json\n")
    z.with_name(z.name + ".sha256").write_text(f"{hashlib.sha256(z.read_bytes()).hexdigest()}  {z.name}\n")
    return z


def test_archive_copy_is_verified_and_restored(tmp_path):
    _archive(tmp_path / "archives")
    res = hostsnap.preserve_archives(tmp_path / "archives", tmp_path / "backup")
    assert res["all_verified"] and res["archives"] == 1
    r = hostsnap.restore_check(tmp_path / "backup/WO-X/forge-c-WO-X-review.zip")
    assert r["status"] == "PASS" and r["package_status"] == "READY_FOR_OFFLINE_REVIEW"


def test_member_hash_mismatch_fails_preservation(tmp_path):
    _archive(tmp_path / "archives", tamper=True)
    res = hostsnap.preserve_archives(tmp_path / "archives", tmp_path / "backup")
    assert not res["all_verified"] and res["rows"][0]["member_mismatches"] == ["manifest.json"]


def test_backup_inside_a_repository_is_refused(tmp_path, monkeypatch):
    for k, d in (("FORGE_DATA_ROOT", "d"), ("FORGE_ARCHIVE_DIR", "d/archives"), ("FORGE_STATE_DIR", "d/state")):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(k, str(tmp_path / d))
    with pytest.raises(ValueError, match="BACKUP_INSIDE_DEPLOYMENT_OR_REPO"):
        hostsnap.snapshot(REPO_ROOT / "build" / "lrtx-backup")


def test_compare_reports_every_changed_field():
    a = {"x/default": {"graph": "g", "nodes": {}}}
    assert compat.compare(a, {"x/default": {"graph": "g2", "nodes": {}}}) == ["x/default:graph"]
    assert compat.compare(a, {}) == ["x/default: missing"]


def test_fixture_covers_existing_workflow_and_provider_combinations():
    data = compat.load(FIXTURE)
    assert set(data) == {f"{e}/{v}" for e, _ in compat.CASES for v in compat.VARIANTS}
    both = data["0009b-iwdg-hal/acp_both"]
    assert both["native_agent_nodes"] == [] and both["acp_converted"]["inspectors"]
    assert data["0002a-arm_55_rcc_ll/default"]["acp_converted"] == {}
    assert data["0008a-rcc-ll-delivered/default"]["nodes"]["swe3_fix_author"]
    assert "/media/" not in json.dumps(data) and "/home/" not in json.dumps(data)


@pytest.mark.skipif(not RCC_RM.is_file(), reason="owner RM0486 inputs (git-ignored) not present in this checkout")
def test_current_tree_reproduces_the_preserved_baseline_fixtures():
    out = subprocess.run([sys.executable, str(Path(compat.__file__)), "--src", str(REPO_ROOT), "--compare",
                          str(FIXTURE)], capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
