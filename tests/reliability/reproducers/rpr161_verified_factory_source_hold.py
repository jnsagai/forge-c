"""Immutable independent Planner oracle; synthetic registry/receipts, no model, grant or production action."""
import copy
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace as S
from forge_factory.afo import line_campaign as C, line_orders as O
BAD, FIX, BASE, GOOD, OTHER = (x * 40 for x in "abcde")
SOURCE = "WO-F014-CMP-SWE4-WWDGHAL-20261104-T1F"
PREVIOUS = "WO-F014-CMP-SWE3-WWDGHAL-20261104-T1E"
FP = "cfp1-verified-source-fixture"
SIG = "verified factory cause retries its known failing source after fix qualification"
def database(path):
    db = sqlite3.connect(path)
    db.executescript("""
      CREATE TABLE cre_capa(capa_id TEXT,record TEXT,state TEXT,root_cause_status TEXT);
      CREATE TABLE cre_capa_links(capa_id TEXT,kind TEXT,ref TEXT);
      CREATE TABLE cre_promotion_decisions(decision_id TEXT,candidate TEXT,baseline TEXT,record TEXT);
      CREATE TABLE cre_reproducer_runs(run_id TEXT,reproducer_id TEXT,revision TEXT,role TEXT,
                                     exit_code INTEGER,verdict TEXT);
    """)
    record = {"state": "EFFECTIVENESS_OBSERVING", "root_cause_status": "VERIFIED", "reproducer_id": "RPR-160",
              "incident_ids": ["cloud:" + SOURCE + ":DEF-001"]}
    db.execute("INSERT INTO cre_capa VALUES(?,?,?,?)",
               ("CAPA-160", json.dumps(record), record["state"], record["root_cause_status"]))
    db.executemany("INSERT INTO cre_capa_links VALUES(?,?,?)",
                   [("CAPA-160", "FIX_REVISION", FIX), ("CAPA-160", "FINGERPRINT", FP),
                    ("CAPA-160", "PROMOTION_DECISION", "pd-fix")])
    fix = {"decision": "ELIGIBLE_FOR_OFFLINE_REVIEW", "evaluator_kind": "INDEPENDENT_DETERMINISTIC_RUNNER",
           "hard_gates": [{"name": "reproducer", "result": "PASS",
                           "evidence_refs": ["reproducer-run:rr-base", "reproducer-run:rr-fix"]}]}
    good = {"decision": "ELIGIBLE_FOR_OFFLINE_REVIEW", "evaluator_kind": "INDEPENDENT_DETERMINISTIC_RUNNER",
            "hard_gates": [{"name": "prevention", "result": "PASS",
                            "evidence_refs": ["reproducer-run:rr-good"]}]}
    db.executemany("INSERT INTO cre_promotion_decisions VALUES(?,?,?,?)",
                   [("pd-fix", FIX, BASE, json.dumps(fix)), ("pd-good", GOOD, BAD, json.dumps(good))])
    db.executemany("INSERT INTO cre_reproducer_runs VALUES(?,?,?,?,?,?)", [
        ("rr-base", "RPR-160", BASE, "BASELINE", 1, "SYMPTOM_PRESENT"),
        ("rr-fix", "RPR-160", FIX, "CANDIDATE", 0, "SYMPTOM_ABSENT"),
        ("rr-actual-bad", "RPR-160", BAD, "BASELINE", 1, "SYMPTOM_PRESENT"),
        ("rr-good", "RPR-160", GOOD, "PREVENTION", 0, "SYMPTOM_ABSENT")])
    db.commit()
    return db

class Records:
    def __init__(self, db):
        self.cre_db = db
        self.source = O.Att(SOURCE, "SWE.4", 6, created=20, status="ENDED", verdict="NO", ended_at=21,
                            rec={"revision": BAD, "tag": "WWDGHAL", "source": PREVIOUS},
                            core={"class": "UNKNOWN", "fingerprint": FP, "cre_fingerprint": FP,
                                  "error_code": "UNCLASSIFIED", "upstream": []})
        self.earlier = copy.deepcopy(self.source)
        self.earlier.wo, self.earlier.n, self.earlier.created, self.earlier.ended_at = SOURCE[:-1] + "E", 5, 10, 11
        self.previous = O.Att(PREVIOUS, "SWE.3", 0, created=1, status="ENDED", verdict="PASS",
                              rec={"passed": {"SWE.3"}})
        self.attempts = [self.earlier, self.source]

    def phase_attempts(self, lineage, phase):
        return self.attempts if phase == "SWE.4" else []

    def attempt(self, wo, phase, n):
        return self.previous if wo == PREVIOUS else next(a for a in self.attempts if a.wo == wo)

def plan(records, revision=BAD):
    lineage = C.Lineage("CMP-TEST-1", "wwdg-hal", "ACTIVE", "wwdg", "WWDGHAL", "20261104-T1",
                        "STM32N6_WWDG_HAL", revision, "test-profile", "test-model", "ASPICE_ONLY", ("SWE.4",), 50,
                        start={"at": "SWE.4", "resume_from": PREVIOUS}, wo_prefix="WO-F014-CMP", sha256="f" * 64)
    campaign = C.Campaign(Path("fixture"), "fixture", lineage.campaign_id, "cloud", "0" * 64, None,
                          lineages=[lineage])
    line = S(resolve=lambda r: r, quality_supported=lambda r: True, spec_quality=lambda *a: (True, None))
    policy = S(get=lambda key, default=None: default)
    return O.Planner([campaign], records, line, policy, 100).run()[0]
def main():
    with tempfile.TemporaryDirectory(prefix="rpr161-") as tmp:
        p = Path(tmp)/"registry.sqlite3"; db = database(p); records = Records(p)
        before = hashlib.sha256(p.read_bytes()).hexdigest()
        held, released, unqualified = plan(records), plan(records, GOOD), plan(records, OTHER)
        correct = (held.state == "WAITING" and held.reason == "WAITING_EXTERNAL_CHANGE:CAPA-160"
                   and held.order is None and held.strikes == 2 and records.source.core["class"] == "UNKNOWN"
                   and released.action == "PLACE" and released.order["resume_from"] == PREVIOUS
                   and released.strikes == 2 and unqualified.state == "WAITING"
                   and hashlib.sha256(p.read_bytes()).hexdigest() == before)
        if not correct:
            print("SYMPTOM_PRESENT:" + SIG); return 1
        passed = O.Att("WO-F014-CMP-SWE4-WWDGHAL-20261104-T1G", "SWE.4", 7, created=30,
                       status="ENDED", verdict="PASS", rec={"revision": GOOD, "tag": "WWDGHAL",
                       "passed": {"SWE.4"}, "ws": None})
        records.attempts.append(passed)
        resolved = plan(records, GOOD)
        assert resolved.state == "DONE" and resolved.strikes == 0 and len(records.attempts) == 3
        records.attempts.pop(); db.execute("DELETE FROM cre_reproducer_runs WHERE run_id='rr-actual-bad'"); db.commit()
        assert plan(records).action == "PLACE", "unproved closed CAPA was treated as active"
        db.close(); print("SYMPTOM_ABSENT"); return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("REPRODUCER_ERROR:" + type(exc).__name__ + ":" + str(exc)[:140]); raise SystemExit(2)
