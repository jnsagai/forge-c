"""Verified human-review intake into existing CRE/CAPA and gated lesson publication.

No model call, policy edit, package rewrite or source activation. Human rationale
is retained as signed evidence, never copied into a lesson or model instruction.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..common import canonical_json
from ..events.redact import redact_text
from ..reliability import events as E
from ..reliability.capa import CapaError, CapaRegistry
from ..reliability.policy import load
from ..reliability.store import CREStore


class Refused(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def registry() -> CapaRegistry:
    return CapaRegistry(CREStore(), load())


@contextmanager
def intake_lock(reg: CapaRegistry):
    with reg.s.path.with_name(reg.s.path.name + ".human-review.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _save(path: Path, data: bytes, *, public: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755 if public else 0o700)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise Refused("DSP_EVIDENCE_CONFLICT")
        return
    fd, temporary = tempfile.mkstemp(prefix=".review-", dir=path.parent)
    try:
        if public:
            os.fchmod(fd, 0o444)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)  # atomic creation; an archive is never overwritten
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise Refused("DSP_EVIDENCE_CONFLICT") from None
    finally:
        Path(temporary).unlink(missing_ok=True)


def received(reg: CapaRegistry, did: str) -> dict | None:
    eid = E.event_id("cre.policy_decision", "human-review|" + did)
    with reg.s.conn() as connection:
        row = connection.execute("SELECT record FROM cre_events WHERE event_id=?", (eid,)).fetchone()
    return json.loads(row[0])["payload"] if row else None


def ingest(reg: CapaRegistry, rec: dict, *, review_sha256: str, signature: bytes, signers: bytes,
           bundle: bytes) -> str | None:
    """Called under intake_lock only after the public signature/export/subject/set checks."""
    old = received(reg, rec["disposition_id"])
    if old:
        if old["review_sha256"] != review_sha256:
            raise Refused("DSP_ID_CONFLICT")
        return old.get("capa_id")
    if redact_text(canonical_json(rec).decode())[1]:
        raise Refused("DSP_REVIEW_CONTAINS_SECRET")
    if hashlib.sha256(bundle).hexdigest() != rec["export_sha256"]:
        raise Refused("DSP_EXPORT_CHANGED")
    artifacts = reg.s.path.parent / "review-artifacts"
    directory = artifacts / "reviews" / review_sha256 / hashlib.sha256(signature).hexdigest()
    review = canonical_json({**rec, "signature_ref": "review.sig"})
    archived_sha = hashlib.sha256(review).hexdigest()
    _save(directory / "review.json", review)
    _save(directory / "review.sig", signature)
    _save(directory / "allowed-signers", signers)
    _save(artifacts / "exports" / (rec["export_sha256"] + ".zip"), bundle)
    cid = None
    if rec["verdict"] in ("CONFIRMED_DEFECT", "FALSE_FINDING"):
        identity = [rec["export_sha256"], rec["run_key"], rec["subject"], rec["verdict"]]
        cid = "CAPA-HR-" + hashlib.sha256(canonical_json(identity)).hexdigest()[:24]
        if reg.get(cid) is None:
            reg.open(cid, ["human-review:" + review_sha256], [],
                     "Verified owner review requests corrective analysis: " + rec["verdict"])
        reg.link(cid, "HUMAN_REVIEW", str(directory / "review.json") + "#sha256=" + archived_sha)
        reg.link(cid, "EXPORT", rec["export_sha256"])
        reg.link(cid, "REVIEW_PHASE", rec["subject"]["phase"])
    event = E.build("cre.policy_decision", "human-review|" + rec["disposition_id"],
        {"operation": "offline.review_intake", "decision": "VERIFIED_REVIEW_RECORDED",
         "disposition_id": rec["disposition_id"], "review_sha256": review_sha256,
         "export_sha256": rec["export_sha256"], "verdict": rec["verdict"], "capa_id": cid,
         "phase": rec["subject"]["phase"], "use": "LEARNING_SET_ONLY"}, policy_sha256=reg.p.sha256,
        correlation_id="review:" + review_sha256[:24], capa_id=cid,
        evidence_refs=[str(directory / "review.json"), "sha256:" + rec["export_sha256"]],
        evidence_sha256=archived_sha)
    E.record(reg.s, event)
    return cid


def _decision(reg, did):
    with reg.s.conn() as connection:
        row = connection.execute("SELECT * FROM cre_promotion_decisions WHERE decision_id=?", (did,)).fetchone()
    if not row:
        raise Refused("DSP_ELIGIBLE_CRE_REQUIRED")
    record = json.loads(row["record"])
    gates = record.get("hard_gates") or []
    expected = {"protected_files", "policy_integrity", "reproducer", "prevention", "quality_process",
                "golden_benchmark", "holdout"}
    if (row["decision"] != "ELIGIBLE_FOR_OFFLINE_REVIEW" or record.get("decision") != row["decision"]
            or record.get("evaluator_kind") != "INDEPENDENT_DETERMINISTIC_RUNNER"
            or record.get("policy_sha256") != reg.p.sha256 or len(gates) != len(expected)
            or {g["name"] for g in gates} != expected or any(g["result"] != "PASS" for g in gates)):
        raise Refused("DSP_ELIGIBLE_CRE_REQUIRED")
    return dict(row), record


def reproducer_entry(reg, record, manifests):
    """Prefer the immutable descriptor bound to this exact qualified fix iteration."""
    selected = []
    fixes = reg.links(record["capa_id"], "FIX_REVISION")
    for ref in reg.links(record["capa_id"], "REVIEW_REPRODUCER"):
        name, sha = ref.rsplit("#sha256=", 1)
        path = Path(name)
        raw = path.read_bytes()
        if path.is_symlink() or hashlib.sha256(raw).hexdigest() != sha:
            raise Refused("DSP_PREVENTION_REQUIRED")
        doc = json.loads(raw)
        if doc["id"] == record["reproducer_id"] and fixes and doc["fix_revision"] == fixes[-1]:
            script = path.parent / "reproducer.py"
            if script.is_symlink() or hashlib.sha256(script.read_bytes()).hexdigest() != doc["sha256"]:
                raise Refused("DSP_PREVENTION_REQUIRED")
            selected.append(doc)
    if len(selected) > 1:
        raise Refused("DSP_PREVENTION_REQUIRED")
    return selected[0] if selected else manifests.get(record.get("reproducer_id"))


def qualify(reg: CapaRegistry, cid: str, did: str, *, reproducer: str | None = None,
            staged_manifest: Path | None = None, description: dict | None = None) -> dict:
    """Advance the review CAPA only from an existing real FIX decision and runner logs.

    A staged maintainer reproducer additionally matches its committed candidate
    source; its curated explanation is still checked by the lesson validators.
    This command executes no candidate, test, model, patch or deployment.
    """
    import re
    import subprocess

    from ..common import REPO_ROOT, load_yaml, state_dir
    from ..reliability import reproduce as RR

    current = reg.must(cid)
    if not reg.links(cid, "HUMAN_REVIEW"):
        raise Refused("DSP_REVIEW_CAPA_REQUIRED")
    row, decision = _decision(reg, did)
    refs = {g["name"]: g.get("evidence_refs", []) for g in decision["hard_gates"]}
    def runs(references):
        result = []
        with reg.s.conn() as connection:
            for ref in references:
                kind, _, rid = ref.partition(":")
                if kind != "reproducer-run" or not re.fullmatch(r"rr-[A-Za-z0-9_-]+", rid):
                    raise Refused("DSP_RUNNER_PROOF_REQUIRED")
                stored = connection.execute("SELECT * FROM cre_reproducer_runs WHERE run_id=?", (rid,)).fetchone()
                if not stored:
                    raise Refused("DSP_RUNNER_PROOF_REQUIRED")
                stored = dict(stored)
                log = state_dir() / "reliability/reproducers" / (rid + ".log")
                if log.is_symlink() or hashlib.sha256(log.read_bytes()).hexdigest() != stored["log_sha256"]:
                    raise Refused("DSP_RUNNER_PROOF_REQUIRED")
                result.append(stored)
        return result
    causal = runs(refs["reproducer"])
    ids = {r["reproducer_id"] for r in causal}
    if reproducer is None and len(ids) != 1:
        raise Refused("DSP_REPRODUCER_SELECTION_REQUIRED")
    rid = reproducer or next(iter(ids))
    paired = [r for r in causal if r["reproducer_id"] == rid]
    baseline = [r for r in paired if r["revision"] == row["baseline"] and r["verdict"] == "SYMPTOM_PRESENT"]
    candidate = [r for r in paired if r["revision"] == row["candidate"] and r["verdict"] == "SYMPTOM_ABSENT"]
    prevention = [r for r in runs(refs["prevention"]) if r["reproducer_id"] == rid
                  and r["revision"] == row["candidate"] and r["verdict"] == "SYMPTOM_ABSENT"]
    if not prevention and rid.startswith("AFO-"):
        # The actual causal candidate run exercises the new staged regression.
        # Qualifying it registers the immutable test for every later CRE gate.
        prevention = candidate
    if len(baseline) != 1 or len(candidate) != 1 or len(prevention) != 1:
        raise Refused("DSP_RUNNER_PROOF_REQUIRED")
    if staged_manifest is not None:
        if (staged_manifest.name != "manifest.yaml" or staged_manifest.is_symlink()
                or (staged_manifest.parent / "reproducer.py").is_symlink()):
            raise Refused("DSP_PREVENTION_REQUIRED")
        staged = load_yaml(staged_manifest)
        members = staged.get("reproducers", []) if isinstance(staged, dict) else []
        if len(members) != 1 or members[0].get("script") != "reproducer.py" or members[0].get("id") != rid:
            raise Refused("DSP_PREVENTION_REQUIRED")
        if description is not None and not isinstance(description, dict):
            raise Refused("DSP_LESSON_DESCRIPTION_REQUIRED")
    manifests, issues = RR.load_manifest(staged_manifest)
    if issues or rid not in manifests:
        raise Refused("DSP_PREVENTION_REQUIRED")
    entry = {**manifests[rid], **({k: v for k, v in (description or {}).items()
                               if k in ("root_cause", "remedy", "operations", "error_codes")} if staged_manifest else {})}
    script = Path(entry["path"]).read_bytes()
    if staged_manifest:
        source_path = entry.get("source_path", "")
        if (not rid.startswith("AFO-") or not re.fullmatch(r"(?!/)(?!.*\.\.)[A-Za-z0-9._/+-]+", source_path)
                or entry.get("fix_revision") != row["candidate"] or entry.get("baseline_revision") != row["baseline"]):
            raise Refused("DSP_PREVENTION_REQUIRED")
        committed = subprocess.check_output(["git", "show", row["candidate"] + ":" + source_path],
                                             cwd=REPO_ROOT, timeout=60)
        if hashlib.sha256(committed).hexdigest() != entry["sha256"]:
            raise Refused("DSP_PREVENTION_REQUIRED")
    if (any(not isinstance(entry.get(key), str) or not 1 <= len(entry[key]) <= maximum
            for key, maximum in (("root_cause", 700), ("remedy", 850), ("symptom_signature", 600)))
            or any(not isinstance(entry.get(key), list) or not 1 <= len(entry[key]) <= 64
                   or any(not isinstance(value, str) or not 1 <= len(value) <= 160 for value in entry[key])
                   for key in ("operations", "error_codes")) or redact_text(canonical_json(entry).decode())[1]):
        raise Refused("DSP_LESSON_DESCRIPTION_REQUIRED")
    descriptor = {k: v for k, v in entry.items() if k not in ("path", "script")}
    descriptor.update(fix_revision=row["candidate"], baseline_revision=row["baseline"])
    raw = canonical_json(descriptor)
    sha = hashlib.sha256(raw).hexdigest()
    directory = reg.s.path.parent / "review-artifacts/reproducers" / sha
    _save(directory / "reproducer.py", script, public=True)
    _save(directory / "descriptor.json", raw, public=True)
    reg.link(cid, "REVIEW_REPRODUCER", str(directory / "descriptor.json") + "#sha256=" + sha)
    if current["state"] in ("OPEN", "REOPENED", "UNRESOLVED"):
        reg.triage(cid, entry["root_cause"], None, "RULE:independent-CRE-receipt")
        reg.transition(cid, "REPRODUCER_PENDING", "immutable qualified reproducer bound", reproducer_id=rid)
    elif current["state"] == "TRIAGED" and current.get("reproducer_id") in (None, rid):
        reg.annotate(cid, "independent CRE receipt supplies the tested hypothesis", root_cause_summary=entry["root_cause"])
        reg.transition(cid, "REPRODUCER_PENDING", "immutable qualified reproducer bound", reproducer_id=rid)
    elif current.get("reproducer_id") != rid:
        raise Refused("DSP_CAPA_ITERATION_CONFLICT")
    if reg.must(cid)["state"] == "REPRODUCER_PENDING":
        reg.verify_cause(cid, baseline[0], candidate[0])
    if reg.must(cid)["state"] == "CAUSE_VERIFIED":
        reg.register_fix(cid)
    if reg.must(cid)["state"] == "FIX_CANDIDATE":
        reg.register_prevention(cid, prevention[0])
    if reg.must(cid)["state"] not in ("PREVENTION_TESTED", "EFFECTIVENESS_OBSERVING", "EFFECTIVE"):
        raise Refused("DSP_CAPA_ITERATION_CONFLICT")
    if reg.links(cid, "FIX_REVISION")[-1] != row["candidate"] or reg.links(cid, "BASELINE_REVISION")[-1] != row["baseline"]:
        raise Refused("DSP_CAPA_ITERATION_CONFLICT")
    reg.link(cid, "PROMOTION_DECISION", did)
    return {"capa_id": cid, "state": reg.must(cid)["state"], "decision_id": did, "reproducer_id": rid}


def publish(reg: CapaRegistry, cid: str, *, workspace: Path | None = None, role: str | None = None) -> dict:
    """Curate a frozen remedy only after causal/prevention proof AND an eligible CRE decision."""
    from ..knowledge.store import LessonStore
    from ..reliability import reproduce as RR

    record = reg.must(cid)
    phases = reg.links(cid, "REVIEW_PHASE")
    if not reg.links(cid, "HUMAN_REVIEW") or len(phases) != 1:
        raise Refused("DSP_REVIEW_CAPA_REQUIRED")
    if record["state"] not in ("PREVENTION_TESTED", "EFFECTIVENESS_OBSERVING", "EFFECTIVE"):
        raise Refused("DSP_CAPA_NOT_VALIDATED")
    manifests, issues = RR.load_manifest()
    entry = reproducer_entry(reg, record, manifests)
    if issues or not entry or not record.get("prevention_test_id") or record["root_cause_status"] != "VERIFIED":
        raise Refused("DSP_PREVENTION_REQUIRED")
    fix, baseline = reg.links(cid, "FIX_REVISION"), reg.links(cid, "BASELINE_REVISION")
    eligible = False
    for did in reg.links(cid, "PROMOTION_DECISION"):
        try:
            row, _ = _decision(reg, did)
        except Refused:
            continue
        eligible |= bool(fix and baseline and row["candidate"] == fix[-1] and row["baseline"] == baseline[-1])
    if not eligible:
        raise Refused("DSP_ELIGIBLE_CRE_REQUIRED")
    from ..common import REPO_ROOT
    from ..knowledge.context import applicability
    from .review_sets import active_workorders

    if workspace is None or role not in ("afo-factory-maintainer", "afo-recovery-planner", f"swe{phases[0][-1]}-author"):
        raise Refused("DSP_LESSON_SCOPE_REQUIRED")
    manifest = json.loads((workspace / ".forge-run/manifest.json").read_text())
    scope = applicability(workspace)
    if scope["holdout"] or manifest.get("work_order") in active_workorders(REPO_ROOT):
        raise Refused("DSP_HELDOUT_REFUSED")
    if not scope["target"] or not scope["source_version"] or not scope["tool_versions"]:
        raise Refused("DSP_LESSON_SCOPE_REQUIRED")
    if any(not isinstance(value, str) or value in ("", "UNKNOWN") for value in scope["tool_versions"].values()):
        raise Refused("DSP_LESSON_SCOPE_REQUIRED")
    for item in manifest.get("inputs", []):
        path = workspace / item["path"]
        if (path.is_symlink() or not path.resolve().is_relative_to(workspace.resolve()) or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256")):
            raise Refused("DSP_SCOPE_INPUTS_CHANGED")
    destination = dict(phases=phases, roles=[role], targets=[scope["target"]], source_versions=[scope["source_version"]])
    lessons = LessonStore(incidents=reg.lesson_source())
    reg.lessons = lessons
    for lid in reg.links(cid, "LESSON"):
        lesson = lessons.get(lid)
        same_scope = (lesson and lesson.get("applicability") == destination
                      and lesson.get("tool_versions") == scope["tool_versions"])
        if same_scope and lesson["state"] == "VALIDATED":
            return {"capa_id": cid, "lesson_id": lid, "state": "VALIDATED", "created": False}
        if same_scope:
            raise Refused("DSP_LESSON_REQUIRES_REVIEW")
    try:
        lesson = reg.propose_lesson(cid, lessons, entry["symptom_signature"], entry["remedy"], phase=phases[0],
                                    applicability=destination, tool_versions=scope["tool_versions"])
    except CapaError as exc:
        raise Refused("DSP_CAPA_NOT_VALIDATED") from exc
    return {"capa_id": cid, "lesson_id": lesson["lesson_id"], "state": lesson["state"], "created": True}


def reconcile(reg: CapaRegistry, workspaces: list[Path], *, lessons, limit: int = 32, cursor_store=None) -> list[dict]:
    """Existing learning-cycle hook: proven recurrence retracts reviewed-CAPA lessons.

    Only completed packages and recorded source revisions count as exposures.
    Retain at most the configured clean window per CAPA; inspect the current
    exposure for recurrence even after that window has filled.
    """
    from ..reliability import observe
    from ..reliability import reproduce as RR

    if not 1 <= limit <= 32 or len(workspaces) > 8:
        raise Refused("DSP_RECONCILIATION_BOUND_REQUIRED")
    cursor = ""
    if cursor_store is not None:
        with cursor_store.tx() as connection:
            saved = connection.execute("SELECT value FROM afo_control WHERE key='human_review_capa_cursor'").fetchone()
            cursor = saved[0] if saved else ""
    query = "SELECT c.record FROM cre_capa c WHERE c.state IN ('EFFECTIVENESS_OBSERVING'," \
            "'EFFECTIVE') AND EXISTS (SELECT 1 FROM cre_capa_links l WHERE l.capa_id=c.capa_id AND l.kind='HUMAN_REVIEW') "
    with reg.s.conn() as connection:
        rows = connection.execute(query + "AND c.capa_id>? ORDER BY c.capa_id LIMIT ?", (cursor, limit)).fetchall()
        if not rows and cursor:
            rows = connection.execute(query + "ORDER BY c.capa_id LIMIT ?", (limit,)).fetchall()
    if not rows:
        return []
    complete = []
    for ws in workspaces:
        package = ws / ".forge-run/package.json"
        if package.is_file() and not package.is_symlink():
            if json.loads(package.read_text()).get("package_status") in ("BLOCKED", "READY_FOR_OFFLINE_REVIEW"):
                complete.append(ws)
    exposures = [x for x in observe.attempt_exposures(complete) if x["revision_basis"] == "recorded_at_launch"]
    observations = [o for ws in complete for o in observe.from_workspace(ws)]
    for observation in observations:
        if reg.s.insert_observation(observation):
            event = E.build("cre.failure_observed", observation["obs_key"],
                {k: observation[k] for k in ("operation", "error_code", "failure_class", "outcome", "source_kind")},
                policy_sha256=reg.p.sha256, correlation_id=observation["attempt_id"],
                evidence_refs=[observation["source_ref"]], evidence_sha256=observation["evidence_sha256"],
                phase=observation["phase"], work_order=observation["attempt_id"])
            E.record(reg.s, event)
    manifests, issues = RR.load_manifest()
    if issues:
        raise Refused("DSP_PREVENTION_REQUIRED")
    reg.lessons = lessons
    out = []
    for row in rows:
        record = json.loads(row[0])
        cid = record["capa_id"]
        entry = reproducer_entry(reg, record, manifests)
        if not entry:
            continue
        saved = {x["attempt_id"]: x for x in map(json.loads, reg.links(cid, "REVIEW_EXPOSURE"))}
        window = int(reg.p.get("capa.effectiveness_window_runs"))
        fix = reg.links(cid, "FIX_REVISION")[-1]
        from ..reliability.capa import is_ancestor

        for exposure in exposures:
            if is_ancestor(fix, exposure["revision"]) and set(exposure["operations"]) & set(entry["operations"]):
                if exposure["attempt_id"] not in saved and len(saved) < window:
                    reg.link(cid, "REVIEW_EXPOSURE", canonical_json(exposure).decode())
                    saved[exposure["attempt_id"]] = exposure
        all_exposures = {**saved, **{x["attempt_id"]: x for x in exposures}}
        result = reg.evaluate_effectiveness(cid, list(all_exposures.values()), observations,
                                            entry["error_codes"], entry["operations"])
        out.append({"capa_id": cid, "state": result["state"]})
    if cursor_store is not None:
        from ..common import utc_now

        with cursor_store.tx() as connection:
            connection.execute("INSERT INTO afo_control VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE "
                "SET value=excluded.value,updated_utc=excluded.updated_utc",
                ("human_review_capa_cursor", json.loads(rows[-1][0])["capa_id"], utc_now(), "review-capa-reconciler"))
    return out
