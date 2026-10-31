"""Independent replay fixtures, no real model/configuration comparison claim."""

from pathlib import Path

import pytest
from forge_factory.afo import configuration_comparison as C
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, canonical, digest, immutable_json
from forge_factory.common import state_dir
from test_da014_qualification import identity


def put(path, doc):
    immutable_json(path, doc)
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": C.hashlib.sha256(raw).hexdigest()}


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    a = identity()
    b = {**a, "context_tokens": 4096}
    catalogue = tmp_path / "targeted-catalogue.json"
    put(
        catalogue,
        {
            "cases": [
                {"case_id": "comparison-A", "expected": "ACCEPTED", "recoverable": True, "repeats": 1},
                {"case_id": "comparison-B", "expected": "BLOCKED", "recoverable": False, "repeats": 1},
            ]
        },
    )
    monkeypatch.setitem(Q.CATALOGUES, "targeted", str(catalogue))
    base = Q.freeze("targeted", tmp_path / "base-initial.json", identity=a)
    controls = {k: put(tmp_path / (k + ".json"), {"kind": k, "scope": "SYNTHETIC_COMPARISON_ONLY"}) for k in C.CONTROLS}
    plan = {
        "schema": "forge-c/configuration-comparison-plan/1",
        "comparison_factor": "context_tokens",
        "baseline_identity": a,
        "candidate_identity": b,
        "case_ids": Q.frozen_trials(base["cases"]),
        "controls": controls,
        "registered_at": 100,
    }
    plan_ref = put(tmp_path / "comparison-plan.json", plan)
    bundles = []
    for lane, ident in (("baseline", a), ("candidate", b)):
        manifest = Q.freeze(
            "targeted",
            tmp_path / (lane + "-manifest.json"),
            identity=ident,
            inputs=[*[r["path"] for r in controls.values()], plan_ref["path"]],
        )
        refs = []
        for i, trial in enumerate(plan["case_ids"]):
            row = {
                "trial_id": trial,
                "manifest_sha256": digest(manifest),
                "native_run_id": lane + "-native-" + str(i),
                "observed": "BLOCKED" if i == 0 else "ACCEPTED",
                "reported_tokens": 30,
            }
            m = {
                **dict.fromkeys(C.BOOL_FACTS, False),
                "useful_plan": i != 0,
                "accepted_work_order": i != 0,
                "closed_defect_ids": ["defect-" + str(i)] if i != 0 else [],
                "started_at": 101,
                "input_tokens": 10,
                "output_tokens": 15,
                "learning_tokens": 5,
                "wall_seconds": 2,
                "learning_wall_seconds": 1,
                "includes_all_attempts_and_learning": True,
            }
            settings = put(
                tmp_path / (lane + "-settings-" + str(i) + ".json"), {"identity": ident, "native_run_id": row["native_run_id"]}
            )
            m["effective_settings_ref"] = settings
            oracle = put(tmp_path / (lane + "-oracle-" + str(i) + ".json"), {"synthetic_independent_measurement": m})
            audit = {
                "schema": "forge-c/independent-qualification-audit/1",
                "producer": "REFERENCE_HARNESS",
                "manifest_sha256": digest(manifest),
                "source_revision": manifest["source_revision"],
                "trial_id": trial,
                "observation_sha256": digest(row),
                "oracle_refs": [oracle, settings],
                "observations": {"comparison_measurement": m},
            }
            audit_path = state_dir() / "lrtx/qualification-audits" / digest(manifest) / (trial.replace(":", "-") + ".json")
            put(audit_path, audit)
            refs.append(put(tmp_path / (lane + "-row-" + str(i) + ".json"), row))
        bundles.append(
            {
                "manifest_ref": {
                    "path": str(tmp_path / (lane + "-manifest.json")),
                    "sha256": C.hashlib.sha256((tmp_path / (lane + "-manifest.json")).read_bytes()).hexdigest(),
                },
                "plan_ref": plan_ref,
                "result_refs": refs,
            }
        )
    return plan, bundles[0], bundles[1], tmp_path


def test_missing_live_comparison_is_not_run(data):
    plan, _, _, _ = data
    r = C.report(plan)
    assert r["status"] == "NOT_RUN" and r["rcc_success_prerequisite"] is False
    assert r["automatic_selection"] is False and r["automatic_deployment"] is False
    assert set(r["blockers"]) == {"BASELINE_MEASUREMENT_NOT_RUN", "CANDIDATE_MEASUREMENT_NOT_RUN"}


def test_measured_report_counts_failed_attempt_costs_and_learning(data):
    plan, a, b, _ = data
    r = C.report(plan, a, b)
    assert r["status"] == "MEASURED" and r["recommendation"] == "REVIEW_MEASURED_RESULTS"
    for lane in ("baseline", "candidate"):
        row = r[lane]
        assert row["recorded"] == 2 and row["metrics"]["failed_or_blocked"] == 1
        assert row["metrics"]["accepted_work_orders"] == 1
        assert row["total_tokens"] == 60 and row["total_wall_seconds"] == 6
        assert row["tokens_per_accepted_work_order"] == 60
        assert row["costs"]["learning_tokens"] == 10 and row["costs"]["learning_wall_seconds"] == 2
        assert row["end_to_end_output_tokens_per_second"] == 5
        assert row["backend_decode_tokens_per_second"] is None


