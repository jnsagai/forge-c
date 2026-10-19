"""AFO-T059 (AFO-FR-064; AT-037/056) - AFO evidence inside the existing deterministic release package.

Only for a workspace an AFO attempt launched (attempt record workspace_ref = workorder:<WO>): the archive gets
operations/afo/ with the order, every attempt, recovery plans, checkpoints, lifecycle events, dead-letter cases and the
service/context versions (policy sha256, authorization id, store schema, factory revision), plus index.json with the
sha256 of each file. Read through a read-only store connection; never changes the package status (READY or BLOCKED
is decided by the packager gates). Work orders not launched by AFO are packaged exactly as before (no files added).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common import pretty_json, sha256_bytes, utc_now


def _w(stage: Path, rel: str, data: str) -> str:
    p = stage / "operations/afo" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data)
    return sha256_bytes(data.encode())


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows) or "\n"


def bundle_into(ws: Path, stage: Path, package_status: str) -> dict | None:
    from .dashboard_api import _table, ro

    wo = Path(ws).parent.name
    with ro() as c:
        if c is None:
            return None
        att = next((r for r in c.execute("SELECT * FROM afo_attempts").fetchall()
                    if json.loads(r["record"]).get("workspace_ref") == f"workorder:{wo}"), None)
        if att is None:
            return None
        oid = att["order_id"]
        order = dict(c.execute("SELECT * FROM afo_work_orders WHERE order_id=?", (oid,)).fetchone())
        attempts = [{**json.loads(r["record"]), "state": r["state"]} for r in c.execute(
            "SELECT * FROM afo_attempts WHERE order_id=? ORDER BY seq", (oid,))]
        plans = [dict(r) for r in c.execute("SELECT * FROM afo_recovery_plans WHERE order_id=?", (oid,))] \
            if _table(c, "afo_recovery_plans") else []
        cps = [dict(r) for r in c.execute("SELECT * FROM afo_checkpoints WHERE order_id=? ORDER BY recorded_utc", (oid,))]
        evs = [json.loads(r["record"]) for r in c.execute(
            "SELECT record FROM afo_lifecycle_events WHERE order_id=? ORDER BY seq", (oid,))]
        dlq = [json.loads(r["record"]) | {"state": r["state"]} for r in c.execute(
            "SELECT record, state FROM afo_dead_letters WHERE order_id=?", (oid,))] if _table(c, "afo_dead_letters") else []
        schema = c.execute("SELECT MAX(version) FROM afo_schema_version").fetchone()[0]
    env = json.loads(order.pop("envelope"))
    files = {
        "order.json": _w(stage, "order.json", pretty_json({**order, "envelope": {k: env.get(k) for k in (
            "request_id", "driver_class", "target", "safety_scope", "model_profile", "manifest_sha256",
            "input_manifest_ref", "approved_by", "authorization_ref")}})),
        "attempts.jsonl": _w(stage, "attempts.jsonl", _jsonl(attempts)),
        "recovery-plans.jsonl": _w(stage, "recovery-plans.jsonl", _jsonl(plans)),
        "checkpoints.jsonl": _w(stage, "checkpoints.jsonl", _jsonl(cps)),
        "lifecycle-events.jsonl": _w(stage, "lifecycle-events.jsonl", _jsonl(evs)),
        "dead-letters.jsonl": _w(stage, "dead-letters.jsonl", _jsonl(dlq)),
        "service-context.json": _w(stage, "service-context.json", pretty_json({
            "policy_sha256": order.get("policy_sha256"), "authorization_id": order.get("authorization_id"),
            "store_schema_version": schema, "factory_revisions": sorted({a.get("factory_revision") for a in attempts}),
            "fabro_run_ids": [a.get("fabro_run_id") for a in attempts], "this_attempt": att["attempt_id"]})),
    }
    idx = {"schema": "forge-c/afo-package-evidence/0.1", "order_id": oid, "attempt_id": att["attempt_id"],
           "package_status_at_bundle": package_status, "generated_utc": utc_now(), "files": files,
           "scope": "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED",
           "note": "AFO queue/recovery evidence; it never changes READY/BLOCKED (decided by the package gates)"}
    _w(stage, "index.json", pretty_json(idx))
    return idx
