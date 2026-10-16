"""CRE D3 (CRE-T017..T023) — Corrective and Preventive Action with reproducer-verified root causes.

State machine (contract capa-record.schema.json):
  OPEN -> TRIAGED -> REPRODUCER_PENDING -> CAUSE_VERIFIED -> FIX_CANDIDATE -> PREVENTION_TESTED
       -> EFFECTIVENESS_OBSERVING -> EFFECTIVE ;  REOPENED/UNRESOLVED -> TRIAGED ;  REJECTED is terminal.
Guards use ONLY records written by deterministic components (reproducer runner, failure registry, git):
  * CAUSE_VERIFIED: the frozen reproducer shows the expected symptom on the baseline revision AND is absent on the
    candidate revision (causal contrast) - root_cause_status becomes VERIFIED here, never from agent text;
  * PREVENTION_TESTED: the same reproducer is registered as a prevention test and is absent at the current revision;
  * EFFECTIVE: `effectiveness_window_runs` later attempts that contain the fix and exercised the operation, with no
    recurrence of the CAPA's error codes; a recurrence in such an attempt -> REOPENED (history kept, lessons retracted).
Every transition is an append-only history row + a cre.capa_transition event. Failed attempts stay recorded.
"""
from __future__ import annotations

import json
import subprocess

from ..common import REPO_ROOT, canonical_json, sha256_bytes, utc_now
from . import events as E
from . import reproduce as RR
from .policy import CRE_CONTRACTS_DIR, Policy
from .store import CREStore

STATES = ("OPEN", "TRIAGED", "REPRODUCER_PENDING", "CAUSE_VERIFIED", "FIX_CANDIDATE", "PREVENTION_TESTED",
          "EFFECTIVENESS_OBSERVING", "EFFECTIVE", "REJECTED", "UNRESOLVED", "REOPENED")
TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"TRIAGED", "REJECTED"},
    "TRIAGED": {"REPRODUCER_PENDING", "UNRESOLVED", "REJECTED"},
    "REPRODUCER_PENDING": {"CAUSE_VERIFIED", "UNRESOLVED"},
    "CAUSE_VERIFIED": {"FIX_CANDIDATE"},
    "FIX_CANDIDATE": {"PREVENTION_TESTED", "UNRESOLVED", "REJECTED"},
    "PREVENTION_TESTED": {"EFFECTIVENESS_OBSERVING"},
    "EFFECTIVENESS_OBSERVING": {"EFFECTIVE", "REOPENED"},
    "EFFECTIVE": {"REOPENED"},
    "REOPENED": {"TRIAGED"},
    "UNRESOLVED": {"TRIAGED"},
    "REJECTED": set(),
}
VERIFIED_STATES = {"CAUSE_VERIFIED", "FIX_CANDIDATE", "PREVENTION_TESTED", "EFFECTIVENESS_OBSERVING", "EFFECTIVE"}
LESSON_STATES = {"PREVENTION_TESTED", "EFFECTIVENESS_OBSERVING", "EFFECTIVE"}
MAX_UNRESOLVED_CYCLES = 3
GUARDED = {"CAUSE_VERIFIED": "verify_cause", "PREVENTION_TESTED": "register_prevention",
           "EFFECTIVE": "evaluate_effectiveness"}


class CapaError(ValueError):
    pass


def _schema_errors(rec: dict) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = json.loads((CRE_CONTRACTS_DIR / "capa-record.schema.json").read_text())
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:160]
            for e in Draft202012Validator(schema).iter_errors(rec)]


def _git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60).stdout.strip()


def is_ancestor(fix: str, rev: str) -> bool | None:
    if not fix or not rev or rev == "UNKNOWN":
        return None
    r = subprocess.run(["git", "merge-base", "--is-ancestor", fix, rev], cwd=REPO_ROOT, capture_output=True, timeout=60)
    return {0: True, 1: False}.get(r.returncode)  # 128 = unknown revision => None (not counted)


