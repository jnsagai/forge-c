#!/usr/bin/env python3
"""Read-only acceptance checks for Spec Kit tasks whose evidence is a merged PR, a ticked sibling feature or a
sealed package set (run through forge_factory.evidence_run so the result is a recorded, hashed evidence file).

  scripts/task_checks.py pr-merged <N>      PR N is merged and its merge commit is on origin/main
  scripts/task_checks.py kpi-tasks          every 003 KPI task is ticked with PASS evidence
  scripts/task_checks.py iwdg-port          001 T-019: IWDG LL + HAL review packages READY, no RCC identifier in
                                            their code, SWE.1 cites only RM0486 chapter 59 pages; archives unchanged

Exit 0 = PASS. Never writes anything.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IWDG_PACKAGES = ("WO-0009A-STM32N6-IWDG-LL-rc1", "WO-0009B-STM32N6-IWDG-HAL-h005")
IWDG_PAGES = range(2979, 2995)  # RM0486 Rev 4 chapter 59 (IWDG)


def _run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)


def pr_merged(number: str) -> list[tuple[str, bool]]:
    pr = json.loads(_run("gh", "api", f"repos/jnsagai/forge-c/pulls/{number}").stdout or "{}")
    sha = pr.get("merge_commit_sha") or ""
    _run("git", "fetch", "-q", "origin", "main")
    on_main = bool(sha) and _run("git", "merge-base", "--is-ancestor", sha, "origin/main").returncode == 0
    print(f"PR #{number}: {pr.get('title', '')[:80]} merged_at={pr.get('merged_at')} merge_commit={sha[:12]}")
    return [("merged", bool(pr.get("merged"))), ("merge commit on origin/main", on_main)]


def _evidence_pass(ref: str) -> bool:
    try:
        rec = json.loads((ROOT / ref).read_text())
    except (OSError, ValueError):
        return False
    return rec.get("status") == "PASS" and rec.get("exit_code") == 0


def kpi_tasks() -> list[tuple[str, bool]]:
    text = (ROOT / "specs/003-manufacturing-kpis/tasks.md").read_text()
    rows = re.findall(r"^- \[([ xX])\] \*\*(KPI-T\d{3})\b(.*)$", text, re.M)
    out = [("20 KPI tasks listed", len(rows) == 20)]
    for box, tid, rest in rows:
        refs = re.findall(r"`(evidence/v0\.4/runs/[^`]+/latest\.json)`", rest)
        out.append((f"{tid} ticked with PASS evidence", box != " " and bool(refs) and all(map(_evidence_pass, refs))))
    return out


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def iwdg_port() -> list[tuple[str, bool]]:
    archives = Path(os.environ.get("FORGE_DATA_ROOT", "")) / "archives"
    out = []
    for wo in IWDG_PACKAGES:
        z_path = archives / wo / f"forge-c-{wo}-review.zip"
        if not z_path.is_file():
            out.append((f"{wo} archive present", False))
            continue
        before = _sha256(z_path)
        side = (z_path.parent / (z_path.name + ".sha256")).read_text().split()[0]
        with zipfile.ZipFile(z_path) as z:
            man = json.loads(z.read("manifest.json"))
            code = [n for n in z.namelist() if re.match(r"evidence/software/(src|ll|hal|include)/.*\.[ch]$", n)]
            rcc = [n for n in code if re.search(rb"\bRCC", z.read(n))]
            pages = {int(p) for p in re.findall(r"RM0486 p\.(\d+)",
                                               z.read("evidence/workproducts/SWE.1/software_requirements.md").decode())}
        out += [(f"{wo} READY_FOR_OFFLINE_REVIEW, 0 gaps",
                 man.get("status") == "READY_FOR_OFFLINE_REVIEW" and man.get("gap_count") == 0),
                (f"{wo} code files present ({len(code)})", bool(code)),
                (f"{wo} no RCC identifier in code {rcc}", not rcc),
                (f"{wo} SWE.1 cites only RM0486 ch. 59 pages {sorted(pages)}", bool(pages) and pages <= set(IWDG_PAGES)),
                (f"{wo} archive hash matches its .sha256 and is unchanged", before == side == _sha256(z_path))]
    return out


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("pr-merged", "kpi-tasks", "iwdg-port"):
        sys.exit(__doc__)
    res = pr_merged(argv[1]) if argv[0] == "pr-merged" else kpi_tasks() if argv[0] == "kpi-tasks" else iwdg_port()
    for name, ok in res:
        print(("PASS " if ok else "FAIL ") + name)
    ok = all(v for _, v in res)
    print("STATUS", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
