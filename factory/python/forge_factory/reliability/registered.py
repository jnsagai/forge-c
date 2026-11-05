"""Durable, qualified staged prevention tests; never replace protected global oracles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def prevention(store) -> tuple[dict, list[str]]:
    tests, issues = {}, []
    root = store.path.parent / "review-artifacts/reproducers"
    with store.conn() as connection:
        rows = connection.execute("SELECT DISTINCT l.ref FROM cre_prevention_tests p JOIN cre_capa c ON c.capa_id=p.capa_id "
            "JOIN cre_capa_links l ON l.capa_id=c.capa_id AND l.kind='REVIEW_REPRODUCER' "
            "WHERE c.root_cause_status='VERIFIED' AND c.state IN ('PREVENTION_TESTED','EFFECTIVENESS_OBSERVING','EFFECTIVE') "
            "ORDER BY l.ref LIMIT 4097").fetchall()
    if len(rows) > 4096:
        return {}, ["REGISTERED_PREVENTION_BOUND_EXCEEDED"]
    for row in rows:
        try:
            name, sha = row[0].rsplit("#sha256=", 1)
            path = Path(name)
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("path")
            if path.stat().st_size > 65536:
                raise ValueError("descriptor bound")
            raw = path.read_bytes()
            if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError("descriptor")
            record = json.loads(raw)
            if not str(record["id"]).startswith("AFO-"):
                continue  # protected global RPRs keep their existing manifest authority
            script = path.parent / "reproducer.py"
            if (script.is_symlink() or script.stat().st_size > 2 * 1024 * 1024
                    or hashlib.sha256(script.read_bytes()).hexdigest() != record["sha256"]):
                raise ValueError("script")
            entry = {**record, "path": str(script)}
            if record["id"] in tests and tests[record["id"]] != entry:
                raise ValueError("identity conflict")
            tests[record["id"]] = entry
        except (OSError, ValueError, KeyError, TypeError):
            issues.append("REGISTERED_PREVENTION_INVALID")
    return tests, issues
