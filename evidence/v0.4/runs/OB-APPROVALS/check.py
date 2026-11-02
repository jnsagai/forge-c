"""Verify the four owner-signed packages and the immutable owner-decision copies."""
from pathlib import Path

from forge_factory.onboarding import onboarding_dir
from forge_factory.onboarding.approval import ALLOWED_SIGNERS, signature_valid, verify

for key in ("0010e-st-cube-gpio-hal-ob", "0011e-st-cube-spi-hal-ob", "0012e-st-cube-usart-hal-ob",
            "0013e-st-cube-tim-hal-ob"):
    root = onboarding_dir(key)
    result = verify(root)
    assert result["code"] == "APPROVAL_OK", result
    approval = result["approval"]
    copy = Path("evidence/easa/owner-decisions/onboarding") / approval["approval_id"] / "approval.json"
    for suffix in ("", ".sig"):
        assert Path(str(copy) + suffix).read_bytes() == (root / ("onboarding/approval.json" + suffix)).read_bytes()
    assert signature_valid(copy, approval["decided_by"], ALLOWED_SIGNERS)
    if "usart" in key:
        assert approval["assumption_confirmations"] == [{"id": "ASM-HAL-RCCEX-GETPERIPHCLKFREQ", "value": 64000000}]
    print(key, "APPROVAL_OK", approval["approval_id"], approval["package_sha256"])
