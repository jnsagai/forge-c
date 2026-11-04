"""Source-bound holds for verified factory causes after their FIX is qualified.

An effectiveness observation is not proof that a running campaign has deployed
the fix. This read-only view leaves the open-CAPA map and recorded classifications
alone. A hold needs an independent PRESENT receipt for the failed source; release
needs an eligible promotion containing this cause's ABSENT prevention receipt.
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

REV = re.compile(r"[0-9a-f]{40}")
WO = re.compile(r"(?:^|:)(WO-[A-Za-z0-9_-]{1,180})(?=:|$)")


class Guard:
    def __init__(self, path: Path | None):
        self.path = Path(path) if path is not None else None
        self.causes = []
        if self.path is None or not self.path.is_file():
            return
        try:
            with closing(self._db()) as db:
                for cid, raw, state, verified in db.execute(
                    "SELECT capa_id,record,state,root_cause_status FROM cre_capa "
                    "WHERE root_cause_status='VERIFIED' AND state IN ('EFFECTIVENESS_OBSERVING','CLOSED')"
                ):
                    try:
                        record = json.loads(raw)
                        if record.get("root_cause_status") != verified or record.get("state") != state:
                            continue
                        rpr = record.get("reproducer_id")
                        if not isinstance(rpr, str) or not re.fullmatch(r"RPR-[0-9]+", rpr):
                            continue
                        links = db.execute("SELECT kind,ref FROM cre_capa_links WHERE capa_id=?", (cid,)).fetchall()
                        fixes = {ref for kind, ref in links if kind == "FIX_REVISION" and REV.fullmatch(ref)}
                        fingerprints = {ref for kind, ref in links if kind == "FINGERPRINT"}
                        sources = {m[1] for value in record.get("incident_ids", []) if isinstance(value, str)
                                   for m in WO.finditer(value)}
                        if not sources or not fingerprints:
                            continue
                        eligible = any(self._fix(db, ref, fixes, rpr) for kind, ref in links
                                       if kind == "PROMOTION_DECISION")
                        if eligible:
                            present = {rev for (rev,) in db.execute(
                                "SELECT revision FROM cre_reproducer_runs WHERE reproducer_id=? AND role='BASELINE' "
                                "AND verdict='SYMPTOM_PRESENT' AND exit_code=1", (rpr,)) if REV.fullmatch(rev)}
                            self.causes.append({"capa": cid, "reproducer": rpr, "sources": sources,
                                                "fingerprints": fingerprints, "present_revisions": present})
                    except (ValueError, TypeError, AttributeError, KeyError):
                        continue  # an unverified/malformed record never becomes an active cause
        except sqlite3.Error:
            self.causes = []

    def _db(self):
        return sqlite3.connect("file:" + str(self.path) + "?mode=ro", uri=True)

    @staticmethod
    def _decision(db, did, revision=None):
        row = db.execute("SELECT candidate,baseline,record FROM cre_promotion_decisions WHERE decision_id=?",
                         (did,)).fetchone()
        if not row or (revision is not None and row[0] != revision):
            return None
        record = json.loads(row[2])
        if (record.get("decision") != "ELIGIBLE_FOR_OFFLINE_REVIEW"
                or record.get("evaluator_kind") != "INDEPENDENT_DETERMINISTIC_RUNNER"):
            return None
        return row[0], row[1], {g["name"]: g for g in record.get("hard_gates", [])}

    @staticmethod
    def _receipt(db, rpr, revision, verdict, code, references=None, role=None):
        rows = db.execute("SELECT run_id,role FROM cre_reproducer_runs WHERE reproducer_id=? AND revision=? "
                          "AND verdict=? AND exit_code=?", (rpr, revision, verdict, code))
        return any((references is None or "reproducer-run:" + rid in references)
                   and (role is None or kind == role) for rid, kind in rows)

    def _fix(self, db, did, revisions, rpr):
        decision = self._decision(db, did)
        if not decision or decision[0] not in revisions:
            return False
        candidate, baseline, gates = decision
        gate = gates.get("reproducer", {})
        refs = gate.get("evidence_refs", [])
        return (gate.get("result") == "PASS"
                and self._receipt(db, rpr, baseline, "SYMPTOM_PRESENT", 1, refs)
                and self._receipt(db, rpr, candidate, "SYMPTOM_ABSENT", 0, refs))

    def _replacement(self, db, revision, rpr):
        for (did,) in db.execute("SELECT decision_id FROM cre_promotion_decisions WHERE candidate=?", (revision,)):
            try:
                decision = self._decision(db, did, revision)
            except (ValueError, TypeError, AttributeError, KeyError):
                continue
            if not decision:
                continue
            gate = decision[2].get("prevention", {})
            if (gate.get("result") == "PASS" and self._receipt(
                    db, rpr, revision, "SYMPTOM_ABSENT", 0, gate.get("evidence_refs", []), role="PREVENTION")):
                return True
        return False

    def blocked(self, attempt, revision, records):
        """Return a known-cause hold reason, without relabeling attempts or changing counters."""
        if (not self.causes or attempt is None or attempt.status != "ENDED" or attempt.verdict != "NO"
                or not attempt.rec or not attempt.core or not REV.fullmatch(attempt.revision or "")):
            return None
        fp = attempt.core.get("cre_fingerprint") or attempt.core.get("fingerprint")
        for cause in self.causes:
            if fp not in cause["fingerprints"] or attempt.revision not in cause["present_revisions"]:
                continue
            for source_wo in cause["sources"]:
                try:
                    source = records.attempt(source_wo, attempt.phase, 0)
                except (KeyError, StopIteration):
                    continue
                if (not source or source.status != "ENDED" or source.verdict != "NO" or not source.rec
                        or source.phase != attempt.phase or source.revision != attempt.revision
                        or source.rec.get("tag") != attempt.rec.get("tag")):
                    continue
                qualified = False
                if revision != attempt.revision:
                    try:
                        with closing(self._db()) as db:
                            qualified = self._replacement(db, revision, cause["reproducer"])
                    except (sqlite3.Error, ValueError, TypeError, AttributeError, KeyError):
                        pass  # inability to prove a replacement cannot release an already proven source hold
                if not qualified:
                    return "WAITING_EXTERNAL_CHANGE:" + cause["capa"]
        return None
