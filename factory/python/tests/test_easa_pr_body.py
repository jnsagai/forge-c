"""EASA-T072 / AT-072: the PR #3 body keeps the owner's text, asserts no conformance/approval and stays a review PR."""
import re
from pathlib import Path

from forge_factory.assurance.normative import compliance_assertions
from forge_factory.common import REPO_ROOT

BODY = REPO_ROOT / "evidence/easa/pr/pr3-body-2026-10-17.md"


def test_at072_pr_body_has_no_conformance_claim_and_no_auto_merge():
    text = BODY.read_text()
    assert compliance_assertions(text) == []
    assert text.startswith("## Overview") and "### Stacked PR note" in text          # owner's sections kept
    assert "Do not merge automatically" in text and "not a safety sign-off" in text
    # a 100% figure may appear only as a negated disclaimer (the owner's text: '... are not attributed to ISO 26262')
    assert all(re.search(r"\b(not|no|never)\b", ln) for ln in text.splitlines() if "100%" in ln)


def test_at072_a_body_asserting_conformance_is_detected():
    assert compliance_assertions("The driver is ISO 26262 compliant and ASPICE level 2 certified.")
    assert Path(BODY).is_file()
