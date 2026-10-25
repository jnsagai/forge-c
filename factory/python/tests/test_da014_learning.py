"""Every-outcome capture, qualified memory and chronological comparison fixtures."""

import copy
import json

import pytest
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.common import sha256_file
from forge_factory.knowledge import comparison, experience, qualification
from forge_factory.knowledge.store import LessonStore
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401


@pytest.fixture
def memory(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return LessonStore()


def candidate(store, tmp_path, *, outcome="PASS", version=1):
    eid = experience.capture(
        store,
        "native-job-A",
        "SWE.3",
        outcome,
        facts={"closed_obligations": ["OB-1"]},
        source_refs=["independent-gate:receipt-A"],
        cohort={"model_digest": "fixture", "revision": "abc"},
    )
    c = {
        "contract_version": "2.0",
        "source_kind": "ORDINARY_OUTCOME",
        "version": version,
        "experience_ref": eid,
        "symptoms": "register field mapping",
        "root_cause": "named field mapping must match the reference",
        "remedy": "Use the validated field mapping. " + "x" * 140 + " EXCLUSION: does not apply to STM32H7.",
        "constraints": "Only STM32N6 RCC fixture contract version v1, SWE.3 authors.",
        "applicability": {"phases": ["SWE.3"], "roles": ["swe3-author"], "targets": ["STM32N6"], "source_versions": ["v1"]},
        "evidence_refs": ["independent-gate:receipt-A"],
        "tool_versions": {"gcc": "14"},
        "validation_tests": [{"id": "applicable-and-adverse", "status": "PASS", "evidence_ref": "fixture:oracle"}],
    }
    with store._conn() as db:
        sourcehash = db.execute("SELECT source_hash FROM job_experience WHERE experience_id=?", (eid,)).fetchone()[0]
    cases = [
        {"id": "app", "kind": "APPLICABLE", "producer": "reference", "oracle_sha256": "a" * 64, "expected": "PASS"},
        {"id": "adverse", "kind": "ADVERSE", "producer": "mutant", "oracle_sha256": "b" * 64, "expected": "DETECTED"},
    ]
    manifest = {"lesson_hash": store.content_hash(c), "experience_source_hash": sourcehash, "cases": cases}
    m = tmp_path / f"manifest-{version}.json"
    immutable_json(m, manifest)
    r = tmp_path / f"report-{version}.json"
    immutable_json(
        r,
        {
            "manifest_sha256": sha256_file(m),
            "rows": [
                {
                    "id": x["id"],
                    "producer": x["producer"],
                    "oracle_sha256": x["oracle_sha256"],
                    "observed": x["expected"],
                    "regressions": [],
                }
                for x in cases
            ],
        },
    )
    q = qualification.record(
        store, c, manifest_path=m, manifest_sha256=sha256_file(m), reports=[{"path": str(r), "sha256": sha256_file(r)}]
    )
    c["qualification_ref"] = q
    return c


def test_every_unique_outcome_is_factually_captured_once_with_durable_disposition(memory):
    for outcome in experience.OUTCOMES:
        a = experience.capture(
            memory, "native-A", "SWE.3", outcome, facts={"code": "known"}, source_refs=["receipt:X"], cohort={}
        )
        assert (
            experience.capture(
                memory, "native-A", "SWE.3", outcome, facts={"code": "known"}, source_refs=["receipt:X"], cohort={}
            )
            == a
        )
    result = experience.consolidate(memory, limit=128)
    assert len(result) == len(experience.OUTCOMES)
    assert experience.consolidate(memory) == []
    assert all(r["inference_tokens"] == 0 for r in result)
    report = experience.report(memory)
    assert report["unique_experiences"] == len(experience.OUTCOMES) and report["benefit_status"] == "UNKNOWN"


def test_ordinary_lesson_requires_independent_source_and_actual_scope(memory, tmp_path):
    c = candidate(memory, tmp_path)
    rec = memory.validate(memory.propose(c, phase="SWE.3")["lesson_id"])
    assert rec["state"] == "VALIDATED", rec["_reasons"]
    args = dict(
        query="register mapping",
        run_id="job-B",
        phase="SWE.3",
        role="swe3-author",
        target="STM32N6",
        source_version="v1",
        tool_versions={"gcc": "14"},
    )
    out = memory.find(**args)
    assert len(out["lessons"]) == 1 and "EXCLUSION: does not apply to STM32H7." in out["lessons"][0]["remedy"]
    for k, v in [
        ("phase", "SWE.1"),
        ("role", "swe3-inspector"),
        ("target", "STM32H7"),
        ("source_version", "v2"),
        ("tool_versions", {"gcc": "15"}),
    ]:
        assert memory.find(**{**args, k: v})["lessons"] == []
    report = experience.report(memory)
    assert report["exposures"] == 1 and report["applications"] == report["measured_benefits"] == 0


def test_late_holdout_classification_retracts_older_source_without_erasing_facts(memory, tmp_path):
    c = candidate(memory, tmp_path)
    rec = memory.validate(memory.propose(c, phase="SWE.3")["lesson_id"])
    assert rec["state"] == "VALIDATED"
    correction = experience.capture(
        memory,
        "native-job-A",
        "JOB",
        "PASS",
        facts={"classification": "frozen acceptance cohort"},
        source_refs=["campaign:independent-frozen-manifest"],
        cohort={"evaluation_holdout": True},
    )
    assert "HELDOUT_ACCEPTANCE_SOURCE_CANNOT_BE_DISTILLED" in qualification.issues(memory, c)
    assert not memory.find(
        "register mapping",
        "later-job",
        phase="SWE.3",
        role="swe3-author",
        target="STM32N6",
        source_version="v1",
        tool_versions={"gcc": "14"},
    )["lessons"]
    assert memory.get(rec["lesson_id"])["state"] == "RETRACTED"
    with pytest.raises(Refused, match="HELDOUT_ACCEPTANCE_SOURCE_CANNOT_BE_DISTILLED"):
        candidate(memory, tmp_path, version=2)
    with memory._conn() as db:
        assert db.execute("SELECT COUNT(*) FROM job_experience").fetchone()[0] == 2
        assert db.execute("SELECT 1 FROM job_experience WHERE experience_id=?", (correction,)).fetchone()


def test_afo_and_qualification_job_capture_preserve_evaluation_scope(protocol, tmp_path):  # noqa: F811
    from forge_factory.afo.local_agent import save
    from forge_factory.inspection.engine import Store as InspectionStore
    from test_resume_from import _all_pass

    p = protocol
    memory = LessonStore(tmp_path / "holdout-lessons.sqlite3")
    (p.ws / ".forge-run").mkdir()
    (p.ws / ".forge-run/manifest.json").write_text(json.dumps({"evaluation_holdout": True}))
    for phase, name in (("SWE.1", "software_requirements.md"), ("SWE.2", "software_architecture.md")):
        directory = p.ws / "workproducts" / phase
        directory.mkdir(parents=True)
        (directory / name).write_text("Frozen capture fixture: SWR-001 maps to USPEC-001.\n")
    inspections = InspectionStore(p.ws)
    for phase in ("SWE.1", "SWE.2", "SWE.3"):
        role = phase.lower().replace(".", "")
        baseline = inspections.freeze(phase, role + "-author")
        inspections.record_inspection(phase, role + "-inspector", baseline["baseline_id"], _all_pass(phase))
    p.store.attempt_transition(p.bundle["attempt_id"], "FAILED")
    save(p.store, {**p.job, "state": "FAILED", "qualification_manifest_sha256": "a" * 64})
    before = p.ledger.snapshot("mission-test")
    ids = experience.capture_afo(p.store, memory, lambda _: p.ws)
    assert len(ids) >= 2
    with memory._conn() as db:
        records = [json.loads(r[0]) for r in db.execute("SELECT record FROM job_experience")]
    assert all(r["cohort"].get("evaluation_holdout") is True for r in records)
    assert any(r["phase"] == "SWE.3" for r in records)
    agent = next(r for r in records if r["execution_id"].startswith("controller-agent:"))
    assert agent["cohort"]["qualification_manifest_sha256"] == "a" * 64
    experience.consolidate(memory)
    assert sum(experience.report(memory)["dispositions"].values()) == len(records)
    assert p.ledger.snapshot("mission-test") == before


def test_late_holdout_classification_excludes_old_facts_from_improvement_routing(memory):
    from forge_factory.knowledge.improvement import route

    for native in ("heldout-A", "ordinary-B"):
        experience.capture(
            memory,
            native,
            "SWE.3",
            "FAILED",
            facts={"fingerprint": "same-failure"},
            source_refs=["independent-gate:" + native],
            cohort={"revision": "r1"},
        )
    assert len(route(memory)) == 1
    experience.capture(
        memory,
        "heldout-A",
        "JOB",
        "FAILED",
        facts={"classification": "frozen acceptance"},
        source_refs=["campaign:heldout-manifest"],
        cohort={"evaluation_holdout": True},
    )
    assert route(memory) == []
    assert experience.report(memory)["unique_experiences"] == 3


def test_self_asserted_passes_and_changed_scope_do_not_qualify(memory, tmp_path):
    c = candidate(memory, tmp_path)
    c["applicability"]["targets"] = ["STM32H7"]
    rec = memory.validate(memory.propose(c)["lesson_id"])
    assert rec["state"] == "QUARANTINED" and "QUALIFICATION_NOT_FOR_THIS_SOURCE_SCOPE_VERSION" in rec["_reasons"]
    c["qualification_ref"] = "model-says-pass"
    assert memory.validate(memory.propose(c)["lesson_id"])["state"] == "QUARANTINED"


def test_retraction_removes_qualified_memory_and_retains_consumers(memory, tmp_path):
    c = candidate(memory, tmp_path)
    rec = memory.validate(memory.propose(c, phase="SWE.3")["lesson_id"])
    memory.find(
        "register mapping",
        "job-B",
        phase="SWE.3",
        role="swe3-author",
        target="STM32N6",
        source_version="v1",
        tool_versions={"gcc": "14"},
    )
    result = memory.invalidate_tool_version("gcc", "14")
    assert result[0]["impacted_runs"] == ["job-B"] and memory.get(rec["lesson_id"])["state"] == "RETRACTED"


def test_chronological_comparison_includes_learning_cost_and_holdout(memory):
    manifest = {
        "evaluation_ids": ["B"],
        "learning_ids": ["A"],
        "learning_cutoff": 1,
        "evaluation_start": 2,
        "configuration_sha256": "abc",
    }

    def row(cost):
        return {
            "case_id": "B",
            "configuration_sha256": "abc",
            "manifest_sha256": digest(manifest),
            "independent_pass": True,
            "costs": dict.fromkeys(comparison.COSTS, cost),
        }

    baseline, learned = row(10), row(8)
    learned["costs"]["curation_tokens"] = 100
    assert not comparison.compare(manifest, [baseline], [learned])["benefit_demonstrated"]
    learned["costs"]["curation_tokens"] = 0
    assert comparison.compare(manifest, [baseline], [learned])["benefit_demonstrated"]
    bad = copy.deepcopy(manifest)
    bad["learning_ids"] = ["B"]
    with pytest.raises(Refused):
        comparison.compare(bad, [baseline], [learned])
    learned["costs"].pop("validation_tokens")
    with pytest.raises(Refused):
        comparison.compare(manifest, [baseline], [learned])


def test_detached_failed_job_capture_survives_absent_package_and_keeps_unknown(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from forge_factory.afo.queue import Store
    from forge_factory.knowledge.store import LessonStore
    from forge_factory.knowledge.experience import capture_workorders, consolidate, report

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    store = Store(tmp_path / "afo.sqlite3")
    lessons = LessonStore(tmp_path / "lessons.sqlite3")
    ws = tmp_path / "state/workorders/WO-detached/workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-detached", "driver": "RCC"}))
    (ws / ".forge-run/fabro_run_id").write_text("native-detached")
    client = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "FAILED"}}})
    ids = capture_workorders(store, lessons, client=client)
    assert len(ids) == 1
    assert not capture_workorders(store, lessons, client=client)  # sweep cursor wraps without recharging
    assert capture_workorders(store, lessons, client=client) == ids
    consolidate(lessons)
    metrics = report(lessons)
    assert metrics["unique_experiences"] == 1 and metrics["dispositions"]["DEFERRED_BUDGET"] == 1


