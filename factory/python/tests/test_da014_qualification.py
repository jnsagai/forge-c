"""Frozen qualification tooling fixtures; these tests make no model/readiness claim."""

import pytest
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.lrtx import role_capability as C


def identity(role="afo-recovery-planner"):
    return {
        "role": role,
        "model_digest": "fixture-digest",
        "precision": "Q8",
        "reasoning": "none",
        "schema_mode": "json_schema",
        "adapter_revision": "candidate",
        "context_tokens": 8192,
        "sampling": {"temperature": 0},
        "task_class": "single-obligation",
    }


def test_history_replay_reports_the_conductor_schema_version(tmp_path):
    import hashlib
    import sqlite3

    from forge_factory.afo.history_qualification import replay
    from forge_factory.afo.queue import Store

    original = tmp_path / "original.sqlite3"
    Store(original)
    with sqlite3.connect(original) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 0
        version = c.execute("SELECT MAX(version) FROM afo_schema_version").fetchone()[0]
        dump = "\n".join(c.iterdump())
    path = tmp_path / "snapshot.sql"
    path.write_text(dump)
    report = replay(path, hashlib.sha256(path.read_bytes()).hexdigest(),
                    tmp_path / "offline-copy.sqlite3", tmp_path / "report.json")
    assert report["schema_before"] == report["schema_after"] == version
    assert report["original_source_mutated"] is False and report["new_live_inference"] is False


def test_protocol_freezes_twenty_times_five_and_does_not_claim_dryrun_qualification(tmp_path):
    m = Q.freeze("protocol", tmp_path / "campaign.json", identity=identity())
    assert len(m["cases"]) == 20 and sum(c["repeats"] for c in m["cases"]) == 100
    report = Q.preflight(m)
    assert report["status"] == "BLOCKED" and report["local_model_capability"] == "NOT_RUN"
    assert Q.protocol_report(m, [])["status"] == "NOT_RUN"
    m["cases"][0]["repeats"] = 6
    with pytest.raises(Refused):
        Q.validate(m)


def test_protocol_blanket_blocks_and_missing_checks_cannot_pass(tmp_path):
    m = Q.freeze("protocol", tmp_path / "campaign.json", identity=identity())
    rows = []
    for c in m["cases"]:
        for i in range(5):
            rows.append(
                {
                    "trial_id": f"{c['case_id']}:{i}",
                    "manifest_sha256": digest(m),
                    "observed": "CLOSE_BLOCKED",
                    "native_run_id": f"fixture:{c['case_id']}:{i}",
                    "receipt": {"admissibility_state": "ACCEPTED", "decision": "CLOSE_BLOCKED"},
                    "false_success": False,
                    "duplicate_effects": 0,
                    "authority_escapes": 0,
                }
            )
    report = Q.protocol_report(m, rows)
    assert report["status"] == "FAIL" and report["observed_denominator"] == 100 and report["useful_plan_count"] == 0
    rows[0]["trial_id"] = rows[1]["trial_id"]
    with pytest.raises(Refused):
        Q.protocol_report(m, rows)


def test_product_denominators_and_all_quality_thresholds(tmp_path):
    m = Q.freeze(
        "benchmark",
        tmp_path / "campaign.json",
        identity=identity("swe3-author"),
        baseline={"median_complete_prompt_tokens": 1000},
    )
    rows = [
        {
            "trial_id": m["product_cases"][i]["trial_id"],
            "sealed_ready": i < 27,
            "native_all_six_gates": i < 27,
            "critical_defects": [{"case_id": cid, "independently_detected": True} for cid in m["critical_defect_ids"]],
            "structured_calls": 100,
            "invalid_structured": 0,
            "complete_prompt_tokens": 450,
            "false_ready": False,
            "required_evidence_complete": True,
        }
        for i in range(30)
    ]
    assert Q.product_report(m, rows)["status"] == "PASS"  # synthetic report checker only
    rows[-1]["invalid_structured"] = 30
    assert Q.product_report(m, rows)["status"] == "FAIL"  # exactly 1% is not below 1%
    rows[-1]["invalid_structured"] = 0
    rows[-1]["critical_defects"][0]["independently_detected"] = False
    assert Q.product_report(m, rows)["status"] == "FAIL"


def test_gpio_each_missing_prerequisite_blocks():
    all_ready = dict.fromkeys(("rcc_ready", "qualified_profile", "authoritative_inputs", "frozen_intake", "authorized"), True)
    assert Q.gpio_admission(all_ready)["admit"]
    for k in all_ready:
        assert not Q.gpio_admission({**all_ready, k: False})["admit"]


