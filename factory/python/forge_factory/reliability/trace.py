"""CRE-T041 — FR -> task -> acceptance test -> executed test -> evidence matrix for feature 004 (AT-038).

Generated only from tasks.md and the recorded evidence (evidence/v0.4/runs/<task>/latest.json): a requirement is
COVERED when at least one of its tasks has a passing evidence record; an unmet P0 requirement is BLOCKED. The
planned crosswalk (planned-traceability.csv) is kept unchanged; the actual matrix is traceability.csv.
"""
from __future__ import annotations

import csv
import io
import json
import re

from ..common import REPO_ROOT
from ..report import FEATURES, cre_matrix

FEATURE = FEATURES["004"]


def task_tests() -> dict[str, dict]:
    out = {}
    for line in (FEATURE / "tasks.md").read_text().splitlines():
        m = re.match(r"^- \[[ X]\] \*\*(CRE-T\d{3})", line)
        if not m:
            continue
        ev = REPO_ROOT / "evidence/v0.4/runs" / m.group(1) / "latest.json"
        rec = json.loads(ev.read_text()) if ev.is_file() else None
        cmd = rec["command"] if rec else []
        out[m.group(1)] = {"acceptance": sorted(set(re.findall(r"AT-\d{3}", line))),
                           "test": next((c for c in cmd if c.endswith(".py")), None),
                           "selection": cmd[cmd.index("-k") + 1] if "-k" in cmd else None,
                           "evidence": f"evidence/v0.4/runs/{m.group(1)}/latest.json" if rec else None,
                           "status": rec["status"] if rec else "NOT_RUN",
                           "log_sha256": rec["log_sha256"] if rec else None}
    return out


def rows() -> list[dict]:
    tasks, frs, _gaps = cre_matrix()
    tt = task_tests()
    out = []
    for fr in frs:
        ts = fr["tasks"]
        out.append({"requirement_id": fr["fr"], "priority": fr["priority"], "tasks": "|".join(ts),
                    "passing_tasks": "|".join(fr["passing_tasks"]),
                    "acceptance_tests": "|".join(sorted({a for t in ts for a in tt.get(t, {}).get("acceptance", [])})),
                    "tests": "|".join(sorted({f"{tt[t]['test']}::{tt[t]['selection'] or '*'}" for t in fr["passing_tasks"]
                                              if tt.get(t, {}).get("test")})),
                    "evidence": "|".join(tt[t]["evidence"] for t in fr["passing_tasks"] if tt.get(t, {}).get("evidence")),
                    "status": fr["status"]})
    return out


def render_csv() -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["requirement_id", "priority", "tasks", "passing_tasks", "acceptance_tests",
                                        "tests", "evidence", "status"], lineterminator="\n")
    w.writeheader()
    for r in rows():
        w.writerow(r)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    (FEATURE / "traceability.csv").write_text(render_csv())
    rs = rows()
    blocked = [r["requirement_id"] for r in rs if r["status"] != "COVERED"]
    print(f"CRE traceability: {len(rs) - len(blocked)}/{len(rs)} requirements covered by passing evidence; "
          f"not covered: {blocked or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
