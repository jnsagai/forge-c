"""Reviewer worksheet for the ISO 26262-6:2018 method catalog (reconciliation plan step 2, machine-assisted).

Reads the owner-registered copy (FORGE_ISO26262_6_2018_PATH, outside the repository) and extracts, per method table,
ONLY the row identifiers and their A/B/C/D rating symbols (++, +, o). No clause, row or footnote text is stored or
printed. It compares them with the working catalog and proposes, per table, the `rows` a human reviewer can confirm
through catalog.reconcile(). It never reconciles anything itself: the reviewer signs each table.
Limits: the copy is an OCR text conversion; a row whose ratings cannot be read is reported UNPARSED, never guessed.
Footnotes, alternatives/combination rules and applicability notes are NOT extracted: the reviewer checks them.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ..common import pretty_json, utc_now
from . import catalog, normative

SYM = r"(\+\+|\+|o)"
ROW = re.compile(rf"^(\d{{1,2}}[a-z])\b(.*?)\s+{SYM}\s+{SYM}\s+{SYM}\s+{SYM}\s*$")
ROW_START = re.compile(r"^(\d{1,2}[a-z])\s+\S")
TAIL = re.compile(rf"\s{SYM}\s+{SYM}\s+{SYM}\s+{SYM}\s*$")
HEAD = re.compile(r"^Table ([A-Z]\.\d+|\d{1,2})(?: —| -|\s*\(continued\))")  # annex tables (C.1 ...) end a table


DUPLICATES: list[str] = []


def parse(text: str) -> dict[int, dict[str, dict[str, str]]]:
    tables: dict[int, dict[str, dict[str, str]]] = {}
    cur, pending = None, None
    DUPLICATES.clear()
    for raw in text.splitlines():
        line = " ".join(raw.replace("|", " ").split())  # Tables 13-15 are OCR'd as markdown tables
        h = HEAD.match(line)
        if h:
            cur, pending = (int(h.group(1)) if h.group(1).isdigit() else None), None
            if cur is not None:
                tables.setdefault(cur, {})
            continue
        if cur is None or not 1 <= cur <= 15:
            continue
        m = ROW.match(line)
        if m:
            if tables[cur].get(m.group(1)):  # never overwrite: a second row with the same id is a parse problem
                DUPLICATES.append(f"T{cur}:{m.group(1)}")
                continue
            tables[cur][m.group(1)] = dict(zip("ABCD", m.groups()[2:6], strict=True))
            pending = None
            continue
        s = ROW_START.match(line)
        if s:  # a row whose name wraps: the ratings end a following line
            pending = s.group(1)
            tables[cur].setdefault(pending, {})
            continue
        t = TAIL.search(line)
        if pending and t:
            tables[cur][pending] = dict(zip("ABCD", t.groups(), strict=True))
            pending = None
    return tables


def worksheet(cat: dict, src: dict[int, dict[str, dict[str, str]]], source_sha: str) -> dict:
    out, total_b = {}, 0
    for t in range(1, 16):
        rows = src.get(t, {})
        parsed = {r: v for r, v in rows.items() if v}
        unparsed = sorted(r for r, v in rows.items() if not v)
        b_hr = sorted(r for r, v in parsed.items() if v["B"] == "++")
        total_b += len(b_hr)
        cat_rows = {m["row"]: m["method_id"] for m in cat["methods"] if m["table"] == t}
        findings, proposal = [], {}
        for row, mid in sorted(cat_rows.items()):
            v = parsed.get(row)
            if v is None:
                findings.append(f"ROW_NOT_FOUND_OR_UNPARSED:{mid}")
                continue
            proposal[mid] = v
            if v["B"] != "++":
                findings.append(f"CATALOG_ROW_NOT_B_HIGHLY_RECOMMENDED:{mid}:B={v['B']}")
        findings += [f"B_HIGHLY_RECOMMENDED_MISSING_FROM_CATALOG:T{t}:{r}" for r in b_hr if r not in cat_rows]
        out[t] = {"source_rows": len(rows), "parsed_rows": len(parsed), "unparsed_rows": unparsed,
                  "source_b_highly_recommended": b_hr, "catalog_rows": sorted(cat_rows),
                  "findings": findings, "proposed_rows_for_reconcile": proposal,
                  "state": "MATCHES_CATALOG" if not findings and not unparsed else "REVIEW_FINDINGS"}
    return {"schema": "forge-c/easa-normative-worksheet/0.1", "generated_at": utc_now(),
            "edition": normative.EDITION, "source_sha256": source_sha, "catalog_digest": catalog.digest(cat),
            "catalog_entries": len(cat["methods"]), "source_b_highly_recommended_total": total_b, "tables": out,
            "duplicate_rows_ignored": list(DUPLICATES),
            "not_extracted": ["footnotes", "alternatives/combination rules", "applicability notes", "row text"],
            "status": "AWAITING_HUMAN_REVIEWER",
            "note": "Machine-extracted from an OCR text copy; identifiers and rating symbols only. A table becomes "
                    "RECONCILED only through catalog.reconcile() signed by a named human reviewer."}


def sign(ws: dict, reviewer: str, competence_ref: str, tables: list[int], store=None, out_dir: Path | None = None) -> list[dict]:
    """Submit the reviewer's confirmation of whole tables through catalog.reconcile(); every accepted table writes a
    new derived catalog version (append-only). Refuses a worksheet made from another source copy, and a table the
    worksheet did not find identical to the catalog (the reviewer resolves those findings first)."""
    out_dir = out_dir or catalog.DERIVED_DIR
    cat = catalog.load()
    acc = normative.standard_access()
    decisions = []
    for t in tables:
        w = ws["tables"].get(str(t)) or ws["tables"].get(t) or {}
        pre = []
        if ws.get("source_sha256") != acc.get("sha256"):
            pre.append("WORKSHEET_FROM_OTHER_SOURCE")
        if w.get("state") != "MATCHES_CATALOG":
            pre.append(f"WORKSHEET_FINDINGS_OPEN:T{t}")
        if pre:
            decisions.append({"table": t, "decision": "REJECTED", "issues": pre})
            continue
        new, dec = catalog.reconcile(cat, {"table": t, "edition": normative.EDITION,
                                           "licensed_source_sha256": acc["sha256"], "reviewer_id": reviewer,
                                           "reviewer_competence_ref": competence_ref,
                                           "rows": w["proposed_rows_for_reconcile"],
                                           "note": f"reviewed with worksheet {ws.get('generated_at')}"}, store)
        decisions.append(dec)
        if new is not None:
            new["reconciled_against_sha256"] = acc["sha256"]
            cat = new
            out_dir.mkdir(parents=True, exist_ok=True)
            n = len(list(out_dir.glob("catalog-v*.json"))) + 1
            (out_dir / f"catalog-v{n:02d}.json").write_text(pretty_json(new))
    return decisions


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.assurance.norm_worksheet")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    acc = normative.standard_access()
    if acc["licensed_copy"] != "REGISTERED":
        print(json.dumps(acc))
        return 2
    import os

    ws = worksheet(catalog.load(), parse(Path(os.environ[normative.ENV]).read_text(errors="replace")), acc["sha256"])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(ws))
    for t, v in ws["tables"].items():
        print(f"T{t:<2} {v['state']:16} parsed {v['parsed_rows']}/{v['source_rows']} B++ {len(v['source_b_highly_recommended'])} "
              f"catalog {len(v['catalog_rows'])} findings {v['findings'][:3]}")
    print(f"source B++ total {ws['source_b_highly_recommended_total']} vs catalog {ws['catalog_entries']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
