"""CAPA-241 (owner 2026-11-11 narrow guard, SWE.2 stage): the SPI LL SWE.2 continuation of L41P was refused
RESUME_CONTRACT_OR_RUNTIME_CHANGED because the contract hashes the whole peripheral profile and F015-T065 added two HAL-only
fields (hal.time_base, hal.host_instance) to spi.yaml. An LL continuation accepts a contract difference that is only the
profile hash when the two profile files (old one read from git at the source run's revision) are identical outside their
hal: section. Any other contract difference, or a non-LL order, still refuses."""
import subprocess

import pytest
from forge_factory.brownfield import resume as R
from forge_factory.common import sha256_bytes

BASE = "id: spi\nname: SPI\nll:\n  header: stm32n6xx_ll_spi.h\nhal:\n  header: stm32n6xx_hal_spi.h\n"


def repo(tmp_path, new_text):
    r = tmp_path / "repo"
    (r / "config/factory/peripherals").mkdir(parents=True)
    p = r / "config/factory/peripherals/spi.yaml"
    g = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True, text=True).stdout.strip()  # noqa: E731
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    g("config", "user.email", "t@example.invalid"); g("config", "user.name", "t")
    p.write_text(BASE); g("add", "."); g("commit", "-qm", "old")
    old_rev = g("rev-parse", "HEAD")
    p.write_text(new_text); g("commit", "-qam", "new")
    return r, old_rev, sha256_bytes(BASE.encode()), sha256_bytes(new_text.encode())


def man(sha, layer="LL", extra=None):
    return {"peripheral": "spi", "layer": layer, "peripheral_profile_sha256": sha, "target": {"core": "cm55"}, **(extra or {})}


def test_a_hal_only_profile_change_is_accepted_for_an_ll_order(tmp_path, monkeypatch):
    r, old_rev, a, b = repo(tmp_path, BASE + "  time_base: HAL_GetTick\n  host_instance: SPI1\n")
    monkeypatch.setattr(R, "REPO_ROOT", r)
    ch = R.profile_hal_only_change(man(a), man(b), old_rev)
    assert ch["field"] == "peripheral_profile_sha256" and ch["from"] == a and ch["to"] == b and "CAPA-241" in ch["rule"]


def test_other_profile_contract_or_layer_changes_are_refused(tmp_path, monkeypatch):
    r, old_rev, a, b = repo(tmp_path, BASE.replace("stm32n6xx_ll_spi.h", "other_ll.h"))
    monkeypatch.setattr(R, "REPO_ROOT", r)
    assert R.profile_hal_only_change(man(a), man(b), old_rev) is None            # the LL part of the profile changed
    r2, old2, a2, b2 = repo(tmp_path / "x", BASE + "  host_instance: SPI1\n")
    monkeypatch.setattr(R, "REPO_ROOT", r2)
    assert R.profile_hal_only_change(man(a2, "HAL"), man(b2, "HAL"), old2) is None  # not an LL order
    assert R.profile_hal_only_change(man(a2), man(b2, extra={"target": {"core": "other"}}), old2) is None
    assert R.profile_hal_only_change(man("f" * 64), man(b2), old2) is None         # recorded hash is not that file


def test_runtime_change_accepts_only_the_recorded_profile_contract_change():
    ida = {"schema": "s", "contract_sha256": "c" * 64, "limits": {}, "runtime": {"factory_assets_sha256": "a"}}
    idb = {**ida, "contract_sha256": "d" * 64, "runtime": {"factory_assets_sha256": "b"}}
    rev_a, rev_b = {"commit": "1" * 40, "dirty": False}, {"commit": "2" * 40, "dirty": False}
    with pytest.raises(R.ResumeRefused, match="RESUME_CONTRACT_OR_RUNTIME_CHANGED"):
        R.runtime_change(ida, idb, rev_a, rev_b)
    ch = R.runtime_change(ida, idb, rev_a, rev_b, profile_change={"field": "peripheral_profile_sha256"})
    assert ch["contract_change"]["field"] == "peripheral_profile_sha256"