def test_missing_row_cannot_shrink_denominator_or_hide_cost(data):
    plan, a, b, _ = data
    b["result_refs"].pop()
    r = C.report(plan, a, b)
    assert r["status"] == "INCOMPLETE" and len(r["candidate"]["missing"]) == 1
    assert r["candidate"]["total_tokens"] is None
    assert r["candidate"]["known_subset_tokens"] == 30
    assert r["candidate"]["end_to_end_output_tokens_per_second"] is None


def test_same_model_agreement_and_missing_audit_is_unknown(data):
    plan, a, b, _ = data
    manifest = C.O.bound_json(b["manifest_ref"])
    trial = plan["case_ids"][0]
    (state_dir() / "lrtx/qualification-audits" / digest(manifest) / (trial.replace(":", "-") + ".json")).unlink()
    r = C.report(plan, a, b)
    assert r["status"] == "INCOMPLETE"
    assert r["candidate"]["unknown"][0]["reason"] == "INDEPENDENT_AUDIT_MISSING"
    assert r["candidate"]["total_tokens"] is None


@pytest.mark.parametrize(
    "change",
    [
        "multi-factor",
        "role",
        "hash",
        "duplicate-case",
        "factor",
        "candidate-time",
        "candidate-plan",
        "negative",
        "nonfinite",
        "bool-cost",
        "missing-learning",
        "token-mismatch",
        "oracle",
        "duplicate-row",
    ],
)
def test_changed_controls_invalid_measurements_or_identity_refused_or_unknown(data, change):
    plan, a, b, tmp = data
    if change == "multi-factor":
        plan["candidate_identity"]["reasoning"] = "high"
    elif change == "role":
        plan["candidate_identity"]["role"] = "swe3-inspector"
    elif change == "hash":
        Path(plan["controls"]["prompts"]["path"]).chmod(0o600)
        Path(plan["controls"]["prompts"]["path"]).write_text("{}")
    elif change == "duplicate-case":
        plan["case_ids"].append(plan["case_ids"][0])
    elif change == "factor":
        plan["comparison_factor"] = "anything"
    elif change == "candidate-plan":
        b.pop("plan_ref")
    elif change == "duplicate-row":
        b["result_refs"][1] = b["result_refs"][0]
    else:
        manifest = C.O.bound_json(b["manifest_ref"])
        trial = plan["case_ids"][0]
        path = state_dir() / "lrtx/qualification-audits" / digest(manifest) / (trial.replace(":", "-") + ".json")
        audit = C.O.read_json(path)
        m = audit["observations"]["comparison_measurement"]
        if change == "candidate-time":
            m["started_at"] = 90
        elif change == "negative":
            m["input_tokens"] = -1
        elif change == "nonfinite":
            m["wall_seconds"] = float("inf")
        elif change == "bool-cost":
            m["learning_tokens"] = True
        elif change == "missing-learning":
            m["includes_all_attempts_and_learning"] = False
        elif change == "token-mismatch":
            m["input_tokens"] = 12
        elif change == "oracle":
            Path(audit["oracle_refs"][0]["path"]).unlink()
        if change != "oracle":
            path.chmod(0o600)
            if change == "nonfinite":
                # Invalid JSON must be rejected before numeric interpretation.
                import json

                path.write_text(json.dumps(audit))
            else:
                path.write_bytes(canonical(audit))
    if change in ("missing-learning", "token-mismatch"):
        r = C.report(plan, a, b)
        assert r["status"] == "INCOMPLETE" and r["candidate"]["total_tokens"] is None
    else:
        with pytest.raises((Refused, KeyError)):
            C.report(plan, a, b)


def test_independent_quality_regression_is_not_recommended(data):
    plan, a, b, _ = data
    manifest = C.O.bound_json(b["manifest_ref"])
    trial = plan["case_ids"][0]
    path = state_dir() / "lrtx/qualification-audits" / digest(manifest) / (trial.replace(":", "-") + ".json")
    audit = C.O.read_json(path)
    audit["observations"]["comparison_measurement"]["false_acceptance"] = True
    path.chmod(0o600)
    path.write_bytes(canonical(audit))
    r = C.report(plan, a, b)
    assert r["status"] == "MEASURED"
    assert r["recommendation"] == "REJECT_QUALITY_REGRESSION"
    assert r["quality_regressions"] == ["false_acceptance"]


def test_cli_reports_missing_comparison_without_claiming_success(data):
    plan, _, _, tmp = data
    out = tmp / "cli-report.json"
    rc = C.main(["--plan", str(tmp / "comparison-plan.json"), "--out", str(out)])
    assert rc == 2 and C.O.read_json(out)["status"] == "NOT_RUN"
