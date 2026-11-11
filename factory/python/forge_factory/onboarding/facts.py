"""Feature 016 (OB-T004): the onboarding package - facts with their sources, authored items, test-environment
assumptions and gaps - and its canonical hash. A fact is DERIVED (value + at least one source), NOT_DERIVED (no value,
an owner question) or CONFLICT (sources that disagree, an owner question); nothing is ever defaulted or guessed
(FR-005). The hash covers everything but itself and the creation time, so the same inputs give the same hash (FR-006)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..common import REPO_ROOT, canonical_json, pretty_json, sha256_bytes, utc_now

SCHEMA = "forge-c/onboarding-package/0.1"
CONTRACT = REPO_ROOT / "specs/016-peripheral-onboarding/contracts/onboarding-package.schema.json"
PACKAGE = "onboarding/package.json"
STATUSES = ("DERIVED", "NOT_DERIVED", "CONFLICT")
BLOCKING = ("CONFLICT", "ASSUMPTION_UNCONFIRMED", "MISSING_INPUT")


class PackageError(ValueError):
    pass


@dataclass(frozen=True)
class Source:
    kind: str                       # file | doc | log | workorder
    ref: str
    line: int | None = None
    page: int | None = None
    value: Any = None

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Fact:
    name: str
    value: Any
    status: str
    method: str
    sources: list[Source] = field(default_factory=list)
    owner_question: str | None = None

    def as_dict(self) -> dict:
        d = {"name": self.name, "value": self.value, "status": self.status, "method": self.method,
             "sources": [s.as_dict() for s in self.sources]}
        if self.owner_question:
            d["owner_question"] = self.owner_question
        return d


def derived(name: str, value: Any, method: str, *sources: Source) -> Fact:
    if value is None or not sources:
        raise PackageError(f"FACT_DERIVED_WITHOUT_VALUE_OR_SOURCE:{name}")
    return Fact(name, value, "DERIVED", method, list(sources))


def not_derived(name: str, method: str, question: str, *sources: Source) -> Fact:
    return Fact(name, None, "NOT_DERIVED", method, list(sources), question)


def conflict(name: str, method: str, question: str, *sources: Source) -> Fact:
    if len({json.dumps(s.value, sort_keys=True) for s in sources}) < 2:
        raise PackageError(f"FACT_CONFLICT_WITHOUT_DIFFERENT_SOURCES:{name}")
    return Fact(name, None, "CONFLICT", method, list(sources), question)


def agree(name: str, method: str, question: str, *sources: Source) -> Fact:
    """DERIVED when every source carries the same value, CONFLICT otherwise (e.g. CMSIS base vs RM memory map)."""
    values = {json.dumps(s.value, sort_keys=True) for s in sources}
    if len(values) == 1:
        return derived(name, sources[0].value, method, *sources)
    return conflict(name, method, question, *sources)


@dataclass
class Assumption:
    id: str
    symbol: str
    reason: str
    affects: list[str]
    proposed_value: Any = None
    proposed_source: Source | None = None
    confirmed_value: Any = None

    def as_dict(self) -> dict:
        d = {"id": self.id, "symbol": self.symbol, "reason": self.reason, "affects": self.affects}
        if self.proposed_value is not None:
            d["proposed_value"] = self.proposed_value
        if self.proposed_source is not None:
            d["proposed_source"] = self.proposed_source.as_dict()
        if self.confirmed_value is not None:
            d["confirmed_value"] = self.confirmed_value
        return d


def gaps_from(facts: list[dict], authored: list[dict], assumptions: list[dict],
              missing_inputs: list[tuple[str, str]] = ()) -> list[dict]:
    """Gaps in a fixed order (missing inputs, facts by name, authored items, assumptions) with ids GAP-OB-nnn."""
    out: list[tuple[str, str, str]] = [("MISSING_INPUT", ref, effect) for ref, effect in missing_inputs]
    for f in sorted(facts, key=lambda x: x["name"]):
        if f["status"] != "DERIVED":
            out.append((f["status"], f["name"], f.get("owner_question") or ""))
    for a in sorted(authored, key=lambda x: x["id"]):
        if a["status"] != "ACCEPTED":
            out.append(("AUTHORED_ITEM_FAILED", a["id"], "; ".join(a["gate"]["findings"] + a["inspection"]["findings"])
                        or "not accepted"))
    for a in sorted(assumptions, key=lambda x: x["id"]):
        if a.get("confirmed_value") is None:
            out.append(("ASSUMPTION_UNCONFIRMED", a["id"], "dependent results: " + ", ".join(a["affects"])))
    return [{"id": f"GAP-OB-{i:03d}", "kind": k, "ref": r, "effect": e or k, "blocks_approval": k in BLOCKING}
            for i, (k, r, e) in enumerate(out, 1)]


def canonical_hash(package: dict) -> str:
    """The approval subject: inputs, facts, items, assumptions, gaps, profile, texts. The factory revision and the
    creation time are recorded but not part of it - a factory update that derives the same facts keeps the approval."""
    body = {k: v for k, v in package.items() if k not in ("sha256", "created_at", "factory_revision")}
    return sha256_bytes(canonical_json(body))


def validate(package: dict) -> list[str]:
    import jsonschema

    schema = json.loads(CONTRACT.read_text())
    return [f"{'/'.join(map(str, e.absolute_path)) or '-'}:{e.message[:160]}"
            for e in jsonschema.Draft202012Validator(schema).iter_errors(package)]


def assemble(work_order: str, inputs: list[dict], revision: str, style: str, facts: list[Fact],
             authored: list[dict], assumptions: list[Assumption], profile: dict, texts: dict,
             missing_inputs: list[tuple[str, str]] = ()) -> dict:
    fd = sorted((f.as_dict() for f in facts), key=lambda x: x["name"])
    ad = [a.as_dict() for a in assumptions]
    pkg = {"schema": SCHEMA, "work_order": work_order, "inputs": sorted(inputs, key=lambda x: x["path"]),
           "factory_revision": revision, "driver_style": style, "facts": fd, "authored": authored,
           "assumptions": ad, "gaps": gaps_from(fd, authored, ad, missing_inputs), "profile": profile,
           "texts": texts, "status": "BLOCKED" if missing_inputs else "READY_FOR_OWNER"}
    pkg["sha256"] = canonical_hash(pkg)
    pkg["created_at"] = utc_now()
    return pkg


def write_package(ws: Path, package: dict) -> Path:
    errs = validate(package)
    if errs:
        raise PackageError("ONBOARDING_PACKAGE_INVALID:" + " | ".join(errs[:5]))
    if package["sha256"] != canonical_hash(package):
        raise PackageError("ONBOARDING_PACKAGE_HASH_MISMATCH")
    p = Path(ws) / PACKAGE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(pretty_json(package))
    return p


def read_package(ws: Path) -> dict | None:
    p = Path(ws) / PACKAGE
    return json.loads(p.read_text()) if p.is_file() else None


def fact(package: dict, name: str) -> dict | None:
    return next((f for f in package["facts"] if f["name"] == name), None)


def value(package: dict, name: str) -> Any:
    f = fact(package, name)
    return f["value"] if f and f["status"] == "DERIVED" else None