def test_retraction_between_selection_and_delivery_fences_exposure(memory, tmp_path):
    c = candidate(memory, tmp_path)
    rec = memory.validate(memory.propose(c, phase="SWE.3")["lesson_id"])
    found = memory.find(
        "register mapping",
        "job-B",
        phase="SWE.3",
        role="swe3-author",
        target="STM32N6",
        source_version="v1",
        tool_versions={"gcc": "14"},
        record_usage=False,
    )
    assert found["lessons"]
    memory.retract(rec["lesson_id"], "independent adverse case invalidated scope")
    assert not memory.expose(found["lessons"], "job-B")
    assert not memory.consumers(rec["lesson_id"])
    assert experience.report(memory)["exposures"] == 0


def test_recurring_facts_link_existing_capa_reproducer_without_fabricating_incident(memory, tmp_path):
    from forge_factory.reliability.capa import CapaRegistry
    from forge_factory.reliability.policy import load
    from forge_factory.reliability.store import CREStore
    from forge_factory.knowledge.improvement import route

    registry = CapaRegistry(CREStore(tmp_path / "cre.sqlite3"), load(), lessons=memory)
    registry.open("CAPA-9001", ["fixture-incident"], ["fixture-fingerprint"], "frozen fixture existing defect")
    registry.triage("CAPA-9001", "fixture root cause for independent reproduction", "RPR-041", "independent-fixture")
    before = len(registry.all())
    for native in ("fixture-native-A", "fixture-native-B"):
        experience.capture(
            memory,
            native,
            "SWE.3",
            "FAILED",
            facts={"fingerprint": "fixture-fingerprint"},
            source_refs=["fixture:independent-finding"],
            cohort={},
        )
    routed = route(memory, capa_registry=registry)
    assert len(routed) == 1 and routed[0]["record"]["lane"] == "CAPA_REPAIR"
    assert len(registry.links("CAPA-9001", "experience")) == 2 and len(registry.all()) == before
    assert routed[0]["record"]["authority"] == "PROPOSAL_ONLY_NO_DEPLOYMENT"
