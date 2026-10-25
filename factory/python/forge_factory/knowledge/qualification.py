"""Source-specific lesson qualification from frozen independent test receipts.

This API belongs to the deterministic engineering/CRE harness, never a curator MCP
grant. Model confidence, same-model review and candidate-supplied PASS lists cannot
qualify memory. Inspector lessons retain knowledge.inspection governance.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..afo.durable import Refused, canonical, digest
from ..common import sha256_file


def heldout_source(connection, source):
    """An append-only correction classifies the whole execution, including older observations."""
    record = json.loads(source["record"])
    if record.get("cohort", {}).get("evaluation_holdout"):
        return True
    return (
        connection.execute(
            "SELECT 1 FROM job_experience WHERE execution_id=? AND json_extract(record,'$.cohort.evaluation_holdout')=1 LIMIT 1",
            (record["execution_id"],),
        ).fetchone()
        is not None
    )


def record(store, lesson, *, manifest_path, manifest_sha256, reports):
    p = Path(manifest_path)
    if p.is_symlink() or sha256_file(p) != manifest_sha256:
        raise Refused("LESSON_QUALIFICATION_MANIFEST_CHANGED")
    manifest = json.loads(p.read_text())
    expected = manifest["cases"]
    if (
        manifest.get("lesson_hash") != store.content_hash(lesson)
        or not expected
        or not {"APPLICABLE", "ADVERSE"} <= {c["kind"] for c in expected}
        or any(c.get("producer") not in ("gate", "reference", "metamorphic", "mutant", "CRE") for c in expected)
    ):
        raise Refused("LESSON_INDEPENDENT_SCOPE_MANIFEST_REQUIRED")
    actual = []
    for ref in reports:
        path = Path(ref["path"])
        if path.is_symlink() or sha256_file(path) != ref["sha256"]:
            raise Refused("LESSON_QUALIFICATION_REPORT_CHANGED")
        doc = json.loads(path.read_text())
        if doc.get("manifest_sha256") != manifest_sha256:
            raise Refused("LESSON_QUALIFICATION_REPORT_UNBOUND")
        actual += doc["rows"]
    if len(actual) != len(expected) or len({r["id"] for r in actual}) != len(actual):
        raise Refused("LESSON_QUALIFICATION_COVERAGE_MISSING")
    for case in expected:
        row = next((r for r in actual if r["id"] == case["id"]), None)
        if (
            not row
            or row.get("producer") != case["producer"]
            or row.get("oracle_sha256") != case["oracle_sha256"]
            or row.get("observed") != case["expected"]
            or row.get("regressions")
        ):
            raise Refused("LESSON_QUALIFICATION_FAILED")
    with store._conn() as c:
        source = c.execute(
            "SELECT source_hash,outcome,record FROM job_experience WHERE experience_id=?", (lesson["experience_ref"],)
        ).fetchone()
        if not source or manifest.get("experience_source_hash") != source["source_hash"]:
            raise Refused("LESSON_EXPERIENCE_SOURCE_CHANGED")
        if heldout_source(c, source):
            raise Refused("HELDOUT_ACCEPTANCE_SOURCE_CANNOT_BE_DISTILLED")
        if lesson["source_kind"] == "NEGATIVE_OBSERVATION" and source["outcome"] in (
            "PASS",
            "SUCCEEDED",
            "READY_FOR_OFFLINE_REVIEW",
        ):
            raise Refused("NEGATIVE_LESSON_SOURCE_NOT_NEGATIVE")
        rec = {
            "lesson_hash": store.content_hash(lesson),
            "experience_ref": lesson["experience_ref"],
            "source_hash": source["source_hash"],
            "manifest_sha256": manifest_sha256,
            "reports": reports,
            "cases": expected,
            "passed": True,
        }
        qid = "lesson-qualification-" + digest(rec)[:24]
        c.execute("INSERT OR IGNORE INTO lesson_qualifications VALUES (?,?,?)", (qid, canonical(rec).decode(), digest(rec)))
    return qid


def issues(store, lesson):
    with store._conn() as c:
        row = c.execute(
            "SELECT record,sha256 FROM lesson_qualifications WHERE qualification_id=?", (lesson.get("qualification_ref"),)
        ).fetchone()
        exp = c.execute(
            "SELECT source_hash,record FROM job_experience WHERE experience_id=?", (lesson.get("experience_ref"),)
        ).fetchone()
        heldout = heldout_source(c, exp) if exp else False
        predecessor = c.execute("SELECT record,state FROM lessons WHERE lesson_id=?", (lesson.get("supersedes"),)).fetchone()
    if not row or not exp:
        return ["SOURCE_OUTCOME_OR_QUALIFICATION_UNRESOLVED"]
    rec = json.loads(row["record"])
    out = []
    if heldout:
        out.append("HELDOUT_ACCEPTANCE_SOURCE_CANNOT_BE_DISTILLED")
    if (
        digest(rec) != row["sha256"]
        or rec["lesson_hash"] != store.content_hash(lesson)
        or rec["source_hash"] != exp["source_hash"]
        or not rec["passed"]
    ):
        out.append("QUALIFICATION_NOT_FOR_THIS_SOURCE_SCOPE_VERSION")
    if lesson.get("supersedes") and (
        not predecessor or lesson.get("version", 0) <= json.loads(predecessor["record"]).get("version", 1)
    ):
        out.append("SUCCESSOR_VERSION_NOT_NEWER")
    for ref in rec["reports"]:
        try:
            if sha256_file(Path(ref["path"])) != ref["sha256"]:
                out.append("QUALIFICATION_REPORT_STALE")
        except OSError:
            out.append("QUALIFICATION_REPORT_UNRESOLVED")
    return out
