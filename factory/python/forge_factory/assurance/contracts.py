"""EASA contracts: the 13 JSON Schemas and catalogs authored in specs/006 are the source of truth (read only)."""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from ..common import REPO_ROOT, load_yaml, sha256_file

SPEC_DIR = REPO_ROOT / "specs" / "006-enhanced-ai-software-assurance"
CONTRACTS = SPEC_DIR / "contracts"
CATALOG = CONTRACTS / "iso26262-6-2018-methods.working.yaml"
TECHNIQUES = CONTRACTS / "enhanced-techniques.yaml"
POLICY_EXAMPLE = CONTRACTS / "assurance-policy.example.yaml"
SCHEMAS = ("assurance-claim", "assurance-policy", "assurance-readiness", "coverage-evidence", "gate-decision",
           "hardware-fidelity", "independence-attestation", "method-applicability", "method-record",
           "mutation-campaign", "oracle-provenance", "safety-scope", "verification-run")


@cache
def schema(name: str) -> dict:
    from jsonschema import Draft202012Validator

    doc = json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(doc)
    return doc


def errors(name: str, instance: Any) -> list[str]:
    """Schema violations as short strings (empty list = valid)."""
    from jsonschema import Draft202012Validator, FormatChecker

    v = Draft202012Validator(schema(name), format_checker=FormatChecker())
    return sorted(f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:200] for e in v.iter_errors(instance))


def load(path: Path) -> Any:
    return load_yaml(path) if path.suffix in (".yaml", ".yml") else json.loads(path.read_text(encoding="utf-8"))


def contract_digests() -> dict[str, str]:
    """sha256 of every authored contract file, to bind decisions to the exact design baseline."""
    return {p.relative_to(REPO_ROOT).as_posix(): sha256_file(p) for p in sorted(CONTRACTS.rglob("*")) if p.is_file()}
