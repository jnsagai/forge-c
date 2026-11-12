"""Bounded full-history replay; fixtures are never operational qualification."""

# ruff: noqa: F811
import json

import pytest
from forge_factory.afo import operational_campaign as R
from forge_factory.afo import operational_collection as C
from forge_factory.afo.durable import Refused, canonical, digest, immutable_json
from test_da014_fault_observer import setup  # noqa: F401
from test_da014_operational_collection import collector  # noqa: F401


def test_partial_results_never_report_complete_history(collector):
    p = collector
    for _ in range(3):
        p.collector(p.soak_id)
    batches = p.collector.verify_batches()
    for count in range(1, 4):
        row = next(batches)
        assert row["status"] == "SOURCE_REPLAY_PARTIAL" and row["samples"] == count
        assert row["unexpected_interventions"] is None
        assert "observation_refs" not in row and "history_sha256" not in row
    final = next(batches)
    assert final["status"] == "SOURCE_REPLAY_PASS" and final["samples"] == 3
    assert final["history_sha256"] == digest(p.collector.history())
    with pytest.raises(StopIteration):
        next(batches)


def test_collection_can_append_during_verification_of_fixed_prefix(collector):
    p = collector
    p.collector(p.soak_id)
    original = p.collector.history()
    batches = p.collector.verify_batches()
    assert next(batches)["status"] == "SOURCE_REPLAY_PARTIAL"
    p.collector(p.soak_id)  # No writer lock is retained by the suspended verifier.
    result = next(batches)
    assert result["status"] == "SOURCE_REPLAY_PASS" and result["samples"] == 1
    assert result["history_sha256"] == digest(original)
    assert p.collector.verify()["samples"] == 2


@pytest.mark.parametrize("change", ["truncate", "rewrite", "partial-tail"])
def test_log_change_before_completion_refuses(collector, change):
    p = collector
    p.collector(p.soak_id)
    batches = p.collector.verify_batches()
    next(batches)
    path = p.collector.log
    lines = path.read_bytes().splitlines()
    if change == "truncate":
        lines = lines[:1]
    elif change == "rewrite":
        head = json.loads(lines[0])
        head["authorization_ref"] = "tampered-fixture-reference"
        lines[0] = canonical(head)
    path.write_bytes(b"\n".join(lines) + b"\n" + (b"{" if change == "partial-tail" else b""))
    with pytest.raises(Refused):
        next(batches)


@pytest.mark.parametrize("name", ["receipt.json", "observation-attempt.json", "observation.json"])
def test_new_invocation_rechecks_earlier_sources_after_partial_replay(collector, name):
    p = collector
    for _ in range(2):
        p.collector(p.soak_id)
    batches = p.collector.verify_batches()
    assert next(batches)["samples"] == 1
    batches.close()
    path = p.collector.directory(0) / name
    path.chmod(0o600)
    raw = json.loads(path.read_bytes())
    raw["synthetic_tamper"] = True
    path.write_bytes(canonical(raw))
    with pytest.raises(Refused):
        C.Collector(p.manifest, p.soak_id, p.ref).verify()


def test_future_capture_corruption_prevents_final_verdict(collector):
    p = collector
    for _ in range(2):
        p.collector(p.soak_id)
    batches = p.collector.verify_batches()
    next(batches)
    path = p.collector.directory(1) / "observation.json"
    path.chmod(0o600)
    path.write_bytes(b"{}")
    with pytest.raises(Refused):
        list(batches)


def test_one_oversized_source_still_refuses(collector):
    p = collector
    p.collector(p.soak_id)
    path = p.collector.directory(0) / "observation.json"
    path.chmod(0o600)
    with path.open("wb") as out:
        out.truncate(C.O.MAX_BYTES + 1)
    with pytest.raises(Refused, match="NOT_BOUNDED_REGULAR_FILE"):
        p.collector.verify()


def test_no_samples_requires_final_prefix_check(collector):
    result = list(collector.collector.verify_batches())
    assert len(result) == 1 and result[0]["samples"] == 0
    assert result[0]["observation_refs"] == []
    assert result[0]["source_bytes"] == 0


def test_campaign_report_refuses_different_replay_window(collector, monkeypatch):
    p = collector
    p.collector(p.soak_id)
    verify = C.Collector.verify

    def append_then_verify(self):
        self(self.soak_id)
        return verify(self)

    monkeypatch.setattr(C.Collector, "verify", append_then_verify)
    with pytest.raises(Refused, match="REPORT_HISTORY_CHANGED"):
        R.report(p.manifest, p.soak_id, observer_plan_ref=p.ref)


@pytest.mark.parametrize("invalid", [None, {}, {"path": "other", "sha256": "f" * 64},
                                     {"path": "receipt.json", "sha256": True}])
def test_missing_or_invalid_frozen_receipt_reference_refuses(collector, invalid):
    p = collector
    p.collector(p.soak_id)
    if invalid is None:
        ref = {"path": str(p.collector.directory(0) / "receipt.json")}
    else:
        ref = invalid
    with pytest.raises(Refused, match="RECEIPT_UNBOUND"):
        p.collector.replay(0, None, receipt_ref=ref)


def test_truncated_batch_stream_cannot_become_report_success(collector, monkeypatch):
    monkeypatch.setattr(collector.collector, "verify_batches", lambda: iter([
        {"status": "SOURCE_REPLAY_PARTIAL", "samples": 1}]))
    with pytest.raises(Refused, match="REPLAY_INCOMPLETE"):
        collector.collector.verify()


def test_real_sources_exceed_128_mib_without_truncating_history(collector, monkeypatch):
    p = collector
    capture = C.O.capture

    def large_fixture(manifest, plan_ref, destination):
        row = capture(manifest, plan_ref, destination.with_name("synthetic-base.json"))
        row["synthetic_padding"] = ""
        # Only generated spaces: no prompt, vendor input or customer content.
        row["synthetic_padding"] = " " * (C.O.MAX_BYTES - len(canonical(row)) - 128)
        immutable_json(destination, row)
        return row

    monkeypatch.setattr(C.O, "capture", large_fixture)
    for _ in range(8):
        p.collector(p.soak_id)
    before = p.collector.log.read_bytes()
    batches = list(p.collector.verify_batches())
    assert len(batches) == 9
    assert all(b["batch_source_bytes"] <= C.O.MAX_TRACE_BYTES for b in batches[:-1])
    final = batches[-1]
    assert final["status"] == "SOURCE_REPLAY_PASS" and final["samples"] == 8
    assert final["source_bytes"] > 128 * 1024 * 1024
    assert len(final["observation_refs"]) == 8
    assert p.collector.log.read_bytes() == before
    assert final["unexpected_interventions"] is None
    assert final["host_coverage"] == "SEPARATE_INDEPENDENT_VERIFICATION_REQUIRED"
