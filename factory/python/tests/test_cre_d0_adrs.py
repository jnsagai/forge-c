"""CRE-T003 — ADR-CRE-001..006 exist, cite only real repository paths, and map every reuse point (no parallel plane)."""
import re

from forge_factory.common import REPO_ROOT

ADRS = sorted((REPO_ROOT / "docs/adr").glob("ADR-CRE-00[1-6]-*.md"))


def test_six_accepted_adrs():
    assert [p.name[:11] for p in ADRS] == [f"ADR-CRE-00{i}" for i in range(1, 7)]
    assert all("Status: accepted" in p.read_text() for p in ADRS)


def test_cited_repository_paths_exist():
    missing = []
    for p in ADRS:
        for ref in re.findall(r"`((?:factory|config|docs|specs|scripts)/[^`*…<> ]+)`", p.read_text()):
            if not (REPO_ROOT / ref.rstrip("/")).exists():
                missing.append(f"{p.name}:{ref}")
    assert missing == []


def test_reuse_map_covers_every_existing_control_plane_component():
    text = (REPO_ROOT / "docs/adr/ADR-CRE-001-reuse-points-and-migration.md").read_text()
    for component in ("incidents.sqlite3", "events.emit", "supervisor", "knowledge/store.py", "kpi/sources.py",
                      "release/finalize.py", "dashboard/app.py", "repair/promotion.py"):
        assert component in text, component
    assert "no parallel component" in text


def test_002_changes_made_during_cre_are_reviewed():
    text = (REPO_ROOT / "docs/adr/ADR-CRE-001-reuse-points-and-migration.md").read_text()
    assert "Review of 002 changes made during CRE" in text
    for f in ("supervisor/router.py", "supervisor/service.py", "test_t009_inspection.py"):
        assert f in text
