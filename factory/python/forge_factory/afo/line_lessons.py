"""M8 bounded factual capture into the existing LessonStore; no model calls or lesson self-validation.

Native identities deduplicate adoption aliases. Malformed sources remain explicit capture gaps and never
change a driver order/attempt. Proposals, validation, retraction and reference-only delivery retain the
existing knowledge governance; raw repair text is never promoted to a trusted prompt.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common import canonical_json, sha256_bytes, state_dir, utc_now
from ..knowledge import experience
from ..knowledge.store import LessonStore
from .durable import Refused
from .line_campaign import RX

CURSOR = "line_learning_capture_cursor"


def capture(store, lessons=None, *, limit=8):
    if type(limit) is not int or not 1 <= limit <= 32:
        raise Refused("LINE_LEARNING_BOUND_REQUIRED")
    root = state_dir().resolve()
    if store.path.resolve() != root / "supervisor/line-queue.sqlite3":
        raise Refused("LINE_LEARNING_STORE_SCOPE_MISMATCH")
    lessons = lessons or LessonStore()
    with store.tx() as c:
        saved = c.execute("SELECT value FROM afo_control WHERE key=?", (CURSOR,)).fetchone()
        cursor = saved[0] if saved else ""
        rows = c.execute(
            "SELECT a.* FROM afo_attempts a WHERE state IN ('SUCCEEDED','FAILED','CANCELLED','UNKNOWN') "
            "AND created_utc||attempt_id>? ORDER BY created_utc,attempt_id LIMIT ?", (cursor, limit),
        ).fetchall()
    refs, gaps = [], []
    for row in rows:
        try:
            order = store.order(row["order_id"])
            if not order or order["tenant_scope"] != "line-local":
                raise Refused("LINE_LEARNING_ORDER_SCOPE_MISMATCH")
            record = json.loads(row["record"])
            native = record.get("fabro_run_id")
            if not native:
                # An unsent/uncertain launch is a controller fact, never an invented native execution.
                identity = "line-attempt:" + row["attempt_id"]
                digest = sha256_bytes(canonical_json(record))
                refs.append(experience.capture(lessons, identity, "JOB", row["state"],
                    facts={"state_record_sha256": digest, "native_run": "NOT_RECORDED"},
                    source_refs=["afo-attempt:sha256:" + digest], cohort={"line": "local"}))
                continue
            wo = order["request_id"]
            if not RX["wo"].fullmatch(wo):
                raise Refused("LINE_LEARNING_SOURCE_NAME_INVALID")
            workspace = (root / "workorders" / wo / "workspace").resolve()
            manifest_path = workspace / ".forge-run/manifest.json"
            if (not workspace.is_relative_to(root / "workorders")
                    or not manifest_path.resolve().is_relative_to(workspace)):
                raise Refused("LINE_LEARNING_SOURCE_PATH_ESCAPE")
            raw = manifest_path.read_bytes()
            manifest = json.loads(raw)
            if manifest.get("work_order") != wo:
                raise Refused("LINE_LEARNING_SOURCE_IDENTITY_MISMATCH")
            digest = sha256_bytes(raw)
            cohort = experience.evaluation_scope({"line": "local", "revision": manifest.get("factory_revision"),
                                                  "model_profile": manifest.get("local_profile")}, manifest)
            refs.append(experience.capture(lessons, native, "JOB", row["state"],
                facts={"package_status": record.get("terminal_package_status"), "outcome_scope": "ONE_M3_ATTEMPT",
                       "phase_reference_provenance": {"work_order": wo, "manifest_sha256": digest}},
                source_refs=["native-run:" + native, "manifest:sha256:" + digest], cohort=cohort))
            refs.extend(experience.capture_workspace(lessons, workspace, native))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Keep telemetry failure separate from manufacturing control: no item_failure/queue transition.
            gaps.append({"attempt_id": row["attempt_id"], "code": getattr(exc, "code", type(exc).__name__)})
    with store.tx() as c:
        if rows:
            last = rows[-1]
            c.execute("INSERT INTO afo_control VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE "
                      "SET value=excluded.value,updated_utc=excluded.updated_utc",
                      (CURSOR, last["created_utc"] + last["attempt_id"], utc_now(), "line-learning-capture"))
        else:
            c.execute("DELETE FROM afo_control WHERE key=?", (CURSOR,))
    dispositions = experience.consolidate(lessons, limit=limit, inference_budget=0)
    return {"schema": "forge-c/line-learning-capture/1", "status": "CAPTURE_GAPS" if gaps else "OBSERVED",
            "processed_attempts": len(rows), "experience_refs": sorted(set(refs)), "gaps": gaps,
            "dispositions": dispositions, "model_calls": 0, "new_lessons": 0,
            "lesson_validation": "EXISTING_INDEPENDENT_KNOWLEDGE_GOVERNANCE_ONLY"}
