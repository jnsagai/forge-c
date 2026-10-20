"""verify_delivery (FR-006, FR-013, FR-014): the delivered files in the workspace against their intake fingerprints.

FROZEN: any difference is a MISMATCH (BLOCKED). FIX_ALLOWED: a changed delivered code file is CHANGED_BY_FIX only
when a CODE defect that targets that file is FIXED/VERIFIED (or IN_FIX during the fix loop); otherwise MISMATCH. The
change report lists each changed file with its defects, original and corrected fingerprints and a unified diff."""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from ..common import pretty_json, sha256_bytes, utc_now
from . import DELIVERY_DIR, code_mode, is_brownfield, manifest_of
from . import delivery as D

FIX_STATES = ("IN_FIX", "FIXED", "VERIFIED")


def _code_defects(ws: Path) -> list[dict]:
    out = []
    for p in sorted((Path(ws) / ".forge-run/defects").glob("DEF-*.json")):
        try:
            d = json.loads(p.read_text())
        except ValueError:
            continue
        if d.get("kind") == "CODE":
            out.append(d)
    return out


def _defect_files(d: dict) -> set[str]:
    """Delivered files a CODE defect names (location `file:line`, or any evidence path)."""
    txt = json.dumps({k: d.get(k) for k in ("location", "evidence_refs", "summary", "files")})
    return set(re.findall(r"software/(?:ll|hal|src)/[A-Za-z0-9_.-]+\.[ch]", txt))


def verify(ws: Path, step: str) -> dict:
    ws = Path(ws)
    m = manifest_of(ws)
    if not is_brownfield(m):
        return {"status": "NOT_APPLICABLE", "issues": []}
    mode = code_mode(m)
    store = D.stored(m["work_order"])
    defects = _code_defects(ws)
    rows, changes, issues = [], [], []
    for d in m.get("delivered") or []:
        rel, exp = d["path"], d["sha256"]
        p = ws / rel
        act = sha256_bytes(p.read_bytes()) if p.is_file() else None
        if act == exp:
            rows.append({"path": rel, "expected": exp, "actual": act, "status": "UNCHANGED"})
            continue
        if act is None:
            rows.append({"path": rel, "expected": exp, "actual": None, "status": "MISSING"})
            issues.append(f"DELIVERY_FILE_MISSING:{rel}")
            continue
        fixing = [x["id"] for x in defects if x.get("status") in FIX_STATES and rel in _defect_files(x)]
        ok = mode == "FIX_ALLOWED" and d["role"] == "delivered_code" and fixing
        rows.append({"path": rel, "expected": exp, "actual": act, "status": "CHANGED_BY_FIX" if ok else "MISMATCH",
                     "defects": fixing})
        if not ok:
            issues.append(f"DELIVERY_MISMATCH:{rel}" + ("" if mode == "FIX_ALLOWED" else " (FROZEN)"))
            continue
        old = store.get(rel, b"").decode("utf-8", errors="replace").splitlines(keepends=True)
        new = p.read_text(errors="replace").splitlines(keepends=True)
        changes.append({"path": rel, "defects": fixing, "original_sha256": exp, "corrected_sha256": act,
                        "diff": "".join(difflib.unified_diff(old, new, f"delivered/{rel}", f"corrected/{rel}"))})
    status = "MISMATCH" if issues else ("CHANGED_BY_FIX" if changes else "UNCHANGED")
    rec = {"schema": "forge-c/delivery-verification/0.1", "step": step, "checked_at": utc_now(), "code_mode": mode,
           "status": status, "files": rows}
    d_ = ws / DELIVERY_DIR
    d_.mkdir(parents=True, exist_ok=True)
    (d_ / f"verification-{step}.json").write_text(pretty_json(rec))
    if mode == "FIX_ALLOWED":
        (d_ / "change_report.json").write_text(pretty_json({"schema": "forge-c/change-report/0.1",
                                                            "code_mode": mode, "changes": changes}))
    return {"status": status, "issues": issues, "changes": changes, "files": rows}
