"""T005 — agents.yaml loader, SKILL validation and fail-closed preflight.

Issue codes (machine-readable, stable): AGENT_SKILL_MISSING, AGENT_SKILL_INVALID, AGENT_SKILL_HASH_MISMATCH,
AGENT_DUPLICATE_ROLE, AGENT_TOOL_UNKNOWN, AGENT_TOOL_UNGRANTED, AGENT_READONLY_MUTATION,
AGENT_OUTPUT_CONTRACT_MISSING, AGENT_BUDGET_INVALID, AGENT_ROLE_SEPARATION, AGENT_MODEL_NOT_LOCAL.
A run may start only when `preflight()` returns no issue for every role it uses.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..common import CONFIG_DIR, REPO_ROOT, sha256_file
from .mcp_registry import McpRegistry, load_registry

ROLE_ID = re.compile(r"^[a-z][a-z0-9-]{2,40}$")
MUTATING_OPS = {"freeze_baseline", "configure", "compile", "create_worktree", "commit_candidate", "retract_lesson"}
REQUIRED_SECTIONS = ("## Mission", "## Allowed MCP tools", "## Constraints", "## Mandatory compact exit format")
LOCAL_PROVIDERS = {"ollama"}


class AgentDefinition(BaseModel):
    id: str
    skill: str
    description: str
    phase: str | None
    model: str
    model_provider: str
    max_stage_tokens: int = Field(gt=0, le=200_000)
    max_turns: int = Field(gt=0, le=200)
    max_mcp_output_bytes: int = Field(gt=0, le=65_536)
    allowed_tools: list[str] = Field(min_length=1)
    readonly: bool
    output_contract: str
    status: str
    task: str

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ROLE_ID.match(v):
            raise ValueError(f"invalid role id {v!r}")
        return v

    @field_validator("skill")
    @classmethod
    def _skill(cls, v: str, info) -> str:
        p = Path(v)
        # Feature 005 overlay roles (afo-*) keep their skills in factory/skills/afo/<role>/ (the v0.4 design keeps
        # exactly the 20 base skills under .fabro/skills); every other role keeps the strict rule
        afo = str(info.data.get("id", "")).startswith("afo-") and v.startswith("factory/skills/afo/")
        if p.is_absolute() or ".." in p.parts or not (v.startswith(".fabro/skills/") or afo) or p.name != "SKILL.md":
            raise ValueError("skill must be .fabro/skills/<role>/SKILL.md")
        return v


@dataclass(frozen=True)
class Issue:
    code: str
    role: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}:{self.role}:{self.detail}"[:120]


def parse_frontmatter(text: str) -> dict | None:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return meta if isinstance(meta, dict) else None


AFO_AGENTS = CONFIG_DIR / "agents.afo.yaml"


def load_agents(path: Path | None = None, include_afo: bool = False) -> tuple[list[AgentDefinition], list[Issue]]:
    """The v0.4 role registry (20 roles); `include_afo` adds the Feature 005 overlay roles (agents.afo.yaml)."""
    raw = yaml.safe_load((path or CONFIG_DIR / "agents.yaml").read_text(encoding="utf-8"))
    if include_afo and path is None and AFO_AGENTS.is_file():
        raw = {**raw, "agents": list(raw.get("agents", [])) + list(
            (yaml.safe_load(AFO_AGENTS.read_text(encoding="utf-8")) or {}).get("agents") or [])}
    roles, issues = [], []
    from .mcp_registry import role_tool_additions

    adds = role_tool_additions() if path is None else {}
    for item in raw.get("agents", []):
        if item.get("id") in adds:
            item = {**item, "allowed_tools": list(item["allowed_tools"]) + [t for t in adds[item["id"]]
                                                                             if t not in item["allowed_tools"]]}
        try:
            roles.append(AgentDefinition.model_validate(item))
        except ValidationError as exc:
            issues.append(Issue("AGENT_SKILL_INVALID", str(item.get("id", "?")), exc.errors()[0]["msg"][:60]))
    return roles, issues


def validate_skill(role: AgentDefinition, root: Path, lock: dict | None) -> list[Issue]:
    p = root / role.skill
    if not p.is_file():
        return [Issue("AGENT_SKILL_MISSING", role.id, role.skill)]
    text = p.read_text(encoding="utf-8", errors="replace")
    meta = parse_frontmatter(text)
    out: list[Issue] = []
    if meta is None:
        return [Issue("AGENT_SKILL_INVALID", role.id, "frontmatter")]
    if meta.get("name") != role.id or p.parent.name != role.id:
        out.append(Issue("AGENT_SKILL_INVALID", role.id, "name_mismatch"))
    if not isinstance(meta.get("description"), str) or not meta["description"].strip():
        out.append(Issue("AGENT_SKILL_INVALID", role.id, "description"))
    for sec in REQUIRED_SECTIONS:
        if sec not in text:
            out.append(Issue("AGENT_SKILL_INVALID", role.id, f"missing:{sec[3:]}"))
    listed = set(re.findall(r"^- `([a-z-]+\.[a-z_]+)`$", text, re.M))
    if listed != set(role.allowed_tools):
        out.append(Issue("AGENT_SKILL_INVALID", role.id, "tool_list_mismatch"))
    if lock is not None:
        want = (lock.get("skills") or {}).get(role.id, {}).get("sha256")
        if want != sha256_file(p):
            out.append(Issue("AGENT_SKILL_HASH_MISMATCH", role.id, "skills.lock"))
    return out


def preflight(roles_required: list[str] | None = None, agents_path: Path | None = None,
              registry: McpRegistry | None = None, root: Path = REPO_ROOT,
              lock_path: Path | None = None, token_policy_path: Path | None = None, include_afo: bool = False) -> dict:
    """`include_afo` (Feature 005): also the AFO overlay roles, the AFO MCP servers and skills.afo.lock.json."""
    roles, issues = load_agents(agents_path, include_afo=include_afo)
    reg = registry or load_registry(include_afo=include_afo)
    ops = reg.ops()
    lock_file = lock_path or CONFIG_DIR / "skills.lock.json"
    lock = json.loads(lock_file.read_text()) if lock_file.is_file() else None
    afo_lock = CONFIG_DIR / "skills.afo.lock.json"
    if include_afo and lock is not None and afo_lock.is_file():
        lock = {**lock, "skills": {**lock["skills"], **json.loads(afo_lock.read_text())["skills"]}}
    if lock is None:
        issues.append(Issue("AGENT_SKILL_INVALID", "*", "skills.lock.json missing"))
    tok = yaml.safe_load((token_policy_path or CONFIG_DIR / "token-policy.yaml").read_text())
    ids = [r.id for r in roles]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        issues.append(Issue("AGENT_DUPLICATE_ROLE", dup, "duplicate id"))
    by_id = {r.id: r for r in roles}
    for r in roles:
        issues += validate_skill(r, root, lock)
        if not (root / r.output_contract).is_file():
            issues.append(Issue("AGENT_OUTPUT_CONTRACT_MISSING", r.id, r.output_contract))
        if r.model_provider not in LOCAL_PROVIDERS:
            issues.append(Issue("AGENT_MODEL_NOT_LOCAL", r.id, r.model_provider))
        output_limit = (tok.get("afo_max_tool_result_bytes", tok["max_tool_result_bytes"])
                        if r.id.startswith("afo-") else tok["max_tool_result_bytes"])
        if (type(output_limit) is not int or not 0 < output_limit <= 65_536
                or r.max_mcp_output_bytes > output_limit):
            issues.append(Issue("AGENT_BUDGET_INVALID", r.id, "max_mcp_output_bytes"))
        for t in r.allowed_tools:
            if t not in ops:
                issues.append(Issue("AGENT_TOOL_UNKNOWN", r.id, t))
            elif r.id not in ops[t].role_grants:
                issues.append(Issue("AGENT_TOOL_UNGRANTED", r.id, t))
            if r.readonly and t.split(".")[-1] in MUTATING_OPS:
                issues.append(Issue("AGENT_READONLY_MUTATION", r.id, t))
    for i in range(1, 7):
        a, n = by_id.get(f"swe{i}-author"), by_id.get(f"swe{i}-inspector")
        if not a or not n or a.skill == n.skill or not n.readonly or a.model_provider == "" or a.id == n.id:
            issues.append(Issue("AGENT_ROLE_SEPARATION", f"swe{i}", "author/inspector"))
    if roles_required is not None:
        missing = [x for x in roles_required if x not in by_id]
        issues += [Issue("AGENT_SKILL_MISSING", m, "undeclared role") for m in missing]
        relevant = set(roles_required) | {"*"} | {f"swe{i}" for i in range(1, 7)}
        issues = [i for i in issues if i.role in relevant]
    snapshot = {r.id: {"skill": r.skill, "sha256": sha256_file(root / r.skill) if (root / r.skill).is_file()
                       else None, "model": r.model, "allowed_tools": sorted(r.allowed_tools),
                       "readonly": r.readonly, "phase": r.phase} for r in roles}
    return {"status": "PASS" if not issues else "BLOCKED", "issues": [str(i) for i in issues],
            "issue_codes": sorted({i.code for i in issues}), "roles": len(roles), "snapshot": snapshot}
