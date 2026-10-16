"""CRE D1 (CRE-T005..T010): typed events, idempotent replay, classifier, fingerprints, root-cause fields, bounded
redacted telemetry (AT-002..AT-007)."""
import json
import random
import sqlite3

import pytest
from forge_factory.reliability import events as E
from forge_factory.reliability import observe as O
from forge_factory.reliability import taxonomy as T
from forge_factory.reliability.store import SCHEMA_VERSION, CREStore
from forge_factory.supervisor.store import IncidentStore

POL = "a" * 64


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path


def _ws(root, name, created="2026-10-16T03:00:00Z", resumed=False, lines=(), inspections=(), defects=(), pkg=None,
        model="deepseek-flash"):
    ws = root / "state/workorders" / name / "workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    m = {"work_order": name, "created_at": created, "driver": "STM32N6 RCC low-level (LL) and HAL driver",
         "target": {"core": "Arm Cortex-M55", "safety_allocation": "OUT_OF_SCOPE: QM"},
         "factory_revision": {"commit": "0123456789abcdef", "basis": "recorded_at_launch"}}
    if resumed:
        m["resumed_from"] = {"source_work_order": "WO-X-r1"}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": model, "provider": "deepseek"}))
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    for i, ins in enumerate(inspections):
        p = ws / f"inspection/{ins['phase']}/INS-{ins['phase']}-00{i + 1}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ins))
    for i, d in enumerate(defects):
        p = ws / f".forge-run/defects/DEF-00{i + 1}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d))
    if pkg:
        (ws / ".forge-run/package.json").write_text(json.dumps(pkg))
    return ws


REJECT = {"ts": "2026-10-16T03:10:00Z", "phase": "SWE.4", "step": "author", "result": "REJECTED", "status": "INCOMPLETE",
          "issues": ["REQUIRED_TOOL_NOT_PASS:run_unit:FAIL", "MISSING_REQUIRED_OUTPUT:workproducts/SWE.4/unit_verification_report.md"]}
BLOCK = {"ts": "2026-10-16T03:20:00Z", "phase": "SWE.4", "step": "route",
         "gate": {"decision": "BLOCKED", "reason": "rework budget exhausted (3 failed cycles)"}}


def _two_attempts(root):
    a = _ws(root, "WO-X-r1", lines=[REJECT, BLOCK], pkg={"package_status": "BLOCKED", "finalized_at": "2026-10-16T03:30:00Z",
                                                      "gaps": ["missing_or_empty_file:safety/software_safety_analysis.md",
                                                               "unresolved_finding:SWE.4:GATE_REWORK"]})
    b = _ws(root, "WO-X-r2", created="2026-10-16T04:00:00Z",
            lines=[{**REJECT, "ts": "2026-10-16T04:10:00Z"}, {"ts": "2026-10-16T02:00:00Z", **{k: v for k, v in REJECT.items() if k != "ts"}}],
            inspections=[{"phase": "SWE.2", "verdict": "REWORK", "recorded_at": "2026-10-16T04:05:00Z",
                          "items": {"SWE2-03": {"verdict": "FAIL"}, "SWE2-01": {"verdict": "PASS"}}},
                         {"phase": "SWE.1", "verdict": "REWORK", "recorded_at": "2026-10-15T13:00:00Z",  # carried over
                          "items": {"SWE1-06": {"verdict": "FAIL"}}}],
            defects=[{"kind": "CODE", "status": "REJECTED", "detected_phase": "SWE.6", "target_phase": "SWE.3",
                      "history": [{"status": "OPEN", "ts": "2026-10-16T04:20:00Z"}]}],
            pkg={"package_status": "BLOCKED", "finalized_at": "2026-10-16T04:30:00Z",
                 "gaps": ["missing_or_empty_file:safety/software_safety_analysis.md"]})
    return [a, b]


# ---- CRE-T005 / AT-002 -----------------------------------------------------------------------------------------
def test_migration_is_additive_on_the_002_incident_database(env):
    p = env / "inc.sqlite3"
    s = IncidentStore(p)
    inc, _ = s.open_or_dedup("fabro:READINESS_FAILURE:-:0.4", "fabro", "READINESS_FAILURE", "CRITICAL", None, "down", True)
    cre = CREStore(p)
    assert cre.version() == SCHEMA_VERSION and cre.migrate() == []  # idempotent
    assert IncidentStore(p).get(inc["incident_id"])["fault_type"] == "READINESS_FAILURE"  # 002 data untouched
    tables = {r[0] for r in sqlite3.connect(p).execute("select name from sqlite_master where type='table'")}
    assert {"incidents", "incident_history", "repair_attempts", "cre_events", "cre_failure_observations",
            "cre_capa_history", "cre_promotion_decisions"} <= tables


