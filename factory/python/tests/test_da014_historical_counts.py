"""Historical native counters survive migration without fabricating request rows."""
import json

import pytest
from forge_factory.afo import mission_admin
from forge_factory.afo.durable import Refused
from forge_factory.common import sha256_file
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401


def import_history(p, tmp_path, counts):
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"mission_id": "mission-test", "executions": [{
        "server_identity": "fixture-server", "native_run_id": "historical", "kind": "PRODUCT",
        "reserved_tokens": 1000, "evidence_refs": ["fixture:sealed-history"], "historical_counts": counts}]}))
    return mission_admin.import_snapshot(p.store, "mission-test", path, sha256_file(path))


def test_imported_counters_are_idempotent_and_deduplicate_later_observations(protocol, tmp_path):  # noqa: F811
    p = protocol
    counts = {"requests": 3, "tools": 4, "corrections": 1}
    for _ in range(2):
        import_history(p, tmp_path, counts)
    snap = p.ledger.snapshot("mission-test")
    assert (snap["requests"], snap["tools"], snap["corrections"]) == (3, 4, 1)
    assert snap["usage_unknown"]
    job = "fixture-server:historical"
    p.ledger.count("mission-test", job, "TOOL", "observed-historical-tool")
    # New corrections cannot hide inside a fully spent historical aggregate.
    with pytest.raises(Refused, match="MISSION_MAX_CORRECTIONS_EXHAUSTED"):
        p.ledger.count("mission-test", job, "CORRECTION", "new-correction")
    p.ledger.acquire_inference(job, "mission-test")
    p.ledger.reserve_request("mission-test", job, "observed-request", body_sha256="a" * 64,
                             input_tokens=10, output_cap=10, authorize=lambda: True)
    snap = p.ledger.snapshot("mission-test")
    assert (snap["requests"], snap["tools"], snap["corrections"]) == (3, 4, 1)
    with pytest.raises(Refused, match="HISTORY_COUNTERS_REBOUND"):
        p.ledger.execution("mission-test", job, "PRODUCT", reserved_tokens=1000, imported=True,
                           evidence_refs=["fixture:sealed-history"], historical_counts={**counts, "requests": 0})


def test_historical_request_reservation_prevents_new_admission_after_exhaustion(protocol, tmp_path):  # noqa: F811
    p = protocol
    import_history(p, tmp_path, {"requests": 8, "tools": 0, "corrections": 0})
    p.ledger.acquire_inference(p.ctx.job_id, "mission-test")
    with pytest.raises(Refused, match="MISSION_REQUESTS_EXHAUSTED"):
        p.ledger.reserve_request("mission-test", p.ctx.job_id, "new", body_sha256="a" * 64,
                                 input_tokens=10, output_cap=10, authorize=lambda: True)


@pytest.mark.parametrize("counts,imported,refs", [
    ({"requests": -1, "tools": 0, "corrections": 0}, True, ["fixture:source"]),
    ({"requests": True, "tools": 0, "corrections": 0}, True, ["fixture:source"]),
    ({"requests": 1, "tools": 0, "corrections": 0}, False, ["fixture:source"]),
    ({"requests": 1, "tools": 0, "corrections": 0}, True, []),
])
def test_historical_counters_require_bound_imported_facts(protocol, counts, imported, refs):  # noqa: F811
    with pytest.raises(Refused, match="HISTORY_COUNTERS_INVALID"):
        protocol.ledger.execution("mission-test", "historical", "PRODUCT", reserved_tokens=1000,
                                  imported=imported, evidence_refs=refs, historical_counts=counts)
