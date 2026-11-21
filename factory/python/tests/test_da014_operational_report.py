"""Source-based campaign accounting with synthetic clocks; not a live soak."""

import copy
import json

import pytest
from forge_factory.afo import operational_campaign as R
from forge_factory.afo import operational_work as W
from forge_factory.afo import soak
from forge_factory.afo.durable import Refused, digest
from test_da014_fault_observer import external_case, fixture_evaluation
from test_da014_operational_work import audited, put, setup, work  # noqa: F401


def timeline(p, *, start=90):
    path = soak.path("soak-operational-report")
    rows = [
        {
            "kind": "start",
            "soak_id": "soak-operational-report",
            "wall": start,
            "mono": start,
            "boot_id": "fixture-boot",
            "interval_s": 30,
            "target_hours": 24,
        },
        *[
            {
                "kind": "sample",
                "wall": wall,
                "mono": wall,
                "boot_id": "fixture-boot",
                "healthy": True,
                "probes": dict.fromkeys(("conductor", "fabro", "gateway", "data_volume"), True),
            }
            for wall in (100, 130)
        ],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    put(path.with_suffix(".manifest.json"), p.manifest)
    return path, rows


def write_rows(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_legacy_work_and_continuity_success_flags_do_not_count(work):  # noqa: F811
    p = work
    timeline(p)
    ref = put(
        p.tmp / "legacy-work.json",
        {"manifest_sha256": digest(p.manifest), "native_run_id": "native-fixture", "independently_verified": True},
    )
    continuation = put(
        p.tmp / "legacy-continuity.json",
        {
            "manifest_sha256": digest(p.manifest),
            "later_authorized_job_admitted": True,
            "service_relaunched_manually": False,
            "observed_until": 9999999999,
        },
    )
    result = R.report(p.manifest, "soak-operational-report", work_refs=[ref], continuity_refs=[continuation])
    assert result["real_work_exposures"] == 0 and result["unverified_work_records"] == 1
    assert result["post_campaign_continuity"] is False and result["status"] == "INCOMPLETE"


def test_real_work_is_recomputed_from_existing_audit_and_native_capture(work):  # noqa: F811
    p = work
    timeline(p)
    row, _, _ = audited(p)
    result = W.evaluate(p.manifest, p.ref, row, p.samples)
    ref = put(p.tmp / "verified-work.json", result)
    report = R.report(p.manifest, "soak-operational-report", work_refs=[ref])
    assert report["real_work_exposures"] == 1 and report["unverified_work_records"] == 0
    assert report["manifest_bound"] is True and report["telemetry_complete"] is True
    assert report["status"] == "INCOMPLETE" and report["missing_faults"]


def test_verified_work_after_campaign_end_is_only_post_campaign_evidence(work):  # noqa: F811
    p = work
    timeline(p, start=100 - 24 * 3600)
    row, _, _ = audited(p)
    ref = put(p.tmp / "post-campaign-work.json", W.evaluate(p.manifest, p.ref, row, p.samples))
    report = R.report(p.manifest, "soak-operational-report", work_refs=[ref])
    assert report["real_work_exposures"] == 0
    assert report["post_campaign_work_exposures"] == 1
    assert report["unverified_work_records"] == 0


def test_work_outside_the_observed_campaign_window_does_not_count(work):  # noqa: F811
    p = work
    path, rows = timeline(p)
    rows = [{**r, "wall": r["wall"] + 1000, "mono": r["mono"] + 1000} for r in rows]
    write_rows(path, rows)
    row, _, _ = audited(p)
    ref = put(p.tmp / "before-campaign-work.json", W.evaluate(p.manifest, p.ref, row, p.samples))
    report = R.report(p.manifest, "soak-operational-report", work_refs=[ref])
    assert report["real_work_exposures"] == 0 and report["unverified_work_records"] == 1


@pytest.mark.parametrize("change", ["duration", "nonfinite", "duplicate-clock", "unknown-boot", "bad-boot", "wrong-soak"])
def test_invalid_or_shortened_campaign_window_is_refused(work, change):  # noqa: F811
    p = work
    path, rows = timeline(p)
    if change == "duration":
        rows[0]["target_hours"] = 0
    if change == "nonfinite":
        rows[-1]["wall"] = float("nan")
    if change == "duplicate-clock":
        rows[-1]["wall"] = rows[1]["wall"]
    if change == "unknown-boot":
        rows[-1]["boot_id"] = "unknown"
    if change == "bad-boot":
        rows[-1]["boot_id"] = ["fixture-boot"]
    if change == "wrong-soak":
        rows[0]["soak_id"] = "soak-other-id"
    write_rows(path, rows)
    with pytest.raises(Refused):
        R.report(p.manifest, "soak-operational-report")


@pytest.mark.parametrize(
    "change", ["clock-jump", "negative-monotonic", "missing-probe", "truthy-probe", "bad-probes", "start-gap"]
)
def test_missing_or_contradictory_telemetry_is_not_complete(work, change):  # noqa: F811
    p = work
    path, rows = timeline(p)
    if change == "clock-jump":
        rows[-1]["mono"] += 100
    if change == "negative-monotonic":
        rows[-1]["mono"] = 0
    if change == "missing-probe":
        del rows[-1]["probes"]["conductor"]
    if change == "truthy-probe":
        rows[-1]["probes"]["conductor"] = "true"
    if change == "bad-probes":
        rows[-1]["probes"] = list(rows[-1]["probes"])
    if change == "start-gap":
        rows[0]["wall"] -= 1000
        rows[0]["mono"] -= 1000
    write_rows(path, rows)
    result = R.report(p.manifest, "soak-operational-report")
    assert result["telemetry_complete"] is False and result["status"] != "PASS"
    if change != "start-gap":
        assert result["gross_24_7_window"]["available_seconds"] == 0
        assert any(r["control_plane"] == "UNKNOWN" for r in result["gross_24_7_window"]["intervals"])


@pytest.mark.parametrize(
    ("changed", "control_state", "worker_state"),
    [({"gateway": None}, "AVAILABLE", "UNKNOWN"), ({"conductor": None}, "UNKNOWN", "READY"),
     ({"gateway": None, "data_volume": False}, "AVAILABLE", "UNREADY")],
)
def test_campaign_keeps_control_and_worker_observations_independent(work, changed, control_state, worker_state):  # noqa: F811
    p = work
    path, rows = timeline(p)
    for sample in rows[1:]:
        sample["probes"].update(changed)
    write_rows(path, rows)
    result = R.report(p.manifest, "soak-operational-report")
    assert result["telemetry_complete"] is False
    gross = result["gross_24_7_window"]
    interval = next(row for row in gross["intervals"] if row["start"] == 100)
    assert (interval["control_plane"], interval["worker"]) == (control_state, worker_state)
    assert gross["available_seconds"] == (30 if control_state == "AVAILABLE" else 0)
    assert gross["worker_ready_seconds"] == (30 if worker_state == "READY" else 0)
    assert gross["control_plane_unknown_seconds"] == 10 + (30 if control_state == "UNKNOWN" else 0)
    assert gross["worker_unknown_seconds"] == 10 + (30 if worker_state == "UNKNOWN" else 0)


@pytest.mark.parametrize("when", ["in-window", "before-start", "after-last-sample"])
def test_replayed_fault_is_bound_to_the_observed_campaign_window(work, when):  # noqa: F811
    p = work
    path, rows = timeline(p)
    if when == "before-start":
        rows = [{**r, "wall": r["wall"] + 30, "mono": r["mono"] + 30} for r in rows]
    elif when == "after-last-sample":
        rows[-1].update(wall=115, mono=115)
    write_rows(path, rows)
    receipt, captures = fixture_evaluation(p)
    from forge_factory.afo import fault_observer

    fault = fault_observer.evaluate(p.manifest, p.ref, receipt, captures, None)
    assert fault["independently_restored"] is True
    ref = put(p.tmp / "observed-crash.json", fault)
    report = R.report(p.manifest, "soak-operational-report", fault_refs=[ref])
    assert report["out_of_window_faults"] == ([] if when == "in-window" else ["crash"])
    assert "crash" in report["failed_faults"]  # Native recovery still requires an independent host audit.


@pytest.mark.parametrize(
    ("scenario", "unexplained", "accounted", "uptime"),
    [
        ("matched", 0, True, 20),
        ("wrong-boot", 1, False, 20),
        ("outside-transition", 1, False, 20),
        ("too-long", 1, False, 20),
        ("unknown-probe", 2, False, 20),
        ("extra-reboot", 1, True, 0),
    ],
)
def test_only_a_matching_replayed_reboot_accounts_for_the_gap(work, scenario, unexplained, accounted, uptime):  # noqa: F811
    from forge_factory.afo import fault_observer as observer

    p = work
    receipt, captures = external_case(p, "reboot")
    for i, ref in enumerate(captures):
        capture = observer.bound_json(ref)
        capture["boot_id"] = "old-boot" if i == 0 else "new-boot"
        capture["health"]["gateway"] = True
        captures[i] = put(p.tmp / f"reboot-capture-{i}.json", capture)
    proof = observer.evaluate(p.manifest, p.ref, receipt, captures, None)
    assert proof["independently_restored"] is True
    fault_ref = put(p.tmp / "reboot-proof.json", proof)
    path, rows = timeline(p)
    rows[0]["boot_id"] = rows[1]["boot_id"] = "old-boot"
    rows[2]["boot_id"] = "unrelated-boot" if scenario == "wrong-boot" else "new-boot"
    if scenario == "too-long":
        late_wall = 101 + p.manifest["bounds"]["probe_gap_seconds"]
        rows[2].update(wall=late_wall, mono=late_wall)
    rows.append({**rows[2], "wall": rows[2]["wall"] + 20, "mono": rows[2]["mono"] + 20})
    if scenario == "outside-transition":
        rows[1].update(wall=106, mono=106)
    if scenario == "unknown-probe":
        rows[1]["probes"].pop("gateway")
    if scenario == "extra-reboot":
        rows[-1]["boot_id"] = "extra-boot"
    write_rows(path, rows)

    report = R.report(p.manifest, "soak-operational-report", fault_refs=[fault_ref])
    assert report["telemetry_complete"] is False
    assert report["unexplained_telemetry_intervals"] == unexplained
    assert report["accounted_reboot_intervals"] == ([{"start": 100, "end": 130}] if accounted else [])
    assert report["gross_24_7_window"]["available_seconds"] == uptime
    assert "reboot" in report["failed_faults"]


@pytest.mark.parametrize(
    ("case", "at", "recovery", "result"),
    [
        ("crash", 95, 9, False),
        ("crash", 95, 4, True),
        ("crash", 100, 0, False),
        ("later-authorized-intake", 99, 1, False),
        ("later-authorized-intake", 100, 10, True),
        ("later-authorized-intake", 1399, 2, False),
        ("post-campaign-continuity", 100, 0, True),
        ("post-campaign-continuity", 300, 0, False),
    ],
)
def test_fault_windows_distinguish_campaign_and_continuation(case, at, recovery, result):
    record = {"fault": case, "restoration_seconds": recovery}
    assert R.fault_in_window({"bounds": {"post_campaign_seconds": 1200}}, record, at, 80, 100, 1400) is result


def test_a_soak_without_its_frozen_manifest_cannot_be_bound(work):  # noqa: F811
    p = work
    path, _ = timeline(p)
    path.with_suffix(".manifest.json").unlink()
    assert R.report(p.manifest, "soak-operational-report")["manifest_bound"] is False


@pytest.mark.parametrize("days, verified", [(29, True), (30, False), (30, True)])
def test_rolling_availability_uses_verified_observations_beyond_the_soak(work, monkeypatch, days, verified):  # noqa: F811
    from forge_factory.afo.operational_collection import Collector

    p = work
    path, original = timeline(p)
    head, sample = original[:2]
    head["interval_s"] = 300
    rows = [head]
    for offset in range(0, days * 86400 + 1, 300):
        at = head["wall"] + offset
        rows.append({**sample, "wall": at, "mono": at})
    write_rows(path, rows)
    if verified:
        def replay(_):
            return {"history_sha256": digest(rows), "status": "SOURCE_REPLAY_PASS",
                    "campaign_intent": {"observations": [], "observed_samples": 0}}

        # Exercise the report projection after the collector's source verification.
        monkeypatch.setattr(Collector, "__init__", lambda *_: None)
        monkeypatch.setattr(Collector, "verify", replay)
    report = R.report(p.manifest, "soak-operational-report", observer_plan_ref=p.ref if verified else None)
    assert report["gross_24_7_window"]["window_seconds"] == 86400
    assert report["rolling_30_day_slo"] == "NOT_DEMONSTRATED"
    rolling = report["rolling_30_day_gross_availability"]
    if verified and days == 30:
        assert (rolling["status"], rolling["window_seconds"], rolling["gross_availability"]) == (
            "TARGET_MET", 30 * 86400, 1.0,
        )
    else:
        assert rolling["status"] == "NOT_DEMONSTRATED"
        assert rolling["reason"] == ("FULL_WINDOW_REQUIRED" if verified else "VERIFIED_COLLECTION_REQUIRED")


def continuity(p, *, intake_at=87700, continued_at=86500, last=87700, order="later-order"):
    fixture = put(p.tmp / "later-fixture.json", {"parameters": {"order_id": order}})
    post = put(p.tmp / "post-receipt.json", {"at": continued_at})
    intake = put(p.tmp / "later-receipt.json", {"at": intake_at, "fixture_ref": fixture})
    samples = [put(p.tmp / "post-first.json", {"wall": 100}), put(p.tmp / "post-last.json", {"wall": last})]
    records = [
        {
            "fault": "post-campaign-continuity",
            "plan_ref": p.ref,
            "sample_refs": samples,
            "injection_ref": post,
            "independently_restored": True,
            "observation_gaps": False,
        },
        {
            "fault": "later-authorized-intake",
            "plan_ref": p.ref,
            "injection_ref": intake,
            "independently_restored": True,
            "observation_gaps": False,
        },
    ]
    evidence = [
        {"plan_ref": p.ref, "independently_verified": True, "order_id": order, "native_terminal_observed_at": intake_at + 30}
    ]
    evidence[0].update(attempt_created_at=intake_at + 1, observed_until=intake_at + 30, native_active_observed_at=[])
    return records, evidence


def test_continuity_requires_post_window_and_later_independently_verified_native_work(work):  # noqa: F811
    p = work
    records, evidence = continuity(p)
    # This tests the pure combiner after the report has independently replayed all records.
    assert R.continuity_verdict(p.manifest, records, evidence, 86500) is True
    assert R.continuity_verdict(p.manifest, records, [], 86500) is False
    changed = copy.deepcopy(evidence)
    changed[0]["order_id"] = "different-order"
    assert R.continuity_verdict(p.manifest, records, changed, 86500) is False


@pytest.mark.parametrize(
    "change", ["early-intake", "premature-intake", "early-continuity", "short-window", "different-plan", "gap", "unverified-work"]
)
def test_continuity_cannot_be_declared_from_a_different_or_incomplete_window(work, change):  # noqa: F811
    p = work
    kwargs = {}
    if change == "early-intake":
        kwargs["intake_at"] = 86499
    if change == "premature-intake":
        kwargs["intake_at"] = 87699
    if change == "early-continuity":
        kwargs["continued_at"] = 86499
    if change == "short-window":
        kwargs["last"] = 87699
    records, evidence = continuity(p, **kwargs)
    if change == "different-plan":
        evidence[0]["plan_ref"] = {}
    if change == "gap":
        records[0]["observation_gaps"] = True
    if change == "unverified-work":
        evidence[0]["independently_verified"] = False
    assert R.continuity_verdict(p.manifest, records, evidence, 86500) is False