def test_events_validate_and_reject_missing_provenance(env):
    ev = E.build("cre.failure_observed", "k1", {"error_code": "BUILD_FAIL"}, policy_sha256=POL, correlation_id="WO-1")
    assert E.schema_errors(ev) == [] and ev["event_id"] == E.event_id("cre.failure_observed", "k1")
    for bad in ({**ev, "data_status": "PASS"}, {**ev, "ts_utc": "yesterday"}, {k: v for k, v in ev.items() if k != "policy_sha256"},
                {**ev, "event_id": "x"}):
        with pytest.raises(ValueError, match="CRE_EVENT_SCHEMA"):
            E.record(CREStore(env / "i.sqlite3"), bad)


def test_event_is_mirrored_once_into_the_002_ledger_with_a_payload_ref(env):
    from forge_factory.events.emit import read_segment
    store = CREStore(env / "i.sqlite3")
    ev = E.build("cre.circuit_opened", "dep|1", {"dependency": "mcp"}, policy_sha256=POL, correlation_id="c")
    assert E.record(store, ev) is True and E.record(store, ev) is False
    seg = [x for x in read_segment() if x.get("payload_ref") == f"cre-event:{ev['event_id']}"]
    assert len(seg) == 1 and seg[0]["event_id"] == "fx-" + ev["event_id"] and seg[0]["channel"] == "supervisor"
    assert seg[0]["schema_version"] == "0.4"  # the 002 envelope contract is unchanged


# ---- CRE-T006 / AT-003 -----------------------------------------------------------------------------------------
def test_duplicate_reordered_and_restarted_ingest_yields_identical_state(env):
    wss = _two_attempts(env)
    a = CREStore(env / "a.sqlite3")
    first = O.ingest(a, POL, wss, incidents=False)
    again = O.ingest(CREStore(env / "a.sqlite3"), POL, wss + wss, incidents=False)  # restart + double delivery
    assert first["new"] == first["observations"] and again["new"] == 0
    ra = O.reduce(a)
    b = CREStore(env / "b.sqlite3")
    obs = [o for ws in wss for o in O.from_workspace(ws)]
    random.Random(7).shuffle(obs)
    for o in obs:  # reordered delivery
        b.insert_observation(o)
    assert O.reduce(b) == ra
    assert [o["obs_id"] for o in a.observations()] == [o["obs_id"] for o in b.observations()]


# ---- CRE-T007 / AT-004 -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("raw,cls,route", [
    ("software/hal/x.c:12:5: error: expected ';' before '}' token", "PRODUCT_QUALITY", "SWE_REWORK"),
    ("BUILD_FAIL:test_rcc.c", "PRODUCT_QUALITY", "SWE_REWORK"),
    ("MCP request timed out after 30 s (forge-tests-mcp)", "TRANSIENT_DEPENDENCY", "RETRY_BOUNDED"),
    ("HTTP 429 rate limit from upstream", "TRANSIENT_DEPENDENCY", "RETRY_BOUNDED"),
    ("READINESS_FAILURE fabro DOWN", "INFRASTRUCTURE", "REPAIR_ELIGIBLE"),
    ("forge gateway cost cap 2.0 USD reached", "INFRASTRUCTURE", "REQUIRES_OFFLINE_ATTENTION"),
    ("WRITE_SCOPE_DENIED software/tests/target/", "POLICY_SECURITY", "REQUIRES_OFFLINE_ATTENTION"),
    ("something nobody has seen", "UNKNOWN", "REQUIRES_OFFLINE_ATTENTION"),
])
def test_classifier_routes_by_class_at004(raw, cls, route):
    c = T.classify(raw)
    assert (c.failure_class, c.route) == (cls, route)


def test_product_quality_can_never_be_routed_to_infrastructure_repair():
    for _, cat, _ in T.RULES:
        if T.CLASS_OF[cat] == "PRODUCT_QUALITY":
            assert T.ROUTE_OF["PRODUCT_QUALITY"] == "SWE_REWORK" and cat not in T.NOT_REPAIRABLE
    assert all(c in T.CATEGORIES for c in T.CLASS_OF) and set(T.CLASS_OF.values()) <= set(T.CLASSES)


# ---- CRE-T008 / AT-005 -----------------------------------------------------------------------------------------
def test_volatile_parts_do_not_split_and_distinct_codes_do_not_merge():
    a = T.classify("/tmp/ws-1234/software/tests/unit/test_rcc.c:250:11: error: call to undeclared function at 2026-10-16T03:00:00Z")
    b = T.classify("/media/x/WO-9-r77/workspace/software/tests/unit/test_rcc.c:7:3: error: call to undeclared function at 2026-10-17T01:00:00Z")
    assert a == b
    fp = lambda c, op="SWE.4/author": T.fingerprint(c.failure_class, "gate", c.error_code, op)  # noqa: E731
    assert fp(a) == fp(b)
    assert fp(a) != fp(T.classify("MISRA-10.6 cppcheck finding"))  # distinct error code
    assert fp(a) != fp(a, "SWE.5/author")  # distinct scope
    assert T.normalize("DEF-002 in WO-0002-STM32N6-RCC-r75 at 2026-10-16T03:45:31Z sha 9f86d081884c7d65") == \
        "DEF-<id> in WO-<id> at <ts> sha <hash>"


