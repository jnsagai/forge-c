"""EASA-T007 — upgrade/migration compatibility with 002/003/004/005 before any gate change: the EASA migration is
applied to a COPY of the live incident database (never the live file) and must leave every pre-existing table, index,
trigger and row count identical; existing contract schemas and policies must be byte-identical to the base revision."""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, state_dir, utc_now
from .store import AssuranceStore

FROZEN = ["specs/002-self-healing-factory/contracts", "specs/003-manufacturing-kpis/contracts",
          "specs/004-continuous-reliability-engineering/contracts", "config/factory/reliability-policy.yaml",
          "config/factory/supervisor-policy.yaml", "config/factory/trace-policy.yaml", "factory/release-manager"]


def _shape(db: Path) -> dict:
    with sqlite3.connect(db) as c:
        objs = {r[0]: r[1] for r in c.execute("SELECT name, sql FROM sqlite_master WHERE name NOT LIKE '%easa%'")}
        rows = {t: c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]  # noqa: S608 - names from sqlite_master
                for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '%easa%' "
                                      "AND name NOT LIKE 'sqlite_%'")}
    return {"objects": objs, "rows": rows}


def db_check(live: Path) -> dict:
    if not live.is_file():
        return {"status": "NOT_VERIFIABLE", "reason": f"no database at {live}"}
    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / "incidents.sqlite3"
        with sqlite3.connect(live) as src, sqlite3.connect(copy) as dst:
            src.backup(dst)  # consistent copy even while the supervisor writes (WAL)
        before = _shape(copy)
        with sqlite3.connect(copy) as c:
            had = {r[0] for r in c.execute("SELECT version FROM easa_schema_version")} if c.execute(
                "SELECT 1 FROM sqlite_master WHERE name='easa_schema_version'").fetchone() else set()
        store = AssuranceStore(copy)  # the constructor applies pending migrations
        applied = sorted(set(range(1, store.version() + 1)) - had)
        again = store.migrate()
        after = _shape(copy)
    same = before == after
    return {"status": "PASS" if same and again == [] else "FAIL", "applied_first": applied, "applied_second": again,
            "pre_existing_objects": len(before["objects"]), "unchanged": same,
            "changed": sorted(k for k in set(before["objects"]) | set(after["objects"])
                              if before["objects"].get(k) != after["objects"].get(k))}


def frozen_files_check(base: str) -> dict:
    out = subprocess.run(["git", "diff", "--name-only", base, "HEAD", "--", *FROZEN], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    return {"status": "PASS" if not out else "FAIL", "base": base, "changed": out}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.assurance.compat")
    ap.add_argument("--base", default="origin/feat/005-autonomous-factory-operations")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rep = {"schema": "forge-c/easa-compat/0.1", "generated_at": utc_now(),
           "database": db_check(state_dir() / "supervisor" / "incidents.sqlite3"),
           "frozen_files": frozen_files_check(a.base)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(rep), encoding="utf-8")
    print(f"db={rep['database']['status']} frozen_files={rep['frozen_files']['status']} {rep['frozen_files']['changed']}")
    return 0 if rep["database"]["status"] in ("PASS",) and rep["frozen_files"]["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
