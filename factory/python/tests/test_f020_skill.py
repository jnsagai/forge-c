"""Feature 020 T014 (constitution IV): the swe1-author role text covers the governance task and the functional template.

The role SKILL.md is part of every register-level SWE.1 packet (its sha256 is in the packet and its input hash), so it
stays byte-identical (T007 golden); the registry generator renders the functional-level text as a versioned reference
file of the same skill, `.fabro/skills/swe1-author/references/functional-level.md` (decision log D15), from the
template config. Functional-level packets carry it as a hash-bound source; register-level packets never do."""
from __future__ import annotations

import json

import yaml
from forge_factory.common import CONFIG_DIR, REPO_ROOT, sha256_file
from forge_factory.registry import skillgen

REF = ".fabro/skills/swe1-author/references/functional-level.md"


def test_the_generator_renders_the_committed_reference_file():
    assert skillgen.FUNCTIONAL_REFERENCES == {"swe1-author": REF}
    assert (REPO_ROOT / REF).read_text() == skillgen.render_functional("swe1-author")


def test_the_reference_covers_the_governance_task_and_every_template_rule():
    text = skillgen.render_functional("swe1-author")
    t = yaml.safe_load((CONFIG_DIR / "swe1-functional-template.yaml").read_text())
    assert "## Governance task" in text and "## Functional-level requirements" in text
    for word in ("actors", "use cases", "open point", "assumptions", "implementation under analysis",
                 t["template_id"], "EARS", "inspection", "not applicable until SWE.2"):
        assert word in text, word
    for attr in t["attributes"]:
        assert f"`{attr}`" in text, attr
    for values in t["enums"].values():
        for v in values:
            assert f"`{v}`" in text, v


def test_the_role_skill_itself_is_unchanged():
    roles = {r["id"]: r for r in yaml.safe_load((CONFIG_DIR / "agents.yaml").read_text())["agents"]}
    assert (REPO_ROOT / ".fabro/skills/swe1-author/SKILL.md").read_text() == skillgen.render(
        {**roles["swe1-author"], "allowed_tools": _tools("swe1-author")})
    assert "functional-level" not in (REPO_ROOT / ".fabro/skills/swe1-author/SKILL.md").read_text()
    lock = json.loads((CONFIG_DIR / "skills.lock.json").read_text())
    assert REF not in json.dumps(lock)  # the release packages' skills manifest stays as it is


def _tools(role: str) -> list[str]:
    from forge_factory.registry.agents import load_agents

    return {a.id: a.allowed_tools for a in load_agents()[0]}[role]


def test_the_governance_packet_carries_the_reference_bound_by_hash(tmp_path, monkeypatch):
    from test_f020_governance_package import MODEL, prepared

    from f020_fixtures import ser_spec
    from forge_factory.governance import package as P

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws = prepared(tmp_path, ser_spec())
    p = P.packet(ws, MODEL)
    src = {s["path"]: s["sha256"] for s in p["sources"]}
    assert src[REF] == sha256_file(REPO_ROOT / REF)
    assert "## Governance task" in "\n".join(m["content"] for m in p["_messages"])
