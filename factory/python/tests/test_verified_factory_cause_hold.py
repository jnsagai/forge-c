"""Verified source receipts prevent retrying a pre-fix runtime after CAPA promotion."""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace as S

import pytest
from forge_factory.afo import line_campaign as C, line_orders as O
from forge_factory.afo.line_verified_causes import Guard

BAD, FIX, BASE, GOOD, OTHER = (x * 40 for x in "abcde")
SOURCE = "WO-F014-CMP-SWE4-WWDGHAL-20261104-T1F"
PREVIOUS = "WO-F014-CMP-SWE3-WWDGHAL-20261104-T1E"
FP = "cfp1-verified-source-fixture"


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


@pytest.fixture
def case(tmp_path):
    path = tmp_path / "registry.sqlite3"
    db = database(path)
    yield db, Records(path)
    db.close()


def test_old_source_waits_without_reclassification_or_history_reset(case):
    db, records = case
    before = hashlib.sha256(records.cre_db.read_bytes()).hexdigest()
    p = plan(records)
    assert (p.state, p.reason, p.action, p.order) == ("WAITING", "WAITING_EXTERNAL_CHANGE:CAPA-160", None, None)
    assert p.strikes == 2 and records.source.core["class"] == "UNKNOWN"
    assert hashlib.sha256(records.cre_db.read_bytes()).hexdigest() == before


def test_qualified_replacement_gets_one_retry_then_adopts_queued_running_and_pass(case):
    _, records = case
    p = plan(records, GOOD)
    assert p.action == "PLACE" and p.order["resume_from"] == PREVIOUS and p.strikes == 2
    queued = O.Att(p.order["wo"], "SWE.4", 7, created=30, status="QUEUED", spec=p.order)
    records.attempts.append(queued)
    p = plan(records, GOOD)
    assert p.action == "LAUNCH" and p.order["wo"] == queued.wo
    queued.status, queued.rid = "RUNNING", "native-fixture"
    assert plan(records, GOOD).state == "RUNNING"
    queued.status, queued.verdict = "ENDED", "PASS"
    queued.rec = {"revision": GOOD, "tag": "WWDGHAL", "passed": {"SWE.4"}, "ws": None}
    p = plan(records, GOOD)
    assert p.state == "DONE" and p.strikes == 0 and len(records.attempts) == 3


def test_merely_different_unqualified_hash_cannot_release_hold(case):
    assert plan(case[1], OTHER).state == "WAITING"


def test_already_queued_retry_of_known_bad_source_is_held(case):
    records = case[1]
    records.attempts.append(O.Att("WO-F014-CMP-SWE4-WWDGHAL-20261104-T1G", "SWE.4", 7,
                                created=30, status="QUEUED", spec={"revision": BAD}))
    p = plan(records)
    assert p.state == "WAITING" and p.order is None and p.strikes == 2


@pytest.mark.parametrize("sql", [
    "UPDATE cre_capa SET root_cause_status='UNRESOLVED'",
    "DELETE FROM cre_capa_links WHERE kind='FIX_REVISION'",
    "DELETE FROM cre_capa_links WHERE kind='PROMOTION_DECISION'",
    "DELETE FROM cre_reproducer_runs WHERE run_id='rr-actual-bad'",
    "UPDATE cre_reproducer_runs SET role='CANDIDATE' WHERE run_id='rr-actual-bad'",
    "UPDATE cre_reproducer_runs SET exit_code=2 WHERE run_id='rr-actual-bad'",
    "DELETE FROM cre_reproducer_runs WHERE run_id='rr-fix'",
])
def test_unproved_closed_capa_never_becomes_active_cause(case, sql):
    db, records = case
    db.execute(sql); db.commit()
    assert plan(records).action == "PLACE"


