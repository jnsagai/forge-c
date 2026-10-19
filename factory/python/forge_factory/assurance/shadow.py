"""EASA-T064/T065/T068 — immutable shadow audit of sealed review packages (OBSERVE_ONLY dry run).

The sealed zip is hash-verified, extracted into a throw-away directory, and every independent verifier runs on that
COPY; the archive and the original workspace are never written (the archive digest is re-checked at the end).
`tamper()` produces a copy with one introduced mismatch for the negative campaign (AT-065): the audit of the copy
must differ from the pristine audit, linked to the changed member.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from ..common import sha256_file, utc_now
from . import audit, policy
from .verifiers import run_for_phase

PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")


def _workspace_from_package(x: Path, inputs_from: Path | None) -> Path:
    """Package layout -> workspace layout the verifiers read (evidence/* -> *, evidence-raw -> evidence/raw)."""
    ws = x / "WO" / "workspace"
    shutil.copytree(x / "evidence", ws)
    if (ws / "evidence-raw").is_dir():
        (ws / "evidence").mkdir(exist_ok=True)
        shutil.move(str(ws / "evidence-raw"), str(ws / "evidence/raw"))
    if (ws / "verification/tool-results.jsonl").is_file():
        shutil.copy(ws / "verification/tool-results.jsonl", ws / "evidence/tool-results.jsonl")
    if inputs_from is not None and (inputs_from / "sections").is_dir():  # baselined RM inputs (not in the package)
        shutil.copytree(inputs_from, ws / "inputs", dirs_exist_ok=True)
    man = ws / ".forge-run/manifest.json"
    man.parent.mkdir(parents=True, exist_ok=True)
    layer = "HAL" if (ws / "software/hal").is_dir() else "LL"
    man.write_text(json.dumps({"layer": layer, "note": "reconstructed for the shadow audit"}))
    return ws


def run(zip_path: Path, inputs_from: Path | None = None, profile: str = "ENHANCED") -> dict:
    zip_path = Path(zip_path)
    before = sha256_file(zip_path)
    frozen = audit.freeze(zip_path)
    t0 = time.monotonic()
    out = {"schema": "forge-c/easa-shadow-audit/0.1", "run_id": frozen["run_id"], "archive_sha256": before,
           "started_at": utc_now(), "unknown_facts": frozen["unknown_facts"],
           "unsupported_claims": frozen["unsupported_claims"], "phases": {}}
    with tempfile.TemporaryDirectory() as td:
        x = Path(td)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(x)
        ws = _workspace_from_package(x, inputs_from)
        for ph in PHASES:
            ev = run_for_phase(ws, ph, policy.profile_requirements(profile)[ph])
            out["phases"][ph] = {req: {"status": items[0]["status"], "findings": items[0]["findings"]}
                                 for req, items in ev.items()}
    out["duration_s"] = round(time.monotonic() - t0, 1)
    out["archive_unchanged"] = sha256_file(zip_path) == before
    return out


def tamper(zip_path: Path, member: str, old: bytes, new: bytes, dst: Path) -> Path:
    """Copy of the archive with one member changed (negative campaign input). The original is only read."""
    dst = Path(dst)
    with zipfile.ZipFile(zip_path) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == member:
                assert old in data, f"{old!r} not in {member}"
                data = data.replace(old, new)
            zout.writestr(info, data)
    return dst


def diff(a: dict, b: dict) -> list[str]:
    out = []
    for ph in PHASES:
        for req in sorted(set(a["phases"].get(ph, {})) | set(b["phases"].get(ph, {}))):
            x, y = a["phases"].get(ph, {}).get(req), b["phases"].get(ph, {}).get(req)
            if x != y:
                out.append(f"{ph}:{req}:{(x or {}).get('status')}->{(y or {}).get('status')}")
    return out
