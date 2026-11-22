"""Gate result records.

Pattern adapted from Forge-C tools/gate_common.py (Apache-2.0): a gate emits a structured verdict with evidence.
Here a check that could not run is NOT_RUN with a mandatory reason, and NOT_RUN is never a pass.
"""
from __future__ import annotations

from pathlib import Path

from . import __version__
from .io import sha256_file, write_json

PASS, FAIL, NOT_RUN = "PASS", "FAIL", "NOT_RUN"


def issue(code: str, message: str, target_id: str | None = None) -> dict:
    out = {"code": code, "message": message[:300]}
    if target_id:
        out["target_id"] = target_id
    return out


def result(
    gate: str,
    issues: list[dict],
    *,
    profile: str,
    integrity_level: str,
    evidence: list[Path] | None = None,
    root: Path | None = None,
    tool: dict | None = None,
    exit_code: int | None = None,
    not_run_reason: str | None = None,
) -> dict:
    if not_run_reason:
        verdict = NOT_RUN
    else:
        verdict = FAIL if issues else PASS
    root = Path(root or Path.cwd())
    ev = []
    for p in evidence or []:
        p = Path(p)
        full = p if p.is_absolute() else root / p
        if full.is_file():
            rel = full.relative_to(root) if full.is_relative_to(root) else full
            ev.append({"path": str(rel), "sha256": sha256_file(full)})
    doc = {
        "gate": gate,
        "verdict": verdict,
        "tool": tool or {"name": "forge-c-hi", "version": __version__},
        "exit_code": exit_code if exit_code is not None else (None if verdict == NOT_RUN else int(bool(issues))),
        "evidence": ev,
        "issues": issues,
        "profile": profile,
        "integrity_level": integrity_level,
    }
    if not_run_reason:
        doc["not_run_reason"] = not_run_reason
    return doc


def write(root: Path, stage: str, doc: dict) -> Path:
    return write_json(Path(root) / "hi" / stage / "gates" / f"{doc['gate']}.json", doc)