def test_recurrence_counts_distinct_attempts_and_aliases_are_audited(env):
    store = CREStore(env / "r.sqlite3")
    O.ingest(store, POL, _two_attempts(env), incidents=False)
    modes = {m["error_code"]: m for m in O.reduce(store)}
    tool = modes["REQUIRED_TOOL_NOT_PASS:run_unit"]
    assert tool["distinct_attempts"] == 2 and tool["recurring"] == 1 and tool["distinct_orders"] == 1
    assert modes["REWORK_BUDGET_EXHAUSTED"]["significant"] == 1  # BLOCKED outcome
    assert "INSPECTION_FAIL:SWE1-06" not in modes  # carried-over inspection of a resumed source is not this run's
    assert modes["PACKAGE_GAP:owner_deferred_document"]["occurrences"] == 0  # deferred: recorded, not a failure
    store.add_alias(tool["fingerprint"], modes["REWORK_BUDGET_EXHAUSTED"]["fingerprint"], "MERGE", "same root", "owner")
    assert store.aliases()[0]["actor"] == "owner"
    assert {o["fingerprint"] for o in store.observations()} >= {tool["fingerprint"]}  # originals kept
    with pytest.raises(sqlite3.IntegrityError):
        store.add_alias("a", "b", "GUESS", "x", "y")


# ---- CRE-T009 / AT-006 -----------------------------------------------------------------------------------------
def test_import_never_fabricates_a_verified_root_cause_and_history_is_append_only(env):
    store = CREStore(env / "h.sqlite3")
    O.ingest(store, POL, _two_attempts(env), incidents=False)
    modes = O.reduce(store)
    assert {m["root_cause_status"] for m in modes} == {"UNKNOWN"}
    fp = modes[0]["fingerprint"]
    store.set_root_cause(fp, "HYPOTHESIS", hypothesis="model wrote the report too late")
    O.reduce(store)  # projection rebuild keeps analysis results
    assert {m["fingerprint"]: m for m in store.failure_modes()}[fp]["root_cause_status"] == "HYPOTHESIS"
    with pytest.raises(ValueError):
        store.set_root_cause(fp, "PROBABLY")
    c = sqlite3.connect(store.path)
    for sql in ("UPDATE cre_failure_observations SET excerpt='x'", "DELETE FROM cre_events"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            c.execute(sql)


# ---- CRE-T010 / AT-007 -----------------------------------------------------------------------------------------
def test_secrets_reasoning_and_size_are_controlled_and_correlation_is_stable(env):
    ws = _ws(env, "WO-S-r1", lines=[{"ts": "2026-10-16T03:10:00Z", "phase": "SWE.3", "step": "author",
                                     "result": "REJECTED", "status": "BLOCKED",
                                     "issues": ["BUILD_FAIL token=ghp_abcdefghijklmnopqrstuvwxyz0123456789 " + "x" * 5000]}])
    store = CREStore(env / "s.sqlite3")
    O.ingest(store, POL, [ws], incidents=False)
    [o] = store.observations()
    [ev] = store.events("cre.failure_observed")
    assert "ghp_" not in o["excerpt"] and "ghp_" not in json.dumps(ev) and len(o["excerpt"]) <= 200
    assert ev["source_type"] == "AGENT_HYPOTHESIS"  # an agent's own report is not deterministic evidence
    assert ev["evidence_sha256"] == o["evidence_sha256"] and ev["evidence_refs"] == [o["source_ref"]]
    assert len(json.dumps(ev["payload"])) < 4000
    with pytest.raises(ValueError, match="FORBIDDEN_KEY"):
        E.build("cre.capa_opened", "k", {"reasoning": "secret thoughts"}, policy_sha256=POL, correlation_id="c")
    store2 = CREStore(env / "s2.sqlite3")
    O.ingest(store2, POL, [ws], incidents=False)
    assert [e["event_id"] for e in store2.events()] == [e["event_id"] for e in store.events()]


def test_superseded_observation_is_retracted_by_record_never_deleted(env):
    """Live finding: run_not_completed after a BLOCKED phase was first classified as orchestration (53 records)."""
    wss = _two_attempts(env)
    store = CREStore(env / "x.sqlite3")
    O.ingest(store, POL, wss, incidents=False)
    stale = {**O.from_workspace(wss[0])[0], "obs_id": E.event_id("cre.failure_observed", "old-rule"),
             "error_code": "RUN_NOT_COMPLETED", "fingerprint": "cfp1-" + "0" * 40}
    store.insert_observation(stale)
    stats = O.ingest(store, POL, wss, incidents=False)
    assert stats["retracted"] == 1 and stats["new"] == 0
    assert stale["obs_id"] not in {o["obs_id"] for o in store.observations()}
    assert stale["obs_id"] in {o["obs_id"] for o in store.observations(include_retracted=True)}
    [r] = store.retractions()
    assert r["classifier_version"] == T.CLASSIFIER_VERSION and "superseded" in r["reason"]
    assert "cfp1-" + "0" * 40 not in {m["fingerprint"] for m in O.reduce(store)}
    assert O.ingest(store, POL, wss, incidents=False)["retracted"] == 0  # idempotent
