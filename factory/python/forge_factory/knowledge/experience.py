"""Factual experience and learning dispositions in the existing LessonStore database.

No synthetic repair incidents, automatic lessons or additional inference. A changed
observation is a new immutable revision; adoption aliases share native identity.
"""

from __future__ import annotations

import json

from ..afo.durable import Refused, canonical, digest
from ..common import utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS job_experience (
 experience_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, phase TEXT NOT NULL, outcome TEXT NOT NULL,
 source_hash TEXT NOT NULL, record TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS learning_dispositions (
 experience_id TEXT PRIMARY KEY REFERENCES job_experience(experience_id), state TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS learning_history (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, experience_id TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lesson_qualifications (qualification_id TEXT PRIMARY KEY, record TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lesson_transfers (transfer_id TEXT PRIMARY KEY, kind TEXT NOT NULL, record TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS experiences_no_update BEFORE UPDATE ON job_experience BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS experiences_no_delete BEFORE DELETE ON job_experience BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END;
"""
OUTCOMES = {
    "FAIL",
    "PASS",
    "SUCCEEDED",
    "READY_FOR_OFFLINE_REVIEW",
    "FAILED",
    "BLOCKED",
    "REWORK",
    "TIMED_OUT",
    "CANCELLED",
    "CANCELED",
    "REVOKED",
    "UNKNOWN",
    "PARTIAL",
    "EXHAUSTED",
    "FAILED_PROTOCOL",
}


def capture(store, execution_id, phase, outcome, *, facts, source_refs, cohort, observed_at=None):
    from ..events.redact import redact_text

    if outcome not in OUTCOMES or not execution_id or not source_refs:
        raise Refused("EXPERIENCE_FACTUAL_SOURCE_REQUIRED")
    # Content references and compact facts only, never prompt/private source/hidden reasoning.
    clean = json.loads(redact_text(canonical(facts).decode())[0])
    body = {
        "execution_id": execution_id,
        "phase": phase,
        "outcome": outcome,
        "facts": clean,
        "source_refs": sorted(set(source_refs)),
        "cohort": cohort,
    }
    sha = digest(body)
    eid = "experience-" + sha[:24]
    rec = {
        "schema": "forge-c/job-experience/1",
        "experience_id": eid,
        **body,
        "source_hash": sha,
        "observed_at": observed_at or utc_now(),
    }
    with store._conn() as c:
        c.execute("BEGIN IMMEDIATE")
        if c.execute("SELECT 1 FROM job_experience WHERE experience_id=?", (eid,)).fetchone():
            c.execute("COMMIT")
            return eid
        c.execute(
            "INSERT INTO job_experience VALUES (?,?,?,?,?,?,?)",
            (eid, execution_id, phase, outcome, sha, canonical(rec).decode(), rec["observed_at"]),
        )
        disposition = {"state": "PENDING", "reason": "AWAITING_BOUNDED_CONSOLIDATION", "at": utc_now()}
        c.execute("INSERT INTO learning_dispositions VALUES (?,?,?)", (eid, "PENDING", canonical(disposition).decode()))
        c.execute("INSERT INTO learning_history(experience_id,record) VALUES (?,?)", (eid, canonical(disposition).decode()))
        c.execute("COMMIT")
    return eid


def consolidate(store, *, limit=32, inference_budget=0):
    if not 1 <= limit <= 128 or inference_budget < 0:
        raise Refused("LEARNING_BOUND_REQUIRED")
    out = []
    with store._conn() as c:
        c.execute("BEGIN IMMEDIATE")
        rows = c.execute(
            "SELECT e.*,d.record AS disposition FROM job_experience e JOIN learning_dispositions d USING(experience_id) WHERE d.state='PENDING' ORDER BY e.created_at,e.experience_id LIMIT ?",
            (limit,),
        ).fetchall()
        for row in rows:
            rec = json.loads(row["record"])
            facts = rec["facts"]
            pattern = facts.get("fingerprint") or facts.get("pattern")
            # Deterministic disposition is sufficient for routine capture. Novel inference needs separate admission.
            state = (
                "NO_NEW_LESSON"
                if rec["outcome"] in ("PASS", "SUCCEEDED", "READY_FOR_OFFLINE_REVIEW") and not pattern
                else "DEFERRED_BUDGET"
            )
            value = {
                "state": state,
                "reason": "FACTS_RETAINED_NO_UNSUPPORTED_GENERALIZATION"
                if state == "NO_NEW_LESSON"
                else "SEPARATE_ADMITTED_CONSOLIDATION_REQUIRED",
                "experience_id": row["experience_id"],
                "at": utc_now(),
                "inference_tokens": 0,
                "pattern": pattern,
            }
            c.execute(
                "UPDATE learning_dispositions SET state=?,record=? WHERE experience_id=?",
                (state, canonical(value).decode(), row["experience_id"]),
            )
            c.execute(
                "INSERT INTO learning_history(experience_id,record) VALUES (?,?)",
                (row["experience_id"], canonical(value).decode()),
            )
            out.append(value)
        c.execute("COMMIT")
    return out


def transfer(store, lesson_id, run_id, kind, *, evidence_refs=(), data=None):
    if kind not in ("EXPOSURE", "APPLICATION", "BENEFIT"):
        raise Refused("LEARNING_TRANSFER_KIND_INVALID")
    if kind != "EXPOSURE" and not evidence_refs:
        raise Refused("TRANSFER_INDEPENDENT_EVIDENCE_REQUIRED")
    record = {"lesson_id": lesson_id, "run_id": run_id, "kind": kind, "evidence_refs": list(evidence_refs), "data": data or {}}
    tid = "transfer-" + digest(record)[:24]
    with store._conn() as c:
        c.execute("INSERT OR IGNORE INTO lesson_transfers VALUES (?,?,?)", (tid, kind, canonical(record).decode()))
    return tid


def report(store):
    with store._conn() as c:
        experiences = c.execute("SELECT COUNT(*) FROM job_experience").fetchone()[0]
        dispositions = dict(c.execute("SELECT state,COUNT(*) FROM learning_dispositions GROUP BY state"))
        uses = dict(c.execute("SELECT kind,COUNT(*) FROM lesson_transfers GROUP BY kind"))
    return {
        "unique_experiences": experiences,
        "dispositions": dispositions,
        "exposures": uses.get("EXPOSURE", 0),
        "applications": uses.get("APPLICATION", 0),
        "measured_benefits": uses.get("BENEFIT", 0),
        "benefit_status": "UNKNOWN" if not uses.get("BENEFIT") else "REQUIRES_COMPARISON_REVIEW",
    }


def capture_afo(afo_store, lessons, workspace_of, *, limit=32):
    """Reconcile terminal native product/phase outcomes, deduplicated across adopted orders."""
    out = capture_controller_outcomes(afo_store, lessons, limit=limit)
    with afo_store.tx() as c:
        saved = c.execute("SELECT value FROM afo_control WHERE key='learning_capture_cursor'").fetchone()
        cursor = saved[0] if saved else ""
        rows = c.execute(
            "SELECT * FROM afo_attempts WHERE state IN ('SUCCEEDED','FAILED','CANCELLED','UNKNOWN') AND created_utc||attempt_id>? ORDER BY created_utc,attempt_id LIMIT ?",
            (cursor, limit),
        ).fetchall()
        if not rows:
            c.execute("DELETE FROM afo_control WHERE key='learning_capture_cursor'")
    for row in rows:
        try:
            att = {**dict(row), "record": json.loads(row["record"])}
            record = att["record"]
            native = record.get("fabro_run_id")
            if not native:
                continue  # uncertain unsent jobs need their own dispatch receipt, never a fabricated native identity
            ws = workspace_of(att)
            manifest_path = ws / ".forge-run/manifest.json"
            manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
            cohort = {"revision": manifest.get("factory_revision"), "server": record.get("fabro_server")}
            # Exclude order/adoption alias from identity. Native metadata and outcome remain factual.
            out.append(
                capture(
                    lessons,
                    native,
                    "JOB",
                    att["state"],
                    facts={"package_status": record.get("terminal_package_status")},
                    source_refs=["native-run:" + native],
                    cohort=cohort,
                )
            )
            ws = workspace_of(att)
            from ..inspection.engine import Store as InspectionStore

            for phase in ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"):
                if not ws.is_dir():
                    continue
                try:
                    records = InspectionStore(ws).inspections(phase)
                    for data in records:
                        outcome = data.get("status") or data.get("result") or data.get("verdict")
                        if outcome not in OUTCOMES:
                            continue
                        out.append(
                            capture(
                                lessons,
                                native,
                                phase,
                                outcome,
                                facts={"record_sha256": digest(data)},
                                source_refs=["inspection:sha256:" + digest(data)],
                                cohort=cohort,
                            )
                        )
                except (OSError, ValueError, TypeError):
                    continue
        except (KeyError, ValueError, TypeError, FileNotFoundError) as exc:
            from ..afo.dispatch import item_failure

            item_failure(afo_store, row["order_id"], exc, "learning_capture")
    if rows:
        last = rows[-1]
        with afo_store.tx() as c:
            c.execute(
                "INSERT INTO afo_control VALUES ('learning_capture_cursor',?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_utc=excluded.updated_utc",
                (last["created_utc"] + last["attempt_id"], utc_now(), "deterministic-learning-reconciler"),
            )
    return out


def capture_workspace(store, workspace, execution_id, *, package=None):
    """All authoritative inspection outcomes plus immutable package fact, including non-AFO work orders."""
    from pathlib import Path
    from ..inspection.engine import Store as InspectionStore

    ws = Path(workspace)
    m = ws / ".forge-run/manifest.json"
    manifest = json.loads(m.read_text()) if m.is_file() else {}
    cohort = {
        "revision": manifest.get("factory_revision"),
        "model_profile": manifest.get("local_profile"),
        "driver": manifest.get("driver"),
        "evaluation_holdout": bool(manifest.get("evaluation_holdout")),
    }
    out = []
    for phase in ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"):
        for record in InspectionStore(ws).inspections(phase):
            outcome = record.get("verdict")
            if outcome not in OUTCOMES:
                continue
            sha = digest(record)
            out.append(
                capture(
                    store,
                    execution_id,
                    phase,
                    outcome,
                    facts={
                        "inspection_record_sha256": sha,
                        "failed_items": sorted(k for k, v in record.get("items", {}).items() if v.get("verdict") == "FAIL"),
                        "successful_scope": record.get("checklist_sha256") if outcome == "PASS" else None,
                    },
                    source_refs=["inspection:sha256:" + sha],
                    cohort=cohort,
                    observed_at=record.get("recorded_at"),
                )
            )
    if package and package.get("package_status") in OUTCOMES:
        out.append(
            capture(
                store,
                execution_id,
                "JOB",
                package["package_status"],
                facts={"archive_sha256": package.get("archive_sha256"), "gap_count": package.get("gap_count")},
                source_refs=["archive:sha256:" + str(package.get("archive_sha256"))],
                cohort=cohort,
            )
        )
    return out


def capture_controller_outcomes(afo_store, lessons, *, limit=32):
    """Capture non-product and never-dispatched terminal jobs without inventing native runs."""
    out = []
    for table, identity_col, scope in (
        ("afo_local_agent_jobs", "job_id", "agent"),
        ("afo_work_orders", "order_id", "order"),
    ):
        control = "learning_" + scope + "_cursor"
        with afo_store.tx() as c:
            prior = c.execute("SELECT value FROM afo_control WHERE key=?", (control,)).fetchone()
            cursor = prior[0] if prior else ""
            fields = identity_col + ",record" if scope == "agent" else "order_id,state,envelope"
            rows = c.execute(
                f"SELECT {fields} FROM {table} WHERE {identity_col}>? ORDER BY {identity_col} LIMIT ?", (cursor, limit)
            ).fetchall()
            if not rows:
                c.execute("DELETE FROM afo_control WHERE key=?", (control,))
        for row in rows:
            try:
                value = json.loads(row["record"] if scope == "agent" else row["envelope"])
                outcome = value.get("state") if scope == "agent" else row["state"]
                if outcome not in OUTCOMES:
                    continue
                if scope == "order":
                    with afo_store.tx() as c:
                        attempts = c.execute("SELECT record FROM afo_attempts WHERE order_id=?", (row["order_id"],)).fetchall()
                    if any(json.loads(a[0]).get("fabro_run_id") for a in attempts):
                        continue  # adoption aliases are covered by their unique native execution
                source = digest(value)
                out.append(
                    capture(
                        lessons,
                        "controller-" + scope + ":" + row[identity_col],
                        value.get("role", "JOB"),
                        outcome,
                        facts={"state_record_sha256": source, "error_code": value.get("error")},
                        source_refs=["afo-state:sha256:" + source],
                        cohort={"model": value.get("model"), "revision": value.get("factory_revision")},
                    )
                )
            except (ValueError, TypeError, KeyError) as exc:
                if scope == "order":
                    from ..afo.dispatch import item_failure

                    item_failure(afo_store, row["order_id"], exc, "learning_capture")
                # Keep malformed source untouched; no unsupported experience is synthesized.
        if rows:
            with afo_store.tx() as c:
                c.execute(
                    "INSERT INTO afo_control VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_utc=excluded.updated_utc",
                    (control, rows[-1][identity_col], utc_now(), "deterministic-learning-reconciler"),
                )
    return out
