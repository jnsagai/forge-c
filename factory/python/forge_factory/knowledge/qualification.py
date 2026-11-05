"""Source-specific lesson qualification from frozen independent test receipts.

This API belongs to the deterministic engineering/CRE harness, never a curator MCP
grant. Model confidence, same-model review and candidate-supplied PASS lists cannot
qualify memory. Inspector lessons retain knowledge.inspection governance.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from ..afo.durable import Refused, canonical, digest
from ..common import REPO_ROOT, sha256_file


def historical_holdout_refs(work_order, *, root=REPO_ROOT, bounds=None):
    """Read historical evaluation projections without rewriting source manifests.

    Older seeded trials recorded holdout identities in reports, while the original
    successful cloud workspace predates evaluation_holdout. An explicit training
    selection cannot erase that later classification. This is a projection of
    existing evidence, not another cohort authority or writable registry.
    """
    refs = []

    def matches(value):
        return isinstance(value, str) and (value == work_order or f"/{work_order}/" in value)

    def contains(value):
        if isinstance(value, dict):
            return any((key == "holdout" and matches(item))
                       or (key == "holdouts" and isinstance(item, list) and any(matches(x) for x in item))
                       or contains(item) for key, item in value.items())
        return isinstance(value, list) and any(contains(item) for item in value)

    if bounds is None:
        files = sorted((Path(root) / "evidence").rglob("*.json"))
        deadline = None
    else:
        files, deadline = _bounded_history_files(Path(root) / "evidence", bounds)
    consumed = 0
    for path in files:
        if bounds is None:
            raw = path.read_text()
            identity = None
        else:
            from ..afo.fault_observer import read_bytes

            if time.monotonic() >= deadline:
                raise Refused("LESSON_HISTORY_TIME_BOUND_EXCEEDED")
            data = read_bytes(path, min(bounds["max_file_bytes"], bounds["max_bytes"] - consumed))
            consumed += len(data)
            if consumed > bounds["max_bytes"] or time.monotonic() >= deadline:
                raise Refused("LESSON_HISTORY_READ_BOUND_EXCEEDED")
            raw = data.decode("utf-8")
            identity = hashlib.sha256(data).hexdigest()
        if work_order not in raw or '"holdout' not in raw:
            continue
        # Unreadable matching evidence is not silently reclassified as training.
        if contains(json.loads(raw)):
            refs.append({"path": str(path.relative_to(root)), "sha256": identity or sha256_file(path)})
        if bounds is not None and time.monotonic() >= deadline:
            raise Refused("LESSON_HISTORY_TIME_BOUND_EXCEEDED")
    if bounds is not None and time.monotonic() >= deadline:
        raise Refused("LESSON_HISTORY_TIME_BOUND_EXCEEDED")
    return refs


def _bounded_history_files(directory, bounds):
    """Optional observation resource limit; exceeding it is UNKNOWN/refusal, never training."""
    import math

    keys = {"max_entries", "max_bytes", "max_file_bytes", "timeout_seconds"}
    if (not isinstance(bounds, dict) or set(bounds) != keys
            or any(type(bounds[k]) is not int or bounds[k] < 1 for k in keys - {"timeout_seconds"})
            or type(bounds["timeout_seconds"]) not in (int, float) or not math.isfinite(bounds["timeout_seconds"])
            or not 0 < bounds["timeout_seconds"] <= 30
            or bounds["max_entries"] > 65536 or bounds["max_bytes"] > 64 * 1024 * 1024
            or bounds["max_file_bytes"] > 16 * 1024 * 1024):
        raise Refused("LESSON_HISTORY_BOUND_INVALID")
    deadline = time.monotonic() + bounds["timeout_seconds"]
    pending, files, count = [directory], [], 0
    if directory.is_symlink():
        raise Refused("LESSON_HISTORY_SYMLINK_UNKNOWN")
    if not directory.exists():
        return files, deadline
    while pending:
        if time.monotonic() >= deadline:
            raise Refused("LESSON_HISTORY_TIME_BOUND_EXCEEDED")
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                count += 1  # Includes directories and non-JSON entries.
                if count > bounds["max_entries"] or time.monotonic() >= deadline:
                    raise Refused("LESSON_HISTORY_SCAN_BOUND_EXCEEDED")
                if entry.is_symlink():
                    raise Refused("LESSON_HISTORY_SYMLINK_UNKNOWN")
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.name.endswith(".json"):
                    if not entry.is_file(follow_symlinks=False):
                        raise Refused("LESSON_HISTORY_NONREGULAR_UNKNOWN")
                    files.append(Path(entry.path))
    # The list is bounded by the already checked total traversal count.
    files = sorted(files)
    if time.monotonic() >= deadline:
        raise Refused("LESSON_HISTORY_TIME_BOUND_EXCEEDED")
    return files, deadline


def heldout_source(connection, source, *, history_bounds=None):
    """An append-only correction classifies the whole execution, including older observations."""
    record = json.loads(source["record"])
    if record.get("cohort", {}).get("evaluation_holdout"):
        return True
    provenance = record.get("facts", {}).get("phase_reference_provenance", {})
    if provenance.get("work_order") and historical_holdout_refs(provenance["work_order"], bounds=history_bounds):
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


def issues(store, lesson, *, history_bounds=None):
    with store._conn() as c:
        row = c.execute(
            "SELECT record,sha256 FROM lesson_qualifications WHERE qualification_id=?", (lesson.get("qualification_ref"),)
        ).fetchone()
        exp = c.execute(
            "SELECT source_hash,record FROM job_experience WHERE experience_id=?", (lesson.get("experience_ref"),)
        ).fetchone()
        heldout = heldout_source(c, exp, history_bounds=history_bounds) if exp else False
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
