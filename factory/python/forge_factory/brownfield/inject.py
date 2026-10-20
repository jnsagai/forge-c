"""delivery_inject (US2, FR-007): the delivered code enters the workspace only after SWE.1 is frozen and inspected.

Deterministic node between the SWE.1 inspection gate and SWE.2. It refuses to run unless the SWE.1 gate is PASS,
re-checks every stored file against its intake fingerprint, writes the files read-only into the workspace, commits
them, and records which frozen SWE.1 baseline the injection followed - the evidence that the requirements were
written without the code."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..common import pretty_json, sha256_bytes, utc_now
from . import DELIVERY_DIR, is_brownfield, manifest_of
from . import delivery as D


def inject(ws: Path) -> dict:
    """Returns {"status": "INJECTED"|"ALREADY_INJECTED"|"REFUSED", "issues": [...], ...}."""
    from ..inspection.engine import Store

    ws = Path(ws)
    m = manifest_of(ws)
    if not is_brownfield(m):
        return {"status": "REFUSED", "issues": ["NOT_A_BROWNFIELD_WORK_ORDER"]}
    rec_path = ws / DELIVERY_DIR / "injection.json"
    if rec_path.is_file():
        return {"status": "ALREADY_INJECTED", "issues": [], **json.loads(rec_path.read_text())}
    st = Store(ws)
    issues = []
    if st.gate("SWE.1").get("decision") != "PASS":
        issues.append(f"SWE1_NOT_PASSED:{st.gate('SWE.1').get('decision')}")
    base = st.latest_baseline("SWE.1")
    if not base:
        issues.append("SWE1_NOT_FROZEN")
    wo = m["work_order"]
    files = D.stored(wo)
    expected = {d["path"]: d["sha256"] for d in m.get("delivered") or []}
    for rel, sha in expected.items():
        if rel not in files:
            issues.append(f"DELIVERY_STORE_MISSING:{rel}")
        elif sha256_bytes(files[rel]) != sha:
            issues.append(f"DELIVERY_STORE_MISMATCH:{rel}")
    present = [rel for rel in expected if (ws / rel).exists()]
    issues += [f"DELIVERED_PATH_ALREADY_IN_WORKSPACE:{rel}" for rel in present]
    if issues:
        return {"status": "REFUSED", "issues": issues}
    for rel in expected:
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(files[rel])
        # FROZEN: read-only on disk as well as by policy; FIX_ALLOWED: policy opens a file only for an IN_FIX defect
        p.chmod(0o644 if m.get("code_mode") == "FIX_ALLOWED" and rel.startswith("software/") else 0o444)
    (ws / DELIVERY_DIR).mkdir(parents=True, exist_ok=True)
    store = D.store_dir(wo)
    for name in ("intake.json", "scope.json"):
        shutil.copyfile(store / name, ws / DELIVERY_DIR / name)
    rec = {"schema": "forge-c/delivery-injection/0.1", "swe1_baseline_id": base["baseline_id"],
           "swe1_baseline_hash": base["baseline_hash"], "injected_at": utc_now(),
           "files": [d for d in m.get("delivered") or []]}
    rec_path.write_text(pretty_json(rec))
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=factory@forge-c.local", "-c", "user.name=forge-factory", "commit", "-qm",
                    f"forge: delivered code injected after SWE.1 baseline {base['baseline_id']}"], cwd=ws, check=True,
                   capture_output=True)
    return {"status": "INJECTED", "issues": [], **rec}
