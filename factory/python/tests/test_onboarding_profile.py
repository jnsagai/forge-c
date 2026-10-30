"""Feature 016 OB-T023 / OB-T029: an onboarding work order prepares only from an owner-approved package; then the
derived profile drives the work order (manifest `onboarded:<WO>`, layer helpers, host device) and its intake uses the
derived file map. Hand-onboarded work orders keep their hand profile. A throwaway test key signs - never the owner's."""
import json
import shutil
import subprocess

import pytest

from forge_factory import onboarding as OB
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT
from forge_factory.onboarding import approval as A
from forge_factory.peripheral import load
from onboarding_util import need_inputs

EX = REPO_ROOT / "examples/0012e-st-cube-usart-hal-ob"


@pytest.fixture
def owner_key(tmp_path, monkeypatch):
    if not shutil.which("ssh-keygen"):
        pytest.skip("ssh-keygen not installed")
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    allowed = tmp_path / "allowed"
    allowed.write_text(f"tester {key.with_suffix('.pub').read_text()}")
    monkeypatch.setattr(A, "ALLOWED_SIGNERS", allowed)
    return key


def _sign(root, key, hz=64000000):
    A.summary(root)
    a = json.loads((root / A.TEMPLATE).read_text())
    a.update(approval_id="OA-2026-10-27-01", decided_by="tester", decided_on="2026-10-27")
    for c in a["assumption_confirmations"]:
        c["value"] = hz
    (root / A.APPROVAL).write_text(json.dumps(a))
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", A.NAMESPACE, str(root / A.APPROVAL)],
                   check=True)


def test_unapproved_onboarding_work_order_is_refused(tmp_path, monkeypatch):
    need_inputs()
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    with pytest.raises(OB.OnboardingNotApproved, match="APPROVAL_MISSING"):   # prepare derives, then refuses
        WO.prepare(EX, "WO-OB-U")
    assert (OB.onboarding_dir(EX.name) / "onboarding/package.json").is_file()
    assert OB.intake_check(REPO_ROOT, {"example": "examples/0012e-st-cube-usart-hal-ob"}).startswith("APPROVAL_MISSING")
    assert OB.intake_check(REPO_ROOT, {"example": "examples/0014d-st-cube-crc-hal"}) is None   # hand-onboarded


def test_approved_package_drives_the_work_order(tmp_path, monkeypatch, owner_key):
    need_inputs()
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    load.cache_clear()
    pkg = OB.derive(EX)
    root = OB.onboarding_dir(EX.name)
    _sign(root, owner_key, 48000000)
    ws, m = WO.prepare(EX, "WO-OB-U")
    assert m["peripheral"] == f"onboarded:{EX.name}" and m["onboarding"]["sha256"] == pkg["sha256"]
    assert OB.intake_check(REPO_ROOT, {"example": "examples/0012e-st-cube-usart-hal-ob"}) is None  # AFO admits it
    assert m["onboarding"]["approval_id"] == "OA-2026-10-27-01" and m.get("hal_standalone") is True
    from forge_factory.brownfield import cmsis
    from forge_factory.layer import profile

    prof = profile(ws)
    assert prof["derived_from"]["package_sha256"] == pkg["sha256"] and prof["hal"]["clock_stub"]["hz"] == 48000000
    assert prof["hal"]["host_instance"] == "USART1" and prof["hal"]["time_base"] == "HAL_GetTick"
    assert "#define USART1_S (&forge_host_usart)" in cmsis.host_header(ws)
    intake = json.loads((tmp_path / "state/workorders/WO-OB-U/delivered/intake.json").read_text())
    assert intake["status"] == "ACCEPTED" and intake["build_check"]["status"] == "PASS"
    conf = [r for r in intake["files"] if r["path"].endswith("stm32n6xx_hal_conf.h")][0]
    assert conf["configured_from"]["hal_modules"] == ["UART", "RCC"]


def test_an_input_change_voids_the_approval(tmp_path, monkeypatch, owner_key):
    need_inputs()
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    OB.derive(EX)
    root = OB.onboarding_dir(EX.name)
    _sign(root, owner_key)
    assert A.verify(root)["code"] == "APPROVAL_OK"
    pkg = json.loads((root / "onboarding/package.json").read_text())
    pkg["inputs"][0]["sha256"] = "0" * 64                                # a stale record from another input set
    pkg["sha256"] = OB.facts.canonical_hash(pkg)
    (root / "onboarding/package.json").write_text(json.dumps(pkg))
    OB.derive(EX)                                            # re-derivation: hash differs -> void
    assert A.verify(root)["code"] == "APPROVAL_MISSING"
    assert any((root / "onboarding/void").iterdir())


def test_hand_onboarded_work_order_keeps_its_hand_profile(tmp_path, monkeypatch):
    need_inputs()
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, m = WO.prepare(REPO_ROOT / "examples/0014d-st-cube-crc-hal", "WO-H")
    assert m["peripheral"] == "crc" and "onboarding" not in m
    from forge_factory.layer import profile

    assert "derived_from" not in profile(ws)
