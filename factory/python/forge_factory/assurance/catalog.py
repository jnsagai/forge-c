"""EASA-T008/T009/T070 — versioned ISO 26262-6 method registry (47-entry ASIL B `++` PROVISIONAL working index).

`validate()` fails closed on a structurally wrong index (e.g. 46 entries, duplicate ids, table counts that do not
add up, a Table 12 `++`, any entry presented as normatively checked). `reconcile()` is the ONLY way to change a
rating: it needs a registered licensed copy (sha256), a reviewer id and competence reference, and covers one whole
table; anything else is rejected and recorded. The authored spec file is never modified: reconciled catalogs are
new derived versions held in the assurance store.
"""
from __future__ import annotations

import copy
from typing import Any

from ..common import canonical_json, sha256_bytes
from . import contracts
from .normative import standard_access

WORKING_STATUS = "SECONDARY_WORKING_INDEX_NOT_AUTHORIZED_STANDARD"
EXPECTED_ENTRIES = 47
TABLES = set(range(1, 16))


def load(path=None) -> dict:
    return contracts.load(path or contracts.CATALOG)


def digest(cat: dict) -> str:
    return sha256_bytes(canonical_json(cat))


def validate(cat: dict, reference_ids: list[str] | None = None) -> list[str]:
    """reference_ids: the frozen authored id list (default: the spec catalog) - absent ids are named."""
    issues: list[str] = []
    methods = cat.get("methods") or []
    inv = {x.get("table"): x for x in cat.get("table_inventory") or []}
    ids = [m.get("method_id") for m in methods]
    working = cat.get("document_status") == WORKING_STATUS
    if working and len(methods) != EXPECTED_ENTRIES:
        issues.append(f"CATALOG_COUNT_MISMATCH:{len(methods)}!={EXPECTED_ENTRIES}")
    if len(set(ids)) != len(ids):
        issues.append("DUPLICATE_METHOD_ID:" + ",".join(sorted({i for i in ids if ids.count(i) > 1})))
    if set(inv) != TABLES:
        issues.append(f"TABLE_INVENTORY_INCOMPLETE:missing={sorted(TABLES - set(inv))}")
    for m in methods:
        issues += [f"METHOD_SCHEMA:{m.get('method_id')}:{e}" for e in contracts.errors("method-record", m)]
    per_table: dict[int, int] = {}
    for m in methods:
        if (m.get("asil_recommendations") or {}).get("B") == "++":
            per_table[m["table"]] = per_table.get(m["table"], 0) + 1
    for t, x in inv.items():
        if per_table.get(t, 0) != x.get("asil_b_highly_recommended_count"):
            issues.append(f"TABLE_COUNT_MISMATCH:T{t}:{per_table.get(t, 0)}!={x.get('asil_b_highly_recommended_count')}")
    if working:
        if (inv.get(12) or {}).get("asil_b_highly_recommended_count") != 0 or per_table.get(12):
            issues.append("TABLE12_HAS_B_PLUS_PLUS")
        for m in methods:
            if m.get("normative_checked") or m.get("recommendation_source") != "SECONDARY_WORKING_INDEX":
                issues.append(f"UNRECONCILED_ENTRY_PRESENTED_AS_CHECKED:{m.get('method_id')}")
        if cat.get("owner_baseline_approval"):
            issues.append("WORKING_INDEX_CLAIMS_OWNER_APPROVAL")
    ref = reference_ids if reference_ids is not None else [m["method_id"] for m in load()["methods"]]
    return issues + [f"MISSING_METHOD_ID:{i}" for i in ref if i not in ids]


def status(cat: dict) -> str:
    methods = cat.get("methods") or []
    if methods and all(m.get("normative_checked") for m in methods) and cat.get("document_status") == "CONTROLLED_RECONCILED":
        return "RECONCILED"
    return "UNVERIFIED"


def reconcile(cat: dict, rec: dict, store=None) -> tuple[dict | None, dict]:
    """Apply one reviewer-signed reconciliation of ONE table. Returns (new catalog or None, decision record).

    rec = {table, edition, licensed_source_sha256, reviewer_id, reviewer_competence_ref,
           rows: {method_id: {A,B,C,D}}, note}
    """
    issues = []
    acc = standard_access()
    if acc["licensed_copy"] != "REGISTERED":
        issues.append(f"LICENSED_SOURCE_UNAVAILABLE:{acc['licensed_copy']}")
    elif rec.get("licensed_source_sha256") != acc["sha256"]:
        issues.append("LICENSED_SOURCE_HASH_MISMATCH")
    if rec.get("edition") != "ISO 26262-6:2018":
        issues.append(f"EDITION_MISMATCH:{rec.get('edition')}")
    if not rec.get("reviewer_id") or not rec.get("reviewer_competence_ref"):
        issues.append("REVIEWER_MISSING")
    if str(rec.get("reviewer_id", "")).lower().startswith(("agent", "ai", "llm", "swe")):
        issues.append("REVIEWER_IS_AGENT")
    table = rec.get("table")
    rows = rec.get("rows") or {}
    in_table = {m["method_id"] for m in cat.get("methods", []) if m.get("table") == table}
    if table not in TABLES or not in_table:
        issues.append(f"UNKNOWN_TABLE:{table}")
    elif set(rows) != in_table:
        issues.append(f"PARTIAL_TABLE_REVIEW:{sorted(in_table ^ set(rows))}")
    for mid, r in rows.items():
        if set(r) != {"A", "B", "C", "D"} or not set(r.values()) <= {"++", "+", "o"}:
            issues.append(f"INVALID_RATING:{mid}")
    decision = {"kind": "reconciliation", "table": table, "reviewer_id": rec.get("reviewer_id"),
                "licensed_source_sha256": rec.get("licensed_source_sha256"), "catalog_before": digest(cat),
                "decision": "REJECTED" if issues else "ACCEPTED", "issues": issues}
    new = None
    if not issues:
        new = copy.deepcopy(cat)
        for m in new["methods"]:
            if m["method_id"] in rows:
                m.update(asil_recommendations=dict(rows[m["method_id"]]), normative_checked=True,
                         recommendation_source="CONTROLLED_STANDARD", verified_reviewer_id=rec["reviewer_id"],
                         verification_ref=f"licensed:{rec['licensed_source_sha256'][:16]}:T{table}")
        for x in new["table_inventory"]:
            if x["table"] == table:
                x["status"] = "RECONCILED"
                x["asil_b_highly_recommended_count"] = sum(1 for m in new["methods"]
                                                           if m["table"] == table and m["asil_recommendations"]["B"] == "++")
        if all(x["status"] == "RECONCILED" for x in new["table_inventory"]):
            new["document_status"] = "CONTROLLED_RECONCILED"
        else:
            new["document_status"] = "PARTIALLY_RECONCILED"
        decision["catalog_after"] = digest(new)
    if store is not None:
        store.append("reconciliation", f"catalog:T{table}", decision, actor=str(rec.get("reviewer_id") or "unknown"))
    return new, decision


def change_rating_without_source(cat: dict, method_id: str, asil: str, value: str, store=None) -> dict:
    """AT-009: a direct rating edit is never applied; it is recorded and rejected."""
    rec: dict[str, Any] = {"kind": "direct_rating_change", "method_id": method_id, "asil": asil, "value": value,
                           "catalog": digest(cat), "decision": "REJECTED",
                           "issues": ["RATING_CHANGE_WITHOUT_SOURCE_CONFIRMATION"]}
    if store is not None:
        store.append("reconciliation", f"catalog:{method_id}", rec, actor="unverified-request")
    return rec
