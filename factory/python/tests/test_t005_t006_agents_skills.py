"""T005/T006 (AT-01): agent registry + SKILL preflight fails closed; all 20 skills valid and discoverable."""
import json
import shutil
from pathlib import Path

import pytest
import yaml
from forge_factory.common import REPO_ROOT
from forge_factory.registry import agents as A
from forge_factory.registry.skillgen import render

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sandbox(tmp_path):
    """Copy the minimal repo surface preflight needs, so tests can corrupt it safely."""
    for rel in [".fabro/skills", "config/factory", "specs/002-self-healing-factory/contracts"]:
        shutil.copytree(REPO_ROOT / rel, tmp_path / rel)
    return tmp_path


def run(root: Path, roles=None):
    return A.preflight(roles, agents_path=root / "config/factory/agents.yaml", root=root,
                       lock_path=root / "config/factory/skills.lock.json",
                       token_policy_path=root / "config/factory/token-policy.yaml")


def test_repository_preflight_passes_for_all_20_roles():
    r = A.preflight()
    assert r["status"] == "PASS", r["issues"]
    assert r["roles"] == 20 and len(r["snapshot"]) == 20
    assert all(v["sha256"] for v in r["snapshot"].values())


def test_missing_skill_blocks_with_code(sandbox):
    (sandbox / ".fabro/skills/swe3-author/SKILL.md").unlink()
    r = run(sandbox, ["swe3-author"])
    assert r["status"] == "BLOCKED" and "AGENT_SKILL_MISSING" in r["issue_codes"]


def test_corrupt_skill_blocks_invalid_and_hash(sandbox):
    p = sandbox / ".fabro/skills/swe3-inspector/SKILL.md"
    p.write_text(p.read_text().replace("## Mandatory compact exit format", "## Whatever"))
    r = run(sandbox, ["swe3-inspector"])
    assert {"AGENT_SKILL_INVALID", "AGENT_SKILL_HASH_MISMATCH"} <= set(r["issue_codes"])


def test_frontmatter_name_mismatch_and_tool_list_drift(sandbox):
    p = sandbox / ".fabro/skills/release-manager/SKILL.md"
    p.write_text(p.read_text().replace("name: release-manager", "name: release-boss", 1)
                 .replace("- `forge-repo-mcp.get_commit`\n", "- `forge-repo-mcp.get_commit`\n- `forge-x-mcp.shell`\n"))
    r = run(sandbox, ["release-manager"])
    assert any("name_mismatch" in i for i in r["issues"]) and any("tool_list_mismatch" in i for i in r["issues"])


def test_duplicate_role_and_ungranted_tool(sandbox):
    cfgp = sandbox / "config/factory/agents.yaml"
    cfg = yaml.safe_load(cfgp.read_text())
    cfg["agents"].append(dict(cfg["agents"][0]))
    cfg["agents"][1]["allowed_tools"].append("forge-evidence-mcp.build_package")
    cfgp.write_text(yaml.safe_dump(cfg))
    r = run(sandbox)
    assert {"AGENT_DUPLICATE_ROLE", "AGENT_TOOL_UNGRANTED"} <= set(r["issue_codes"])


def test_readonly_role_with_mutating_tool_and_cloud_model_rejected(sandbox):
    cfgp = sandbox / "config/factory/agents.yaml"
    cfg = yaml.safe_load(cfgp.read_text())
    insp = next(a for a in cfg["agents"] if a["id"] == "swe2-inspector")
    insp["allowed_tools"].append("forge-build-mcp.compile")
    insp["model_provider"] = "openai"
    cfgp.write_text(yaml.safe_dump(cfg))
    r = run(sandbox, ["swe2-inspector"])
    assert {"AGENT_READONLY_MUTATION", "AGENT_MODEL_NOT_LOCAL"} <= set(r["issue_codes"])


def test_unsafe_skill_path_rejected(sandbox):
    cfgp = sandbox / "config/factory/agents.yaml"
    cfg = yaml.safe_load(cfgp.read_text())
    cfg["agents"][0]["skill"] = "../../etc/passwd"
    cfgp.write_text(yaml.safe_dump(cfg))
    assert "AGENT_SKILL_INVALID" in run(sandbox)["issue_codes"]


def test_skills_render_deterministically_and_match_lock():
    roles = yaml.safe_load((REPO_ROOT / "config/factory/agents.yaml").read_text())["agents"]
    for role in roles:
        assert (REPO_ROOT / role["skill"]).read_text() == render(role), role["id"]


def test_swe1_skills_require_ears():
    assert "EARS" in (REPO_ROOT / ".fabro/skills/swe1-author/SKILL.md").read_text()
    assert "SWE1-07" in (REPO_ROOT / ".fabro/skills/swe1-inspector/SKILL.md").read_text()


def test_fabro_discovered_all_20_skills_in_live_probe():
    """Recorded from the installed Fabro 0.362 (agent.skills.discovered event)."""
    evs = [json.loads(x) for x in (FIX / "fabro-0.362-skills-discovered.json").read_text().splitlines() if x]
    names = {s["name"] for s in evs[0]["skills"]}
    roles = {a["id"] for a in yaml.safe_load((REPO_ROOT / "config/factory/agents.yaml").read_text())["agents"]}
    assert names == roles
