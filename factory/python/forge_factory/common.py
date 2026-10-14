"""Shared deterministic helpers: paths, hashing, canonical JSON, UTC time, IDs."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(os.environ.get("FORGE_REPO_ROOT") or Path(__file__).resolve().parents[3])
CONFIG_DIR = REPO_ROOT / "config" / "factory"
CONTRACTS_DIR = REPO_ROOT / "specs" / "002-self-healing-factory" / "contracts"
KPI_CONTRACTS_DIR = REPO_ROOT / "specs" / "003-manufacturing-kpis" / "contracts"
DEFAULT_DATA_ROOT = Path("/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c")


def data_root() -> Path:
    return Path(os.environ.get("FORGE_DATA_ROOT") or DEFAULT_DATA_ROOT)


def state_dir() -> Path:
    return Path(os.environ.get("FORGE_STATE_DIR") or data_root() / "state")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj: Any) -> bytes:
    """Deterministic serialization used for hashing and checksum-ready snapshots."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.match(value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return value


def load_yaml(path: Path) -> Any:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_schema(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def validator_for(schema_name: str):
    from jsonschema import Draft202012Validator, FormatChecker

    schema = load_schema(schema_name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def schema_errors(schema_name: str, instance: Any) -> list[str]:
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:200]
            for e in validator_for(schema_name).iter_errors(instance)]


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"
