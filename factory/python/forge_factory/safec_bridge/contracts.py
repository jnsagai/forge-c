"""F011-T006: strict parsing of the frozen SafeC bridge wire contracts (specs/011-safec-semantic-first/contracts).

Every message crossing the bridge is bytes from another program. It is accepted only if it is
- at most a fixed size;
- valid UTF-8;
- one JSON object without duplicate keys or non-finite numbers;
- valid against the frozen 2020-12 schema;
- consistent beyond the schema (unique finding and artifact ids, no PASS that carries a major or critical finding).

Anything else is a `ContractError` with a machine-readable code and is never interpreted. Requests are written as
canonical bytes (sorted keys, no whitespace, UTF-8), so the request digest is reproducible.

The identity handshake (`<engine> identity`) is a separate, versioned message of this module (IDENTITY_SCHEMA). It
names the engine and the protocol versions it speaks, and it carries no check result. An engine that implements
register-io semantics also names the domain protocol (DOMAIN_SCHEMA): the domain document is passed as a file
whose SHA-256 is the request's binding.source_manifest_sha256.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..common import REPO_ROOT, sha256_file

FEATURE = REPO_ROOT / "specs/011-safec-semantic-first/contracts"
REQUEST_SCHEMA = "forge-c/safec-bridge-request/1"
RESULT_SCHEMA = "forge-c/safec-bridge-result/1"
IDENTITY_SCHEMA = "forge-c/safec-bridge-identity/1"
DOMAIN_SCHEMA = "forge-c/register-io-domain/2"
CONTRACT_SCHEMA = "forge-c/register-io-contract/1"
STATUSES = ("PASS", "FAIL", "INCONCLUSIVE", "UNSUPPORTED", "STALE", "ERROR")
PROFILES = ("register-io-0.1",)
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESULT_BYTES = 4 * 1024 * 1024
MAX_IDENTITY_BYTES = 64 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


class ContractError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ContractError("DUPLICATE_KEY", k[:80])
        out[k] = v
    return out


def _no_constant(name: str):
    raise ContractError("NON_FINITE_NUMBER", name)


def strict_loads(raw: bytes, limit: int) -> dict:
    if not isinstance(raw, bytes | bytearray):
        raise ContractError("NOT_BYTES")
    if len(raw) > limit:
        raise ContractError("OVERSIZED", f"{len(raw)} > {limit} bytes")
    if not raw.strip():
        raise ContractError("EMPTY")
    try:
        text = bytes(raw).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractError("INVALID_UTF8", f"byte {exc.start}") from None
    try:
        doc = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except ContractError:
        raise
    except (ValueError, RecursionError) as exc:
        raise ContractError("MALFORMED_JSON", str(exc)[:200]) from None
    if not isinstance(doc, dict):
        raise ContractError("NOT_AN_OBJECT")
    return doc


_validators: dict[str, object] = {}


def schema(kind: str) -> dict:
    name = {"request": "bridge-request.schema.json", "result": "bridge-result.schema.json",
            "domain": "register-io-domain.schema.json", "contract": "register-io-contract.schema.json"}[kind]
    return json.loads((FEATURE / name).read_text())


def _validator(kind: str):
    if kind not in _validators:
        from jsonschema import Draft202012Validator

        s = schema(kind)
        Draft202012Validator.check_schema(s)
        _validators[kind] = Draft202012Validator(s)
    return _validators[kind]


def schema_errors(kind: str, doc: dict) -> list[str]:
    return sorted(f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"[:300]
                  for e in _validator(kind).iter_errors(doc))


def _require(kind: str, doc: dict) -> dict:
    errs = schema_errors(kind, doc)
    if errs:
        raise ContractError("SCHEMA_VIOLATION", "; ".join(errs[:5]))
    return doc


def parse_request(raw: bytes) -> dict:
    return _require("request", strict_loads(raw, MAX_REQUEST_BYTES))


def parse_result(raw: bytes) -> dict:
    doc = _require("result", strict_loads(raw, MAX_RESULT_BYTES))
    ids = [f["finding_id"] for f in doc["findings"]]
    if len(ids) != len(set(ids)):
        raise ContractError("DUPLICATE_FINDING_ID")
    arts = [a["artifact_id"] for a in doc["output_artifacts"]]
    if len(arts) != len(set(arts)):
        raise ContractError("DUPLICATE_ARTIFACT_ID")
    if doc["status"] == "PASS" and any(f["severity"] in ("major", "critical") for f in doc["findings"]):
        raise ContractError("CONTRADICTORY_PASS", "PASS with a major or critical finding")
    return doc


def parse_identity(raw: bytes) -> dict:
    doc = strict_loads(raw, MAX_IDENTITY_BYTES)
    eng = doc.get("engine")
    if doc.get("schema") != IDENTITY_SCHEMA or set(doc) != {"schema", "engine", "protocol", "operations"} \
            or not isinstance(eng, dict) or set(eng) != {"source_commit_sha", "binary_sha256", "semantic_profiles"}:
        raise ContractError("IDENTITY_SHAPE")
    if not (isinstance(eng["source_commit_sha"], str) and COMMIT.match(eng["source_commit_sha"])
            and isinstance(eng["binary_sha256"], str) and SHA256.match(eng["binary_sha256"])
            and isinstance(eng["semantic_profiles"], list)):
        raise ContractError("IDENTITY_VALUES")
    if doc["protocol"] not in ({"request": REQUEST_SCHEMA, "result": RESULT_SCHEMA},
                               {"request": REQUEST_SCHEMA, "result": RESULT_SCHEMA, "domain": DOMAIN_SCHEMA}):
        raise ContractError("PROTOCOL_MISMATCH", json.dumps(doc["protocol"])[:200])
    ops = doc["operations"]
    if not isinstance(ops, dict) or not all(isinstance(k, str) and v in ("SUPPORTED", "UNSUPPORTED")
                                            for k, v in ops.items()):
        raise ContractError("IDENTITY_OPERATIONS")
    return doc


def canonical_bytes(doc: dict) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(p: Path) -> str:
    return sha256_file(Path(p))


def build_request(*, request_id: str, operation: str, engine: dict, binding: dict, intents: list[dict],
                  **extra_inputs: str) -> tuple[dict, bytes]:
    """A schema-valid request and its canonical bytes; anything the schema refuses is refused here, before any
    process starts."""
    doc = {"schema": REQUEST_SCHEMA, "request_id": request_id, "operation": operation,
           "expected_engine": {k: engine[k] for k in ("source_commit_sha", "binary_sha256", "semantic_profile")},
           "binding": binding, "inputs": {"semantic_intents": intents, **extra_inputs}}
    _require("request", doc)
    raw = canonical_bytes(doc)
    if len(raw) > MAX_REQUEST_BYTES:
        raise ContractError("OVERSIZED", f"request {len(raw)} bytes")
    return doc, raw
