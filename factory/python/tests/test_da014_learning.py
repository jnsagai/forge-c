"""Every-outcome capture, qualified memory and chronological comparison fixtures."""

import copy
import json

import pytest
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.common import sha256_file
from forge_factory.knowledge import comparison, experience, qualification
from forge_factory.knowledge.store import LessonStore


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
