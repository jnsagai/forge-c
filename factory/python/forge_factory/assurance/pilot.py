"""EASA-T079 / AT-094 — check a sealed review package of a real pilot work order for the owner-addendum evidence.

PASS needs all six traceability matrices (csv + md) in the package and every matrix reporting 'Uncovered items: none',
with the archive hash recorded and left unchanged (the archive is only read). Otherwise the result names the exact
failing relation. The package status (READY/BLOCKED) and its gaps are reported, never upgraded.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

from ..common import pretty_json, sha256_file, utc_now

MATRICES = ("matrix_1_swr_to_architecture", "matrix_2_unitspec_to_swr", "matrix_3_code_to_unitspec",
            "matrix_4_unittest_to_unitspec", "matrix_5_integrationtest_to_architecture", "matrix_6_validationtest_to_swr")
PREFIX = "evidence/traceability/matrices/"


def check(zip_path: Path) -> dict:
    zip_path = Path(zip_path)
    before = sha256_file(zip_path)
    rows, failing = {}, []
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        pkg = next((n for n in names if n.endswith("quality/final-gates.json")), None)
        gates = json.loads(z.read(pkg)) if pkg else {}
        for m in MATRICES:
            csv_n, md_n = PREFIX + m + ".csv", PREFIX + m + ".md"
            if csv_n not in names or md_n not in names:
                rows[m] = {"present": False}
                failing.append(f"MATRIX_MISSING:{m}")
                continue
            md = z.read(md_n).decode(errors="replace")
            csv = z.read(csv_n).decode(errors="replace").splitlines()
            unc = re.search(r"Uncovered items:\s*(.+)", md)
            uncovered = (unc.group(1).strip() if unc else "UNSTATED")
            status = {}
            for line in csv[1:]:
                st = line.rsplit(",", 1)[-1].strip()
                status[st] = status.get(st, 0) + 1
            rows[m] = {"present": True, "rows": len(csv) - 1, "status_counts": status, "uncovered": uncovered}
            if uncovered.lower() != "none":
                failing.append(f"MATRIX_UNCOVERED:{m}:{uncovered[:120]}")
    after = sha256_file(zip_path)
    return {"schema": "forge-c/easa-pilot-check/0.1", "checked_at": utc_now(), "package": zip_path.name,
            "archive_sha256": before, "archive_unchanged": before == after, "matrices": rows,
            "failing_relations": failing, "package_gates": {k: v for k, v in (gates.get("checks") or {}).items()},
            "status": "PASS" if not failing and before == after else "FAIL",
            "scope": "trace completeness of a real pilot package; not a safety or release decision"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.assurance.pilot")
    ap.add_argument("zips", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    res = {z.parent.name: check(z) for z in a.zips}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(res))
    for k, v in res.items():
        print(f"{k}: {v['status']} failing={v['failing_relations']}")
    return 0 if all(v["status"] == "PASS" for v in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
