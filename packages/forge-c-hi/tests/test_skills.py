"""Skill files: frontmatter per the Agent Skills format, stage mapping, and cited reference paths."""
from __future__ import annotations

import json
import re

import pytest

from conftest import REFS, SKILLS

SKILL_DIRS = sorted(p for p in SKILLS.iterdir() if p.is_dir())
ROLES = {"author", "inspector", "gate", "conductor", "intake", "release"}
STAGES = json.loads((REFS / "stages.json").read_text())
STAGE_IDS = {s["id"] for s in STAGES["stages"]}
# Stage skills that later milestones add (US4). Shrinks to empty as they land.
PENDING = set()


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter"
    fm, meta, cur = {}, {}, None
    for line in m.group(1).splitlines():
        if line.startswith("  ") and cur == "metadata":
            k, _, v = line.strip().partition(":")
            meta[k.strip()] = v.strip().strip('"')
        else:
            k, _, v = line.partition(":")
            cur = k.strip()
            fm[cur] = v.strip()
    fm["metadata"] = meta
    return fm, text[m.end():]


@pytest.mark.parametrize("d", SKILL_DIRS, ids=lambda p: p.name)
def test_frontmatter(d):
    fm, body = frontmatter(d / "SKILL.md")
    assert fm["name"] == d.name and re.fullmatch(r"[a-z0-9-]{1,64}", d.name)
    assert 50 <= len(fm["description"]) <= 1024
    assert fm["license"] == "Apache-2.0"
    meta = fm["metadata"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", meta["version"])
    assert meta["role"] in ROLES
    assert meta["stage"] == "all" or meta["stage"] in STAGE_IDS
    assert len(body.strip()) > 300


@pytest.mark.parametrize("d", SKILL_DIRS, ids=lambda p: p.name)
def test_cited_reference_paths_exist(d):
    _, body = frontmatter(d / "SKILL.md")
    for ref in re.findall(r"`(hi-gates/references/[\w./-]+\.json)`", body):
        assert (SKILLS / ref).is_file(), ref
    for ref in re.findall(r"`(references/[\w./-]+\.json)`", body):
        assert (d / ref).is_file(), ref


def test_every_stage_skill_exists_or_is_pending():
    for st in STAGES["stages"]:
        for key, role in (("author_skill", "author"), ("inspector_skill", "inspector")):
            name = st[key]
            if name in PENDING:
                assert not (SKILLS / name).exists(), f"{name} landed: remove it from PENDING"
                continue
            fm, _ = frontmatter(SKILLS / name / "SKILL.md")
            assert fm["metadata"]["role"] == role
            assert fm["metadata"]["stage"] in (st["id"], "all") or name.startswith("hi-sys-verif")


def test_inspector_skills_are_read_only():
    for d in SKILL_DIRS:
        fm, body = frontmatter(d / "SKILL.md")
        if fm["metadata"]["role"] == "inspector":
            assert fm["metadata"]["write_scope"] == ""
            assert "never create, edit or delete a file" in body.lower()


def test_no_certification_claims_in_skills():
    bad = re.compile(r"\b(is|are|becomes?|makes?\s+\w+)\s+(certified|compliant|qualified|approved)\b", re.I)
    for d in SKILL_DIRS:
        assert not bad.search((d / "SKILL.md").read_text()), d.name


def test_core_rules_copy_matches_instructions():
    from conftest import PKG
    src = (PKG / ".apm/instructions/hi-core.instructions.md").read_text()
    body = re.sub(r"^---\n.*?\n---\n\n?", "", src, flags=re.S)
    assert (REFS / "hi-core-rules.md").read_text() == body


def test_compact_reply_contract_stated():
    """T082: authors reply with AgentStatus (<=2 KB contract), inspectors with the findings object."""
    for d in SKILL_DIRS:
        fm, body = frontmatter(d / "SKILL.md")
        if fm["metadata"]["role"] == "author":
            assert "AgentStatus" in body and ("agent-status.schema.json" in body or '"role": "author"' in body), d.name
        if fm["metadata"]["role"] == "inspector":
            assert '"status": "DONE", "findings"' in body.replace("\n", " "), d.name
