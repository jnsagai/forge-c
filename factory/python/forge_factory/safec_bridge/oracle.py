"""F011-T034 (Forge-C side of S013-T016/T017): a SafeC test oracle becomes Forge-C test expectations only after
independent checks.

`materialize(outcome, contract, domain_bytes, workdir)` accepts the `test_oracle` artifact of an admissible PASS
`derive_tests` result only when each of these holds:
- it parses strictly and satisfies contracts/register-io-oracle.schema.json;
- its oracle_digest equals the SHA-256 of its canonical JSON without the digest;
- it is bound to the semantic digest of the contract Forge-C already validated (contract.materialize);
- its cases equal, case by case and in order, what `reference_cases` derives here from the validated operations and
  the domain facts. A difference is `ENGINES_DISAGREE` and blocks, with both values kept.

The expectations come from the contract, so from the source facts. A candidate implementation is never read, and a
model never writes an expected value. `check(oracle, observed)` compares host observations with the oracle: a
finding carries the intent id of its case, so a seeded mutant is reported on the intent it breaks; an absent
observation stays INCONCLUSIVE and never counts as passed.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import contracts as C
from .client import Outcome
from .contract import ValidatedContract

ORACLE_SCHEMA = "forge-c/register-io-oracle/1"


class OracleRejected(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("ORACLE_REJECTED: " + "; ".join(issues[:10]))
        self.issues = issues


def _h32(v: int) -> str:
    return f"0x{v:08x}"


def images(register: dict) -> list[int]:
    """Two initial images: all zeros, and all ones with the bits no field defines held at their reset value."""
    used = 0
    for f in register["fields"]:
        used |= ((1 << (f["msb"] - f["lsb"] + 1)) - 1) << f["lsb"]
    reserved = ~used & 0xFFFFFFFF
    return [0, (0xFFFFFFFF & ~reserved) | (int(register["reset_value"], 16) & reserved)]


def reference_cases(domain: dict, operations: list[dict] | tuple[dict, ...]) -> list[dict]:
    regs = {r["register_id"]: r for r in domain["registers"]}
    out = []
    for op in operations:
        mask, preserved = int(op["field_mask"], 16), int(op["preserved_mask"], 16)
        enc = int(op["encoded_value"], 16) if op.get("encoded_value") else 0
        for init in images(regs[op["register"]]):
            case = {"intent_id": op["intent_id"], "register": op["register"], "offset": op["offset"],
                    "initial": _h32(init)}
            if op["write_kind"] == "none":
                case.update(expected_after=_h32(init), expected_return=str((init & mask) >> op["lsb"]), writes=False)
            elif op["write_kind"] == "full_register_write":
                case.update(expected_after=_h32(enc), expected_return=None, writes=True)
            else:
                case.update(expected_after=_h32((init & preserved) | enc), expected_return=None, writes=True)
            out.append(case)
    return out


def verify(doc: dict, contract: ValidatedContract, domain_bytes: bytes) -> list[str]:
    issues = [f"ORACLE_SCHEMA:{e}" for e in C.schema_errors("oracle", doc)]
    if issues:
        return issues
    body = {k: v for k, v in doc.items() if k != "oracle_digest"}
    if C.sha256_bytes(C.canonical_bytes(body)) != doc["oracle_digest"]:
        issues.append("ORACLE_DIGEST_MISMATCH")
    if doc["contract_semantic_digest"] != contract.semantic_digest:
        issues.append("ORACLE_CONTRACT_MISMATCH")
    if contract.domain_sha256 != C.sha256_bytes(domain_bytes):
        issues.append("ORACLE_DOMAIN_MISMATCH")
        return issues
    ref = reference_cases(json.loads(domain_bytes), contract.operations)
    if len(ref) != len(doc["cases"]):
        issues.append(f"ORACLE_CASE_COUNT: safec={len(doc['cases'])} forge-c={len(ref)}")
        return issues
    for n, (got, want) in enumerate(zip(doc["cases"], ref)):
        for k, v in want.items():
            if got.get(k) != v:
                issues.append(f"ENGINES_DISAGREE:case {n} {want['intent_id']}:{k}: safec={got.get(k)!r} forge-c={v!r}")
    return issues


def materialize(outcome: Outcome, contract: ValidatedContract, domain_bytes: bytes, workdir: Path) -> dict:
    if not outcome.admissible or outcome.status != "PASS":
        raise OracleRejected([f"NOT_ADMISSIBLE:{outcome.status}"] + outcome.issues)
    arts = [a for a in outcome.result["output_artifacts"] if a["kind"] == "test_oracle"]
    if len(arts) != 1:
        raise OracleRejected([f"ORACLE_ARTIFACT_COUNT:{len(arts)}"])
    raw = (Path(workdir) / "evidence/artifacts" / arts[0]["artifact_id"]).read_bytes()
    if C.sha256_bytes(raw) != arts[0]["sha256"]:
        raise OracleRejected(["ORACLE_ARTIFACT_DIGEST"])
    try:
        doc = C.strict_loads(raw, C.MAX_RESULT_BYTES)
    except C.ContractError as exc:
        raise OracleRejected([f"ORACLE_{exc.code}"]) from None
    issues = verify(doc, contract, domain_bytes)
    if issues:
        raise OracleRejected(issues)
    return doc


def check(oracle: dict, observed: dict[str, list[dict]]) -> list[dict]:
    """observed[intent_id] lists observations {initial, after, return} in the oracle's case order for that intent.
    Returns one finding per case that is not a pass; an empty list means every case was observed and matched."""
    out, seen = [], {}
    for case in oracle["cases"]:
        iid = case["intent_id"]
        n = seen.get(iid, 0)
        seen[iid] = n + 1
        obs = (observed.get(iid) or [])[n] if n < len(observed.get(iid) or []) else None
        if obs is None:
            out.append({"intent_id": iid, "verdict": "INCONCLUSIVE", "check": "ORACLE-NO-OBSERVATION"})
        elif obs.get("initial") != case["initial"]:
            out.append({"intent_id": iid, "verdict": "INCONCLUSIVE", "check": "ORACLE-OTHER-INITIAL-IMAGE",
                        "expected": case["initial"], "observed": obs.get("initial")})
        elif obs.get("after") != case["expected_after"]:
            out.append({"intent_id": iid, "verdict": "FAIL",
                        "check": "ORACLE-REGISTER-EFFECT" if case["writes"] else "ORACLE-UNEXPECTED-WRITE",
                        "expected": case["expected_after"], "observed": obs.get("after")})
        elif case["expected_return"] is not None and obs.get("return") != case["expected_return"]:
            out.append({"intent_id": iid, "verdict": "FAIL", "check": "ORACLE-RETURN-VALUE",
                        "expected": case["expected_return"], "observed": obs.get("return")})
    return out
