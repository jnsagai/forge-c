"""AFO-T072 (AFO-FR-006/071; AT-065/066) - acceptance report: every AT of acceptance-tests.md with the tasks that
cite it (planned-traceability.csv), their evidence status (status.report: executed evidence + blocker register) and
the FRs it verifies. An AT is PASS only when every citing task is PASS; any BLOCKED task makes it BLOCKED, any
PARTIAL makes it PARTIAL, otherwise NOT_RUN. Nothing is inferred from tasks.md boxes or from prose.

    python -m forge_factory.afo.acceptance        # writes evidence/afo/acceptance-report.json + docs/afo/ACCEPTANCE-AFO.md
"""
from __future__ import annotations

import json
import re
import sys

from ..common import REPO_ROOT, pretty_json, utc_now
from . import status

SPEC = REPO_ROOT / "specs/005-autonomous-factory-operations"
OUT_JSON = REPO_ROOT / "evidence/afo/acceptance-report.json"
OUT_MD = REPO_ROOT / "docs/afo/ACCEPTANCE-AFO.md"


def report() -> dict:
    rep = status.report()
    ats = dict(re.findall(r"^- \*\*(AT-\d{3}) — ([^:*]+):", (SPEC / "acceptance-tests.md").read_text(), re.M))
    out = []
    for at, title in sorted(ats.items()):
        tasks = {t: v["status"] for t, v in rep["tasks"].items() if at in v["planned_test_refs"].split(";")}
        frs = sorted(r["id"] for r in rep["requirements"] if at in r["acceptance"])
        st = set(tasks.values())
        verdict = ("NOT_RUN" if not tasks else "PASS" if st == {"PASS"} else "BLOCKED" if "BLOCKED" in st
                   else "PARTIAL" if ("PARTIAL" in st or "PASS" in st) else "NOT_RUN")
        out.append({"at": at, "title": title.strip(), "verdict": verdict, "tasks": tasks, "requirements": frs})
    counts = {v: sum(x["verdict"] == v for x in out) for v in ("PASS", "PARTIAL", "BLOCKED", "NOT_RUN")}
    return {"schema": "forge-c/afo-acceptance/0.1", "generated_utc": utc_now(), "acceptance": out, "counts": counts,
            "task_counts": rep["task_counts"], "fr_counts": rep["fr_counts"],
            "statement": "Derived from executed evidence and the blocker register only. BLOCKED/PARTIAL/NOT_RUN are "
                         "reported as such; no compliance, safety approval or production-readiness claim."}


def markdown(r: dict) -> str:
    c = ", ".join(f"{k} {v}" for k, v in r["counts"].items())
    lines = ["# Feature 005 (AFO) acceptance report - generated", "", f"Generated {r['generated_utc']}. {r['statement']}",
             "", f"Acceptance tests: {c}. Tasks: {r['task_counts']}. FRs: {r['fr_counts']}.", "",
             "| AT | Title | Verdict | Tasks | FRs |", "|---|---|---|---|---|"]
    lines += [f"| {x['at']} | {x['title']} | {x['verdict']} | " + ", ".join(f"{k}={v}" for k, v in x["tasks"].items())
              + f" | {', '.join(x['requirements'])} |" for x in r["acceptance"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    r = report()
    OUT_JSON.write_text(pretty_json(r))
    OUT_MD.write_text(markdown(r))
    print(json.dumps(r["counts"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
