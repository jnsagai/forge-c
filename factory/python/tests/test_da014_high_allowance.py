"""Owner-approved bring-up quotas remain finite, cumulative and separate from historical missions."""
import copy
import time

import pytest
from forge_factory.afo import policy
from forge_factory.afo.durable import Refused
from forge_factory.afo.mission_ledger import MissionLedger
from test_afo_m4_recovery import order  # noqa: F401


def test_high_quota_allows_multiple_large_attempts_without_resetting_history(order):  # noqa: F811
    store, _, _, _, eff = order
    configured = copy.deepcopy(eff.policy)
    configured["budgets"]["max_model_tokens_per_order"] = 100_000_000_000
    assert not policy.schema_errors(configured) and not policy.floor_violations(configured)
    ledger = MissionLedger(store)
    old = dict(max_attempts=3, max_jobs=4, max_requests=40, max_tokens=2_000_000,
               max_tools=256, max_corrections=1, deadline=time.time() + 600)
    ledger.register("old-crc", "old:crc", old, "AUTH-historical-fixture", authorize=lambda *a: True)
    ledger.execution("old-crc", "old-native", "PRODUCT", reserved_tokens=1_900_000)
    history = ledger.snapshot("old-crc")
    generous = dict(old, max_attempts=1000, max_jobs=1000, max_requests=100_000,
                    max_tokens=100_000_000_000, max_tools=1_000_000)
    ledger.register("m1-high", "new:idr", generous, "AUTH-current-fixture", authorize=lambda *a: True)
    for i in range(3):
        ledger.execution("m1-high", f"new-native-{i}", "PRODUCT", reserved_tokens=100_000_000)
    snapshot = ledger.snapshot("m1-high")
    assert snapshot["attempts"] == 3 and snapshot["charged_tokens"] == 300_000_000 and snapshot["usage_unknown"]
    assert ledger.snapshot("old-crc") == history  # No refund, reinterpretation or new limits for history.
    with pytest.raises(Refused, match="MISSION_ALLOWANCE_RESET_FORBIDDEN"):
        ledger.register("old-crc", "old:crc", generous, "AUTH-current-fixture", authorize=lambda *a: True)
    configured["budgets"]["max_model_tokens_per_order"] += 1
    assert policy.schema_errors(configured)  # Large finite ceiling, not an unbounded bypass.
