"""Feature 016 OB-T026: the owner's signed approval of an onboarding package. A throwaway test key and test
allowed-signers file are used - never the owner's key; the factory never signs an approval."""
import json
import shutil
import subprocess

import pytest
from forge_factory.onboarding import approval as A
from forge_factory.onboarding import facts as F


@pytest.fixture
def signer(tmp_path):
    if not shutil.which("ssh-keygen"):
        pytest.skip("ssh-keygen not installed")
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    allowed = tmp_path / "allowed"
    allowed.write_text(f"tester {key.with_suffix('.pub').read_text()}")
    return key, allowed


def _pkg(root, facts=None, asm=None):
    facts = facts or [F.derived("instance", "USART1", "m", F.Source("workorder", "target.instance"))]
    p = F.assemble("WO-T", [{"path": "inputs/a.md", "role": "rm", "sha256": "1" * 64}], "abcdef1", "HAL_STANDALONE",
                   facts, [], asm or [], {"derived_from": {}}, {})
    F.write_package(root, p)
    return p


def _approve(root, key, mutate=None, namespace=A.NAMESPACE):
    A.summary(root)
    a = json.loads((root / A.TEMPLATE).read_text())
    a.update(approval_id="OA-2026-10-27-01", decided_by="tester", decided_on="2026-10-27")
    for c in a["assumption_confirmations"]:
        c["value"] = 64000000
    for c in a["conflict_resolutions"]:
        c.update(chosen_value="0x52001000", reason="RM is authoritative")
    if mutate:
        mutate(a)
    (root / A.APPROVAL).write_text(json.dumps(a))
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", namespace, str(root / A.APPROVAL)],
                   check=True)


ASM = [F.Assumption("ASM-CLOCK", "HAL_RCCEx_GetPeriphCLKFreq", "not delivered", ["USART_BRR"])]
CONFLICT = [F.agree("base_address", "m", "which?", F.Source("file", "h", line=1, value="0x52001000"),
                    F.Source("doc", "mm", page=180, value="0x42001000")),
            F.not_derived("mm_page", "m", "page?")]


def test_a_complete_signed_approval_verifies(tmp_path, signer):
    key, allowed = signer
    _pkg(tmp_path, CONFLICT, ASM)
    _approve(tmp_path, key)
    r = A.verify(tmp_path, allowed)
    assert r["code"] == "APPROVAL_OK", r
    assert (tmp_path / A.SUMMARY).read_text().count("Question") == 2


def test_shipped_signer_permissions_allow_both_factory_namespaces(signer):
    from repro_onboarding_signer_namespace import probe

    assert probe() == {A.NAMESPACE: True, "forge-afo-authorization": True, "forge-unrelated": False}


@pytest.mark.parametrize("mutate,code", [
    (lambda a: a["assumption_confirmations"][0].update(value=None), "APPROVAL_INCOMPLETE:assumption"),
    (lambda a: a["conflict_resolutions"][0].update(chosen_value=None), "APPROVAL_INCOMPLETE:conflict"),
    (lambda a: a.update(accepted_gaps=[]), "APPROVAL_INCOMPLETE:gap_not_accepted"),
    (lambda a: a.update(package_sha256="0" * 64), "APPROVAL_STALE"),
    (lambda a: a.update(decision="REJECTED", reason="base address wrong"), "APPROVAL_REJECTED"),
    (lambda a: a.update(decided_by="someone-else"), "APPROVAL_BAD_SIGNATURE")])
def test_incomplete_stale_rejected_or_foreign_approvals_are_refused(tmp_path, signer, mutate, code):
    key, allowed = signer
    _pkg(tmp_path, CONFLICT, ASM)
    _approve(tmp_path, key, mutate)
    assert A.verify(tmp_path, allowed)["code"] == code


def test_wrong_namespace_or_edited_after_signing_is_a_bad_signature(tmp_path, signer):
    key, allowed = signer
    _pkg(tmp_path)
    _approve(tmp_path, key, namespace="forge-afo-authorization")
    assert A.verify(tmp_path, allowed)["code"] == "APPROVAL_BAD_SIGNATURE"
    _approve(tmp_path, key)
    a = json.loads((tmp_path / A.APPROVAL).read_text())
    a["decided_on"] = "2026-10-28"
    (tmp_path / A.APPROVAL).write_text(json.dumps(a))
    assert A.verify(tmp_path, allowed)["code"] == "APPROVAL_BAD_SIGNATURE"


def test_missing_input_blocks_and_invalidation_keeps_the_old_approval(tmp_path, signer):
    key, allowed = signer
    p = F.assemble("WO-T", [{"path": "inputs/a.md", "role": "rm", "sha256": "1" * 64}], "abcdef1", "LL", [], [], [],
                   {"derived_from": {}}, {}, [("Inc/x.h", "build")])
    F.write_package(tmp_path, p)
    _approve(tmp_path, key)
    assert A.verify(tmp_path, allowed)["code"] == "APPROVAL_INCOMPLETE:blocking_gap"
    assert A.invalidate(tmp_path, "input changed") and not (tmp_path / A.APPROVAL).exists()
    void = next((tmp_path / "onboarding/void").iterdir())
    assert (void / "approval.json").is_file() and (void / "approval.json.sig").is_file()
    assert A.verify(tmp_path, allowed)["code"] == "APPROVAL_MISSING"