def test_role_capability_is_exact_and_independent_not_context_advertising(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ident = identity()
    r = tmp_path / "report.json"
    oracle = tmp_path / "oracle.json"
    immutable_json(oracle, {"observed": "fixture-independent-expected"})
    from forge_factory.common import sha256_file

    report = {
        "manifest_sha256": "m",
        "identity_sha256": C.key(ident),
        "status": "PASS",
        "execution_host": "omniverse2",
        "independent_oracle_refs": [{"producer": "reference", "path": str(oracle), "sha256": sha256_file(oracle)}],
        "envelope": {"max_obligations": 1, "work_classes": ["PROTOCOL_DIAGNOSIS"]},
    }
    immutable_json(r, report)
    from forge_factory.common import sha256_file

    ref = C.record(ident, report_path=r, report_sha256=sha256_file(r), expected_manifest_sha256="m")
    assert C.require(ref, ident, semantic_obligations=1)["qualified"]
    for k, v in [("role", "swe3-inspector"), ("precision", "Q4"), ("reasoning", "high"), ("context_tokens", 16384)]:
        with pytest.raises(Refused):
            C.require(ref, {**ident, k: v})
    with pytest.raises(Refused):
        C.require(ref, ident, semantic_obligations=2)
    with pytest.raises(Refused):
        C.require(None, ident)
    # A receipt measured on seeded protocol fixtures admits no product work.
    assert C.require(ref, ident, semantic_obligations=1, work_class="PROTOCOL_DIAGNOSIS")["qualified"]
    with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
        C.require(ref, ident, semantic_obligations=1, work_class="PRODUCT_DIAGNOSIS")
    unclassed = tmp_path / "unclassed.json"
    immutable_json(unclassed, {**report, "envelope": {"max_obligations": 1}})
    with pytest.raises(Refused, match="ROLE_CAPABILITY_WORK_CLASS_UNMEASURED"):
        C.record(ident, report_path=unclassed, report_sha256=sha256_file(unclassed), expected_manifest_sha256="m")


def test_every_role_needs_a_measured_objective_never_an_assumed_size():
    planner = {"selected_obligations": ["USPEC-001"], "work_class": "PROTOCOL_DIAGNOSIS"}
    assert C.measured_objective(planner, "afo-recovery-planner") == (1, "PROTOCOL_DIAGNOSIS")
    assert C.measured_objective({"semantic_obligations": 3, "work_class": "PRODUCT"}, "swe3-author") == (3, "PRODUCT")
    for job, role in [
        ({"work_class": "PRODUCT"}, "swe3-author"),  # author/inspector size unmeasured: no implicit 1
        ({"work_class": "MAINTENANCE"}, "afo-factory-maintainer"),
        ({"semantic_obligations": True, "work_class": "PRODUCT"}, "swe3-inspector"),
        ({"selected_obligations": ["USPEC-001"]}, "afo-recovery-planner"),  # work class unmeasured
        ({"selected_obligations": ["USPEC-001"], "work_class": "ANY"}, "afo-recovery-planner"),
    ]:
        with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
            C.measured_objective(job, role)


def test_operational_campaign_cannot_pass_idle_duration_without_faults_and_later_intake(tmp_path, monkeypatch):
    from forge_factory.afo import soak, operational_campaign as O

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    m = Q.freeze("operation-24", tmp_path / "manifest.json", identity=identity(), model_profile="qwen-fixture")
    soak.start("soak-014-fixture", 24, 30, "AUTH-fixture")
    path = soak.path("soak-014-fixture")
    head = __import__("json").loads(path.read_text().splitlines()[0])
    # Synthetic source timeline tests the report checker; no elapsed/live qualification claim.
    for seconds in (0, 24 * 3600):
        soak._append(
            path,
            {
                "kind": "sample",
                "wall": head["wall"] + seconds,
                "mono": head["mono"] + seconds,
                "boot_id": head["boot_id"],
                "utc": "synthetic-fixture",
                "healthy": True,
                "probes": {"conductor": True, "gateway": True, "fabro": True, "data_volume": True},
            },
        )
    report = O.report(m, "soak-014-fixture")
    assert report["status"] == "FAIL" and report["missing_faults"] and not report["post_campaign_continuity"]
    assert report["gross_24_7_window"]["unavailable_seconds"] > 0 and report["rolling_30_day_slo"] == "NOT_DEMONSTRATED"


def test_independent_inspection_cannot_pass_unknown_or_same_model_agreement():
    claims = {"SWR-001": "PASS"}
    assert (
        Q.inspector_report(
            ["SWR-001"],
            claims,
            [{"obligation_id": "SWR-001", "producer": "QWEN", "pass": True, "evidence_ref": "model:agreement"}],
        )["status"]
        == "FAIL"
    )
    assert (
        Q.inspector_report(
            ["SWR-001"], claims, [{"obligation_id": "SWR-001", "producer": "reference", "pass": None, "evidence_ref": "unknown"}]
        )["status"]
        == "FAIL"
    )
    assert Q.inspector_report([], {}, [])["status"] == "FAIL"
    result = Q.inspector_report(
        ["SWR-001"],
        claims,
        [{"obligation_id": "SWR-001", "producer": "mutant", "pass": False, "evidence_ref": "actual:counterexample"}],
    )
    assert result["escaped_defects"] == ["SWR-001"] and result["status"] == "FAIL"


def test_controlled_comparison_retains_frozen_denominator_and_no_automatic_selection(tmp_path):
    import copy

    manifest = Q.freeze("protocol", tmp_path / "manifest.json", identity=identity())
    baseline = {
        "manifest_sha256": digest(manifest),
        "measured": True,
        "native_run_ids": ["fixture-baseline"],
        "identity": identity(),
        "case_ids": ["frozen-case-A"],
    }
    candidate = copy.deepcopy(baseline)
    candidate["identity"]["precision"] = "Q4"
    candidate["independent_outcomes"] = [{"case_id": "frozen-case-A", "fixture_oracle": "FAIL"}]
    report = Q.configuration_comparison(manifest, baseline, candidate)
    assert report["changed_factor"] == "precision" and report["automatic_selection"] is False
    assert report["automatic_deployment"] is False and report["rcc_success_prerequisite"] is False
    candidate["case_ids"] = []
    with pytest.raises(Refused, match="COMPARISON_DENOMINATOR_OR_ORACLE_MISSING"):
        Q.configuration_comparison(manifest, baseline, candidate)
    candidate["case_ids"] = baseline["case_ids"]
    candidate["identity"]["reasoning"] = "high"
    with pytest.raises(Refused, match="ONE_CONTROLLED_CONFIGURATION_FACTOR_REQUIRED"):
        Q.configuration_comparison(manifest, baseline, candidate)
