"""F011-T018: a SafeC validated register contract becomes a Forge-C typed contract only after independent checks.

`materialize(outcome, request, domain_bytes, workdir, pin)` accepts the `validated_contract` artifact of an
admissible PASS only when each of these holds:
- it parses strictly and satisfies contracts/register-io-contract.schema.json;
- its semantic_digest equals the SHA-256 of its canonical JSON (sorted keys, no whitespace, UTF-8) without the
  digest;
- it names the pinned engine, the request's binding and the digest of the domain bytes;
- it has exactly one operation per requested intent, with the intent's identity;
- every number in every operation (offset, bits, width, field mask, encoding, write kind, preserved bits) equals what
  `reference_operation` derives here, in Python, from the same domain facts.

That last check is diversity, not trust: two independent implementations must agree. A disagreement is
`ENGINES_DISAGREE` and blocks, with both values kept. No number from a model ever enters a contract.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import contracts as C
from .client import EnginePin, Outcome


class ContractRejected(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("CONTRACT_REJECTED: " + "; ".join(issues[:10]))
        self.issues = issues


@dataclass(frozen=True)
class ValidatedContract:
    semantic_digest: str
    domain_sha256: str
    operations: tuple[dict, ...]
    coverage: tuple[dict, ...]
    assumptions: tuple[str, ...]
    unresolved_obligations: tuple[str, ...]
    properties_checked: tuple[str, ...]
    raw: dict = field(repr=False, compare=False)

    def by_intent(self) -> dict[str, dict]:
        return {o["intent_id"]: o for o in self.operations}


def _h32(v: int) -> str:
    return f"0x{v:08x}"


def _literal(s: str | None) -> int | None:
    if s is None:
        return None
    return int(s, 16) if s.startswith("0x") else int(s)


def reference_operation(domain: dict, intent: dict) -> dict:
    """What the operation must be for an intent the engine accepted, derived from the domain facts alone (the
    acceptance rules themselves are SafeC's; here only the arithmetic of an accepted operation is recomputed)."""
    reg = next(r for r in domain["registers"] if r["register_id"] == intent["register"])
    f = next(x for x in reg["fields"] if x["field_id"] == intent["field"])
    width = f["msb"] - f["lsb"] + 1
    mask = ((1 << width) - 1) << f["lsb"]
    action = intent["action"]
    if action == "read_field":
        value, kind, encoded, preserved = None, "none", None, 0xFFFFFFFF
    else:
        value = {"set_field": 1, "clear_field": 0}.get(action, _literal(intent.get("logical_value")))
        if value is None and action == "write_key_sequence":  # the key of the one value fact the intent cites
            value = next(int(v["value"], 16) for v in f["values"] if v["fact_id"] in intent["source_fact_ids"])
        bits = value << f["lsb"]
        used = 0
        for x in reg["fields"]:
            used |= ((1 << (x["msb"] - x["lsb"] + 1)) - 1) << x["lsb"]
        reserved = ~used & 0xFFFFFFFF
        if f["access_tokens"] == ["w"]:
            kind, encoded, preserved = "full_register_write", bits | (int(reg["reset_value"], 16) & reserved), 0
        else:
            kind, encoded, preserved = "read_modify_write", bits, ~mask & 0xFFFFFFFF
    return {"intent_id": intent["intent_id"], "action": action, "register": reg["register_id"],
            "field": f["field_id"], "offset": reg["offset"], "lsb": f["lsb"], "msb": f["msb"], "width": width,
            "logical_value": None if value is None else str(value), "field_mask": _h32(mask),
            "encoded_value": None if encoded is None else _h32(encoded),
            "access": {"r": "RO", "w": "WO", "rw": "RW"}.get("+".join(f["access_tokens"]), "UNSUPPORTED"),
            "write_kind": kind, "preserved_mask": _h32(preserved),
            "source_fact_ids": list(intent["source_fact_ids"]),
            "precondition_fact_ids": list(intent.get("precondition_fact_ids") or [])}


def verify(doc: dict, request: dict, domain_bytes: bytes, pin: EnginePin) -> list[str]:
    issues = [f"CONTRACT_SCHEMA:{e}" for e in C.schema_errors("contract", doc)]
    if issues:
        return issues
    body = {k: v for k, v in doc.items() if k != "semantic_digest"}
    if C.sha256_bytes(C.canonical_bytes(body)) != doc["semantic_digest"]:
        issues.append("CONTRACT_DIGEST_MISMATCH")
    if doc["engine"] != pin.expected():
        issues.append("CONTRACT_ENGINE_NOT_PIN")
    if doc["binding"] != request["binding"]:
        issues.append("CONTRACT_BINDING_MISMATCH")
    if doc["domain_sha256"] != C.sha256_bytes(domain_bytes):
        issues.append("CONTRACT_DOMAIN_MISMATCH")
    intents = request["inputs"]["semantic_intents"]
    ops = {o["intent_id"]: o for o in doc["operations"]}
    if sorted(ops) != sorted(i["intent_id"] for i in intents) or len(ops) != len(doc["operations"]):
        issues.append("CONTRACT_INTENTS_MISMATCH")
        return issues
    domain = json.loads(domain_bytes)
    for it in intents:
        try:
            ref = reference_operation(domain, it)
        except (StopIteration, KeyError, ValueError) as exc:
            issues.append(f"REFERENCE_UNAVAILABLE:{it['intent_id']}:{type(exc).__name__}")
            continue
        got = ops[it["intent_id"]]
        for k, v in ref.items():
            if got.get(k) != v:
                issues.append(f"ENGINES_DISAGREE:{it['intent_id']}:{k}: safec={got.get(k)!r} forge-c={v!r}")
    return issues


def materialize(outcome: Outcome, request: dict, domain_bytes: bytes, workdir: Path, pin: EnginePin) -> \
        ValidatedContract:
    if not outcome.admissible or outcome.status != "PASS":
        raise ContractRejected([f"NOT_ADMISSIBLE:{outcome.status}"] + outcome.issues)
    arts = [a for a in outcome.result["output_artifacts"] if a["kind"] == "validated_contract"]
    if len(arts) != 1:
        raise ContractRejected([f"CONTRACT_ARTIFACT_COUNT:{len(arts)}"])
    p = Path(workdir) / "evidence/artifacts" / arts[0]["artifact_id"]
    raw = p.read_bytes()
    if C.sha256_bytes(raw) != arts[0]["sha256"]:
        raise ContractRejected(["CONTRACT_ARTIFACT_DIGEST"])
    try:
        doc = C.strict_loads(raw, C.MAX_RESULT_BYTES)
    except C.ContractError as exc:
        raise ContractRejected([f"CONTRACT_{exc.code}"]) from None
    issues = verify(doc, request, domain_bytes, pin)
    if issues:
        raise ContractRejected(issues)
    return ValidatedContract(doc["semantic_digest"], doc["domain_sha256"], tuple(doc["operations"]),
                             tuple(doc["coverage"]), tuple(doc["assumptions"]), tuple(doc["unresolved_obligations"]),
                             tuple(doc["properties_checked"]), doc)
