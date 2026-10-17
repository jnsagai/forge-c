"""EASA-FR-072 / AT-080 — autonomous changes may not touch safety constitution, release/CRE policies, approved
specs/contracts, the assurance policy authorization or historical evidence. Reuses the CRE git-based check (the
diff decides, not an agent claim); EASA adds its own design baseline and policy to the protected set."""
from __future__ import annotations

from pathlib import Path

from ..common import REPO_ROOT, load_yaml
from ..reliability.protect import protected_changes

EASA_GLOBS = ["specs/005-autonomous-factory-operations/**", "specs/006-enhanced-ai-software-assurance/**",
              "specs/004-continuous-reliability-engineering/**", "config/factory/assurance-policy.yaml",
              "config/factory/reliability-policy.yaml", "config/factory/*release*", "config/factory/*safety*",
              "factory/release-manager/**", ".specify/memory/constitution.md", "CLAUDE.md", "evidence/**"]


def globs(repo: Path = REPO_ROOT) -> list[str]:
    pol = repo / "config/factory/reliability-policy.yaml"
    cre = list(((load_yaml(pol) or {}).get("security") or {}).get("protected_path_globs") or []) if pol.is_file() else []
    return sorted(set(cre) | set(EASA_GLOBS))


def denied(base: str, candidate: str, repo: Path = REPO_ROOT, strict: bool = True) -> list[str]:
    """Protected-path changes between two revisions; strict=True (autonomous candidates) also denies new evidence."""
    return protected_changes(base, candidate, globs(repo), repo=repo, strict=strict)
