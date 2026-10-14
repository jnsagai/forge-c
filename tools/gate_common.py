"""Shared, fail-closed helpers for Forge-C evidence gates. Standard library only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDERS = {"", "TBD", "REPLACE", "NOT_MEASURED", "NOT_RUN", "unknown", "null"}


def read_json(path: str | Path) -> dict[str, Any]:
    filename = Path(path)
    try:
        obj = json.loads(filename.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unable to load JSON {filename}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"{filename}: expected a JSON object")
    return obj


def good(value: Any) -> bool:
    return isinstance(value, str) and value.strip() not in PLACEHOLDERS and not value.startswith(("TBD_", "REPLACE_"))


def positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def checked_file(path: str, sha256: str, root: Path = PROJECT_ROOT) -> str | None:
    """Verify contained nonempty evidence file and exact SHA-256; return error or None."""
    if not good(path) or not good(sha256):
        return "missing path or SHA256"
    anchor = root.resolve()
    try:
        evidence = (anchor / path).resolve()
        evidence.relative_to(anchor)
    except ValueError:
        return f"evidence path escapes root: {path}"
    if not evidence.is_file() or evidence.stat().st_size == 0:
        return f"missing or empty evidence file: {path}"
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    if digest.lower() != sha256.lower():
        return f"SHA256 mismatch: {path}"
    return None


def emit(errors: list[str], success_label: str) -> int:
    if errors:
        print("RELEASE_BLOCKED")
        for err in errors:
            print(" -", err)
        return 1
    print(success_label)
    return 0