@pytest.mark.parametrize("sql", [
    "DELETE FROM cre_reproducer_runs WHERE run_id='rr-good'",
    "UPDATE cre_reproducer_runs SET reproducer_id='RPR-999' WHERE run_id='rr-good'",
    "UPDATE cre_reproducer_runs SET revision='wrong' WHERE run_id='rr-good'",
    "UPDATE cre_reproducer_runs SET role='BASELINE' WHERE run_id='rr-good'",
    "UPDATE cre_promotion_decisions SET record='{}' WHERE decision_id='pd-good'",
    "UPDATE cre_promotion_decisions SET record='malformed' WHERE decision_id='pd-good'",
])
def test_replacement_needs_exact_eligible_prevention_receipt(case, sql):
    db, records = case
    db.execute(sql); db.commit()
    assert plan(records, GOOD).state == "WAITING"


def test_receipt_outside_eligible_decision_cannot_release(case):
    db, records = case
    raw = json.loads(db.execute("SELECT record FROM cre_promotion_decisions WHERE decision_id='pd-good'").fetchone()[0])
    raw["hard_gates"][0]["evidence_refs"] = []
    db.execute("UPDATE cre_promotion_decisions SET record=? WHERE decision_id='pd-good'", (json.dumps(raw),)); db.commit()
    assert plan(records, GOOD).state == "WAITING"


def test_unrelated_fingerprint_or_source_revision_is_not_reclassified(case):
    records = case[1]
    records.source.core["cre_fingerprint"] = "unrelated"
    assert plan(records).action == "PLACE"
    records.source.core["cre_fingerprint"] = FP
    records.source.rec["revision"] = GOOD
    assert plan(records, GOOD).action == "PLACE"


def test_more_than_three_strikes_still_escalates(case):
    records = case[1]
    for n in (7, 8):
        extra = copy.deepcopy(records.source)
        extra.wo, extra.n, extra.created, extra.ended_at = SOURCE + str(n), n, n * 10, n * 10 + 1
        records.attempts.append(extra)
    p = plan(records)
    assert p.state == "ESCALATED" and p.reason == "SAME_ISSUE_EXCEEDED_3" and p.strikes == 4


def test_absent_registry_is_read_only_and_leaves_legacy_behavior(case, tmp_path):
    records = case[1]
    records.cre_db = tmp_path / "not-created.sqlite3"
    assert plan(records).action == "PLACE" and not records.cre_db.exists()
    assert Guard(None).causes == []


def test_lost_registry_cannot_release_a_previously_proven_source_hold(case):
    _, records = case
    guard = Guard(records.cre_db)
    assert guard.causes
    records.cre_db.rename(records.cre_db.with_suffix(".unavailable"))
    assert guard.blocked(records.source, GOOD, records) == "WAITING_EXTERNAL_CHANGE:CAPA-160"


def test_signed_fixture_dry_placer_passes_configured_registry_without_placing(case, tmp_path, monkeypatch):
    """Real signature verification in a private synthetic fixture; no owner/runtime grant is changed."""
    import test_line_conductor_m3 as M3

    root = tmp_path / "signed-fixture"
    root.mkdir()
    env = M3.env.__wrapped__(root, monkeypatch)
    env["line"].revs[BAD] = BAD
    M3.write_campaign(env, [M3.lineage("wwdg-hal", "WWDGHAL", "20261104-T1", factory_revision=BAD,
                                      phases=["SWE.4"], start={"at": "SWE.4", "resume_from": PREVIOUS})])
    M3.grant(env)
    policy = O.load_policy(root / "line-policy.yaml")
    authorization = O.verify_grant(policy, now=env["clock"](), base=root / "auth", allowed_signers=env["signers"])
    assert authorization.allow
    registry, records = case[1].cre_db, case[1]
    records.cre_db = None  # the production cycle must supply its explicitly configured registry

    class ReplayPlacer(O.Placer):
        def _records(self, now, capa_of):
            return records

    placer = ReplayPlacer(env["line"], dry_run=True, campaigns_dir=env["camp"], policy_path=root / "line-policy.yaml",
                           auth_base=root / "auth", allowed_signers=env["signers"], clock=env["clock"],
                           capa_of={}, cre_db=registry)
    result = placer.cycle()
    assert result["mode"] == "DRY_RUN" and result["authorization"]["code"] == "AUTH_OK"
    assert result["lineages"][0]["reason"] == "WAITING_EXTERNAL_CHANGE:CAPA-160"
    assert result["lineages"][0]["strikes"]["count"] == 2 and not env["line"].launched
