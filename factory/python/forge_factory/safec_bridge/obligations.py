"""F011-T033 (Forge-C side of S013-T018): SafeC's C11/ACSL lowering becomes Forge-C proof obligations only after
independent checks.

`materialize(outcome, contract, domain_bytes, workdir)` accepts the `formal_obligations` artifact of an admissible
PASS `derive_contracts` result only when each of these holds:
- it parses strictly and satisfies contracts/register-io-obligations.schema.json;
- its obligations_digest equals the SHA-256 of its canonical JSON without the digest;
- it is bound to the semantic digest of the contract Forge-C already validated (contract.materialize);
- per operation, in order, it states what `reference` derives here from the validated operations: the obligation
  ids and their ACSL text, the word, the write kind, the C11 reference body, the applicability class per tool and
  the obligations not lowered. A difference is `ENGINES_DISAGREE` and blocks, with both values kept.

The obligations come from the contract, so from the source facts; a candidate implementation is never read. The
model is stated in the document (registers as plain memory, one thread, no interrupts, one call); nothing outside
it is covered.
"""
from __future__ import annotations

from pathlib import Path

from . import contracts as C
from .client import Outcome
from .contract import ValidatedContract

OBLIGATIONS_SCHEMA = "forge-c/register-io-obligations/1"
REGISTER_ARRAY = "R"
WP = "frama-c-wp"


class ObligationsRejected(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("OBLIGATIONS_REJECTED: " + "; ".join(issues[:10]))
        self.issues = issues


def applicability(obligation: str) -> dict[str, str]:
    """The class per tool (the text before ':'), as measured (S013-T018): WP leaves bit preservation open, a
    bit-precise bounded checker decides it, and a one-call pre/post property is not a Kind 2 (temporal) property."""
    return {"cbmc": "SUPPORTED", WP: "INCONCLUSIVE" if obligation == "PRESERVED_BITS" else "SUPPORTED",
            "kind2": "NOT_APPLICABLE"}


def lower(op: dict, reg: str = REGISTER_ARRAY) -> tuple[list[tuple[str, str]], str]:
    """(obligation id, ACSL clause) pairs over the register array `reg`, and the C11 reference statement."""
    w = int(str(op["offset"]), 0) // 4
    mask, pres = int(op["field_mask"], 16), int(op["preserved_mask"], 16)
    enc = int(op["encoded_value"], 16) if op.get("encoded_value") else 0
    if op["write_kind"] == "none":
        return ([("RETURN_FIELD", f"ensures \\result == ((\\old({reg}[{w}]) & 0x{mask:08X}U) >> {op['lsb']});"),
                 ("NO_WRITE", "assigns \\nothing;")],
                f"return ({reg}[{w}U] & 0x{mask:08X}U) >> {op['lsb']}U;")
    if op["write_kind"] == "full_register_write":
        return ([("WHOLE_WORD", f"ensures {reg}[{w}] == 0x{enc:08X}U;"), ("FRAME", f"assigns {reg}[{w}];")],
                f"{reg}[{w}U] = 0x{enc:08X}U;")
    return ([("FIELD_VALUE", f"ensures ({reg}[{w}] & 0x{mask:08X}U) == 0x{enc & mask:08X}U;"),
             ("PRESERVED_BITS", f"ensures ({reg}[{w}] & 0x{pres:08X}U) == (\\old({reg}[{w}]) & 0x{pres:08X}U);"),
             ("FRAME", f"assigns {reg}[{w}];")],
            f"{reg}[{w}U] = ({reg}[{w}U] & 0x{pres:08X}U) | 0x{enc:08X}U;")


def not_lowered(op: dict) -> list[str]:
    head = ["KEY_SEQUENCE_ORDER"] if op["action"] == "write_key_sequence" else []
    return head + ["HARDWARE_SIDE_EFFECTS", "RESET_AND_TIMING", "CONCURRENCY"]


def reference(operations: list[dict] | tuple[dict, ...]) -> list[dict]:
    out = []
    for op in operations:
        clauses, body = lower(op)
        out.append({"intent_id": op["intent_id"], "register": op["register"], "field": op["field"],
                    "offset": op["offset"], "word": int(str(op["offset"]), 0) // 4, "write_kind": op["write_kind"],
                    "obligations": [{"id": i, "acsl": a, "applicability": applicability(i)} for i, a in clauses],
                    "reference_c11": body, "unsupported": not_lowered(op)})
    return out


def _as_stated(op: dict) -> dict:
    """SafeC's operation reduced to what Forge-C derives: the applicability class per tool, the not-lowered ids."""
    return {**op, "obligations": [{"id": o["id"], "acsl": o["acsl"],
                                   "applicability": {t: v.split(":", 1)[0] for t, v in o["applicability"].items()}}
                                  for o in op["obligations"]],
            "unsupported": [u["obligation"] for u in op["unsupported"]]}


def verify(doc: dict, contract: ValidatedContract, domain_bytes: bytes) -> list[str]:
    issues = [f"OBLIGATIONS_SCHEMA:{e}" for e in C.schema_errors("obligations", doc)]
    if issues:
        return issues
    body = {k: v for k, v in doc.items() if k != "obligations_digest"}
    if C.sha256_bytes(C.canonical_bytes(body)) != doc["obligations_digest"]:
        issues.append("OBLIGATIONS_DIGEST_MISMATCH")
    if doc["contract_semantic_digest"] != contract.semantic_digest:
        issues.append("OBLIGATIONS_CONTRACT_MISMATCH")
    if contract.domain_sha256 != C.sha256_bytes(domain_bytes):
        issues.append("OBLIGATIONS_DOMAIN_MISMATCH")
    if doc["register_array"] != REGISTER_ARRAY:
        issues.append(f"OBLIGATIONS_REGISTER_ARRAY:{doc['register_array']}")
    if issues:
        return issues
    ref = reference(contract.operations)
    if len(ref) != len(doc["operations"]):
        return [f"OBLIGATIONS_OPERATION_COUNT: safec={len(doc['operations'])} forge-c={len(ref)}"]
    for got, want in zip(doc["operations"], ref):
        got = _as_stated(got)
        for k, v in want.items():
            if got.get(k) != v:
                issues.append(f"ENGINES_DISAGREE:{want['intent_id']}:{k}: safec={got.get(k)!r} forge-c={v!r}")
    return issues


def materialize(outcome: Outcome, contract: ValidatedContract, domain_bytes: bytes, workdir: Path) -> dict:
    if not outcome.admissible or outcome.status != "PASS":
        raise ObligationsRejected([f"NOT_ADMISSIBLE:{outcome.status}"] + outcome.issues)
    arts = [a for a in outcome.result["output_artifacts"] if a["kind"] == "formal_obligations"]
    if len(arts) != 1:
        raise ObligationsRejected([f"OBLIGATIONS_ARTIFACT_COUNT:{len(arts)}"])
    raw = (Path(workdir) / "evidence/artifacts" / arts[0]["artifact_id"]).read_bytes()
    if C.sha256_bytes(raw) != arts[0]["sha256"]:
        raise ObligationsRejected(["OBLIGATIONS_ARTIFACT_DIGEST"])
    try:
        doc = C.strict_loads(raw, C.MAX_RESULT_BYTES)
    except C.ContractError as exc:
        raise ObligationsRejected([f"OBLIGATIONS_{exc.code}"]) from None
    issues = verify(doc, contract, domain_bytes)
    if issues:
        raise ObligationsRejected(issues)
    return doc