class CapaRegistry:
    def __init__(self, store: CREStore, policy: Policy, lessons=None):
        self.s, self.p = store, policy
        self.lessons = lessons  # the 002 LessonStore this registry links/retracts (never an implicit default)

    # -- persistence ---------------------------------------------------------------------------
    def get(self, capa_id: str) -> dict | None:
        with self.s.conn() as c:
            r = c.execute("SELECT record FROM cre_capa WHERE capa_id=?", (capa_id,)).fetchone()
        return json.loads(r[0]) if r else None

    def must(self, capa_id: str) -> dict:
        rec = self.get(capa_id)
        if rec is None:
            raise CapaError(f"UNKNOWN_CAPA:{capa_id}")
        return rec

    def all(self) -> list[dict]:
        with self.s.conn() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT record FROM cre_capa ORDER BY capa_id")]

    def history(self, capa_id: str) -> list[dict]:
        with self.s.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM cre_capa_history WHERE capa_id=? ORDER BY seq", (capa_id,))]

    def links(self, capa_id: str, kind: str | None = None) -> list[str]:
        q, a = "SELECT ref FROM cre_capa_links WHERE capa_id=?", (capa_id,)
        if kind:
            q, a = q + " AND kind=?", (capa_id, kind)
        with self.s.conn() as c:
            return [r[0] for r in c.execute(q + " ORDER BY seq", a)]

    def link(self, capa_id: str, kind: str, ref: str) -> None:
        with self.s.conn() as c:
            c.execute("INSERT OR IGNORE INTO cre_capa_links(capa_id,kind,ref,at) VALUES (?,?,?,?)",
                      (capa_id, kind, ref, utc_now()))

    def _save(self, rec: dict, frm: str | None, reason: str, evidence: list[str]) -> dict:
        errs = _schema_errors(rec)
        if errs:
            raise CapaError("CAPA_SCHEMA:" + "; ".join(errs[:3]))
        with self.s.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            cur = c.execute("SELECT state FROM cre_capa WHERE capa_id=?", (rec["capa_id"],)).fetchone()
            if (cur[0] if cur else None) != frm:
                c.execute("ROLLBACK")
                raise CapaError(f"CONCURRENT_UPDATE:{rec['capa_id']}")
            c.execute("INSERT INTO cre_capa(capa_id,record,state,root_cause_status,updated_at) VALUES (?,?,?,?,?) "
                      "ON CONFLICT(capa_id) DO UPDATE SET record=excluded.record, state=excluded.state, "
                      "root_cause_status=excluded.root_cause_status, updated_at=excluded.updated_at",
                      (rec["capa_id"], canonical_json(rec).decode(), rec["state"], rec["root_cause_status"],
                       rec["updated_at"]))
            c.execute("INSERT INTO cre_capa_history(capa_id,from_state,to_state,at,reason,evidence) VALUES (?,?,?,?,?,?)",
                      (rec["capa_id"], frm, rec["state"], rec["updated_at"], reason[:300], json.dumps(evidence)[:2000]))
            n = c.execute("SELECT count(*) FROM cre_capa_history WHERE capa_id=?", (rec["capa_id"],)).fetchone()[0]
            c.execute("COMMIT")
        ev = E.build("cre.capa_opened" if frm is None else "cre.capa_transition", f"{rec['capa_id']}|{n}",
                     {"state": rec["state"], "from": frm or "-", "root_cause_status": rec["root_cause_status"],
                      "reason": reason[:200]}, policy_sha256=self.p.sha256, correlation_id=rec["capa_id"],
                     capa_id=rec["capa_id"], evidence_refs=evidence[:20],
                     data_status="VERIFIED" if rec["root_cause_status"] == "VERIFIED" else "OBSERVED")
        E.record(self.s, ev)
        return rec

    # -- lifecycle ----------------------------------------------------------------------------
    def open(self, capa_id: str, incident_ids: list[str], fingerprints: list[str], reason: str) -> dict:
        if self.get(capa_id) is not None:
            raise CapaError(f"CAPA_EXISTS:{capa_id}")
        for fp in fingerprints:  # one active CAPA per fingerprint (duplicates are linked, not re-opened)
            for other in self.all():
                if other["state"] != "REJECTED" and fp in self.links(other["capa_id"], "FINGERPRINT"):
                    raise CapaError(f"DUPLICATE_FINGERPRINT:{fp}:{other['capa_id']}")
        now = utc_now()
        rec = {"schema_version": "1.0", "capa_id": capa_id, "incident_ids": sorted(set(incident_ids)) or [capa_id],
               "state": "OPEN", "root_cause_status": "UNKNOWN", "root_cause_summary": None,
               "root_cause_evidence_refs": [], "reproducer_id": None, "prevention_test_id": None,
               "candidate_patch_sha256": None, "affected_versions": [], "lesson_ids": [],
               "observation_window_end": None, "created_at": now, "updated_at": now, "policy_sha256": self.p.sha256,
               "event_ids": []}
        self._save(rec, None, reason, rec["incident_ids"][:10])
        for fp in fingerprints:
            self.link(capa_id, "FINGERPRINT", fp)
        return self.must(capa_id)

    def transition(self, capa_id: str, to: str, reason: str, evidence: list[str] | None = None,
                   _guard: str | None = None, **fields) -> dict:
        rec = self.must(capa_id)
        frm = rec["state"]
        if to not in TRANSITIONS.get(frm, set()):
            raise CapaError(f"INVALID_TRANSITION:{frm}->{to}")
        if GUARDED.get(to) and _guard != GUARDED[to]:  # AT-015/016: no claim reaches a verified state by assertion
            raise CapaError(f"GUARDED_TRANSITION:{to} only via {GUARDED[to]}")
        if fields.get("root_cause_status") == "VERIFIED" and _guard != "verify_cause":
            raise CapaError("ROOT_CAUSE_VERIFIED_ONLY_BY_CAUSAL_CONTRAST")
        rec = {**rec, **fields, "state": to, "updated_at": utc_now(), "policy_sha256": self.p.sha256}
        if to in ("REOPENED", "UNRESOLVED") and rec["root_cause_status"] == "VERIFIED":
            rec["root_cause_status"] = "HYPOTHESIS"  # a recurrence puts the verified cause back in question
        return self._save(rec, frm, reason, evidence or [])

    def annotate(self, capa_id: str, reason: str, evidence: list[str] | None = None, **fields) -> dict:
        """Same-state update of non-guarded fields (e.g. lesson_ids), recorded in the history like a transition."""
        if {"state", "root_cause_status"} & set(fields):
            raise CapaError("ANNOTATE_CANNOT_CHANGE_STATE_OR_CAUSE")
        rec = self.must(capa_id)
        return self._save({**rec, **fields, "updated_at": utc_now()}, rec["state"], reason, evidence or [])

    def triage(self, capa_id: str, hypothesis: str, reproducer_id: str | None, source: str) -> dict:
        """A hypothesis is never a verified cause; `source` records who proposed it (AGENT/HUMAN/RULE).
        Bounded: after MAX_UNRESOLVED_CYCLES failed verifications the CAPA stays UNRESOLVED for offline attention."""
        unresolved = sum(h["to_state"] == "UNRESOLVED" for h in self.history(capa_id))
        if unresolved >= MAX_UNRESOLVED_CYCLES:
            raise CapaError(f"CAPA_ATTEMPTS_EXHAUSTED:{unresolved} unresolved verifications; offline attention")
        rec = self.transition(capa_id, "TRIAGED", f"triage by {source}", [], root_cause_summary=hypothesis[:2000],
                              root_cause_status="HYPOTHESIS")
        if reproducer_id:
            if reproducer_id not in RR.load_manifest()[0]:
                return self.transition(capa_id, "UNRESOLVED", f"reproducer {reproducer_id} not in the frozen manifest")
            rec = self.transition(capa_id, "REPRODUCER_PENDING", f"reproducer {reproducer_id} assigned",
                                  reproducer_id=reproducer_id)
        return rec

    def verify_cause(self, capa_id: str, baseline_run: dict, candidate_run: dict) -> dict:
        """CRE-T019: only runner records count; any claim without them leaves the cause a HYPOTHESIS."""
        rec = self.must(capa_id)
        if rec["state"] != "REPRODUCER_PENDING":
            raise CapaError(f"NOT_PENDING:{rec['state']}")
        known = {r["run_id"]: r for r in RR.reproducer_runs(self.s, rec["reproducer_id"])}
        for r in (baseline_run, candidate_run):  # forged or edited records are not runner records (AT-016)
            if known.get(r.get("run_id")) != r:
                return self.transition(capa_id, "UNRESOLVED", f"UNVERIFIED_EVIDENCE:{r.get('run_id')}")
        ok, why = RR.causal_verdict(baseline_run, candidate_run)
        refs = [f"reproducer-run:{baseline_run['run_id']}", f"reproducer-run:{candidate_run['run_id']}"]
        if not ok:
            return self.transition(capa_id, "UNRESOLVED", why, refs)
        self.link(capa_id, "BASELINE_REVISION", baseline_run["revision"])
        self.link(capa_id, "FIX_REVISION", candidate_run["revision"])
        return self.transition(capa_id, "CAUSE_VERIFIED", why, refs, _guard="verify_cause", root_cause_status="VERIFIED",
                               root_cause_evidence_refs=refs,
                               affected_versions=[f"forge-c@<{candidate_run['revision'][:12]}"])

    def register_fix(self, capa_id: str) -> dict:
        fix = self.links(capa_id, "FIX_REVISION")[-1]
        base = self.links(capa_id, "BASELINE_REVISION")[-1]
        patch = subprocess.run(["git", "diff", base, fix], cwd=REPO_ROOT, capture_output=True, timeout=120).stdout
        rec = self.transition(capa_id, "FIX_CANDIDATE", f"fix {fix[:12]} (patch {len(patch)} bytes)",
                              [f"git:{base[:12]}..{fix[:12]}"], candidate_patch_sha256=sha256_bytes(patch))
        E.record(self.s, E.build("cre.corrective_action_applied", f"{capa_id}|{fix}", {
            "fix_revision": fix[:12], "baseline_revision": base[:12], "patch_sha256": rec["candidate_patch_sha256"]},
            policy_sha256=self.p.sha256, correlation_id=capa_id, capa_id=capa_id))  # CRE-T052
        return rec

    def register_prevention(self, capa_id: str, regression_run: dict) -> dict:
        """The reproducer becomes a durable prevention test; it must be absent at the regression revision."""
        rec = self.must(capa_id)
        known = {r["run_id"]: r for r in RR.reproducer_runs(self.s, rec["reproducer_id"])}
        if known.get(regression_run.get("run_id")) != regression_run or regression_run["verdict"] != "SYMPTOM_ABSENT":
            return self.transition(capa_id, "UNRESOLVED", f"prevention not demonstrated: {regression_run.get('verdict')}")
        test_id = f"prevention:{rec['reproducer_id']}"
        with self.s.conn() as c:
            c.execute("INSERT OR IGNORE INTO cre_prevention_tests VALUES (?,?,?,?,?)",
                      (test_id, capa_id, rec["reproducer_id"], utc_now(), regression_run["revision"]))
        E.record(self.s, E.build("cre.preventive_test_registered", f"{capa_id}|{test_id}",
                                 {"test_id": test_id, "revision": regression_run["revision"][:12]},
                                 policy_sha256=self.p.sha256, correlation_id=capa_id, capa_id=capa_id))
        self.transition(capa_id, "PREVENTION_TESTED", f"prevention test {test_id} absent at "
                        f"{regression_run['revision'][:12]}", [f"reproducer-run:{regression_run['run_id']}"],
                        _guard="register_prevention", prevention_test_id=test_id)
        return self.transition(capa_id, "EFFECTIVENESS_OBSERVING", "observation window opened")

    def evaluate_effectiveness(self, capa_id: str, exposures: list[dict], observations: list[dict],
                               error_codes: list[str], operations: list[str]) -> dict:
        """CRE-T021: recurrence (same error code + operation) in an attempt that contains the fix -> REOPENED;
        `effectiveness_window_runs` clean exposures -> EFFECTIVE; otherwise keep observing (no claim)."""
        rec = self.must(capa_id)
        if rec["state"] not in ("EFFECTIVENESS_OBSERVING", "EFFECTIVE"):
            return rec
        fix = self.links(capa_id, "FIX_REVISION")[-1]
        window = int(self.p.get("capa.effectiveness_window_runs"))
        after = [x for x in exposures if is_ancestor(fix, x["revision"]) and set(x["operations"]) & set(operations)]
        seen = {x["attempt_id"] for x in after}
        recur = [o for o in observations if o["attempt_id"] in seen and o["error_code"] in error_codes
                 and o["operation"] in operations and o["disposition"] == "ACTIVE"]
        if recur:
            first = sorted(recur, key=lambda o: o["ts_utc"])[0]
            self.link(capa_id, "RECURRENCE", first["obs_id"])
            rec = self.transition(capa_id, "REOPENED", f"recurrence {first['error_code']} {first['operation']} in "
                                  f"{first['attempt_id']} (contains fix {fix[:12]})",
                                  [f"cre-observation:{first['obs_id']}"])
            self.retract_lessons(capa_id, f"CAPA {capa_id} reopened by recurrence {first['obs_id']}")
            return rec
        if len(after) >= window and rec["state"] == "EFFECTIVENESS_OBSERVING":
            return self.transition(capa_id, "EFFECTIVE", f"{len(after)} clean exposures >= window {window}",
                                   [f"attempt:{a['attempt_id']}" for a in after[:10]], _guard="evaluate_effectiveness")
        self.link(capa_id, "EXPOSURE_COUNT", f"{len(after)}/{window}@{utc_now()[:16]}")
        return rec

    # -- lessons (CRE-T022) -------------------------------------------------------------------
    def lesson_source(self) -> CapaLessonSource:
        return CapaLessonSource(self)

    def propose_lesson(self, capa_id: str, lessons, symptom: str, remedy: str) -> dict:
        rec = self.must(capa_id)
        if rec["state"] not in LESSON_STATES or rec["root_cause_status"] != "VERIFIED":
            raise CapaError(f"LESSON_REQUIRES_VERIFIED_CAPA:{rec['state']}/{rec['root_cause_status']}")
        runs = [r.split(":", 1)[1] for r in rec["root_cause_evidence_refs"]]
        les = lessons.propose({"source_incident_id": capa_id, "source_attempt_id": runs[-1],
                               "symptoms": symptom, "root_cause": rec["root_cause_summary"] or "", "remedy": remedy,
                               "constraints": "Reference data from a verified CAPA; never overrides requirements, "
                                              "hardware manuals or factory policy.",
                               "evidence_refs": rec["root_cause_evidence_refs"] + [f"cre-capa:{capa_id}"],
                               "tool_versions": {"forge-factory": self.links(capa_id, "FIX_REVISION")[-1][:12]},
                               "validation_tests": [{"id": f"{rec['reproducer_id']}:{r}", "status": "PASS",
                                                     "evidence_ref": f"reproducer-run:{r}"} for r in runs]})
        les = lessons.validate(les["lesson_id"])
        self.link(capa_id, "LESSON", les["lesson_id"])
        if les["state"] == "VALIDATED":
            self.annotate(capa_id, f"lesson {les['lesson_id']} validated", [f"lesson:{les['lesson_id']}"],
                          lesson_ids=sorted(set(self.must(capa_id)["lesson_ids"]) | {les["lesson_id"]}))
            E.record(self.s, E.build("cre.lesson_linked", f"{capa_id}|{les['lesson_id']}",
                                     {"lesson_id": les["lesson_id"], "state": les["state"]},
                                     policy_sha256=self.p.sha256, correlation_id=capa_id, capa_id=capa_id))
        return les

    def retract_lessons(self, capa_id: str, reason: str, lessons=None) -> list[dict]:
        ls = lessons or self.lessons
        if ls is None:
            raise CapaError("NO_LESSON_STORE_BOUND")
        out = []
        for lid in self.links(capa_id, "LESSON"):
            les = ls.get(lid)
            if les and les["state"] == "VALIDATED":
                out.append(ls.retract(lid, reason[:200]))
                E.record(self.s, E.build("cre.lesson_retracted", f"{capa_id}|{lid}|{reason[:60]}",
                                         {"lesson_id": lid, "reason": reason[:160]}, policy_sha256=self.p.sha256,
                                         correlation_id=capa_id, capa_id=capa_id))
        return out


class CapaLessonSource:
    """Adapter for the 002 lesson curator: a CAPA counts as a promoted source correction only when its root cause
    is VERIFIED by the runner and its prevention test is registered (`attempts` mirrors IncidentStore.attempts)."""

    def __init__(self, reg: CapaRegistry):
        self.reg = reg

    def attempts(self, capa_id: str | None) -> list[dict]:
        rec = self.reg.get(capa_id or "")
        if rec is None:
            return []
        runs = [r.split(":", 1)[1] for r in rec["root_cause_evidence_refs"]]
        ok = rec["root_cause_status"] == "VERIFIED" and rec["state"] in LESSON_STATES and rec["prevention_test_id"]
        return [{"attempt_id": runs[-1] if runs else capa_id, "status": "PROMOTED" if ok else "NOT_VERIFIED",
                 "tests": [{"name": r, "status": "PASS" if ok else "NOT_RUN"} for r in runs] or
                          [{"name": "none", "status": "NOT_RUN"}]}]
