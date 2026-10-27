"""Source-based campaign accounting with synthetic clocks; not a live soak."""

import copy
import json

import pytest
from forge_factory.afo import operational_campaign as R
from forge_factory.afo import operational_work as W
from forge_factory.afo import soak
from forge_factory.afo.durable import Refused, digest
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


def test_work_outside_the_observed_campaign_window_does_not_count(work):  # noqa: F811
    p = work
    path, rows = timeline(p)
    rows = [{**r, "wall": r["wall"] + 1000, "mono": r["mono"] + 1000} for r in rows]
    write_rows(path, rows)
    row, _, _ = audited(p)
    ref = put(p.tmp / "before-campaign-work.json", W.evaluate(p.manifest, p.ref, row, p.samples))
    report = R.report(p.manifest, "soak-operational-report", work_refs=[ref])
    assert report["real_work_exposures"] == 0 and report["unverified_work_records"] == 1


@pytest.mark.parametrize("change", ["duration", "nonfinite", "duplicate-clock", "unknown-boot", "wrong-soak"])
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
    if change == "wrong-soak":
        rows[0]["soak_id"] = "soak-other-id"
    write_rows(path, rows)
    with pytest.raises(Refused):
        R.report(p.manifest, "soak-operational-report")


@pytest.mark.parametrize("change", ["clock-jump", "negative-monotonic", "missing-probe", "truthy-probe", "start-gap"])
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
    if change == "start-gap":
        rows[0]["wall"] -= 1000
        rows[0]["mono"] -= 1000
    write_rows(path, rows)
    result = R.report(p.manifest, "soak-operational-report")
    assert result["telemetry_complete"] is False and result["status"] != "PASS"
    if change in ("clock-jump", "negative-monotonic", "missing-probe", "truthy-probe"):
        assert result["gross_24_7_window"]["available_seconds"] == 0
        assert any(r["control_plane"] == "UNKNOWN" for r in result["gross_24_7_window"]["intervals"])


def test_a_soak_without_its_frozen_manifest_cannot_be_bound(work):  # noqa: F811
    p = work
    path, _ = timeline(p)
    path.with_suffix(".manifest.json").unlink()
    assert R.report(p.manifest, "soak-operational-report")["manifest_bound"] is False


def continuity(p, *, intake_at=86500, continued_at=86500, last=87700, order="later-order"):
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
    "change", ["early-intake", "early-continuity", "short-window", "different-plan", "gap", "unverified-work"]
)
def test_continuity_cannot_be_declared_from_a_different_or_incomplete_window(work, change):  # noqa: F811
    p = work
    kwargs = {}
    if change == "early-intake":
        kwargs["intake_at"] = 86499
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
