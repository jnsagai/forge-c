"""Feature 018: the versioned IQ/SQ criteria are exactly the pinned guideline's tables."""
import re

import yaml
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.lrtx import swe1_quality as Q


def _table(text, prefix):
    rows = []
    for line in text.splitlines():
        m = re.match(rf"^\| ({prefix}-\d\d) \| \*\*(.+?)\*\* \| (.+?) \|", line)
        if m:
            rows.append({"id": m.group(1), "property": m.group(2), "criterion": m.group(3).strip()})
    return rows


def test_checklist_is_derived_from_the_pinned_guideline():
    cl = Q.quality_checklist()
    g = REPO_ROOT / cl["guideline"]["path"]
    assert sha256_file(g) == cl["guideline"]["sha256"]
    text = g.read_text()
    assert cl["individual"] == _table(text, "IQ") and len(cl["individual"]) == 12
    assert cl["set"] == _table(text, "SQ") and len(cl["set"]) == 10
    assert cl["rework_severities"] == ["BLOCKING", "CORRECTABLE"] and cl["phase1"]["rounds"] >= 1


def test_a_changed_guideline_refuses_the_checklist(tmp_path):
    for rel in (Q.CHECKLIST, "docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes((REPO_ROOT / rel).read_bytes())
    Q.quality_checklist(tmp_path)
    p = tmp_path / "docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md"
    p.write_text(p.read_text() + "\nedited\n")
    try:
        Q.quality_checklist(tmp_path)
        raise AssertionError("not refused")
    except ValueError as exc:
        assert str(exc) == "QUALITY_GUIDELINE_CHANGED"
    assert yaml.safe_load((REPO_ROOT / Q.CHECKLIST).read_text())["schema"] == "forge-c/swe1-quality-checklist/1"
