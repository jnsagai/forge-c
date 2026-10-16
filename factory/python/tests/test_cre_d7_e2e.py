"""CRE-T040 (AT-037): a real local-model RCC work order on the real Fabro server reached a terminal deterministic
package whose archive re-verifies and that CRE observed. Reads the live installation (no mocks)."""
import pytest
from forge_factory.reliability import e2e


def test_latest_local_qwen_work_order_has_real_terminal_evidence():
    wss = e2e.latest_local_attempts(1)
    if not wss:
        pytest.fail("BLOCKED: no local-model work order with a package on this host (real E2E not demonstrated)")
    r = e2e.assess(wss[0])
    assert r["model_profile"]["local_only"] is True and r["fabro_server"].startswith("http://127.0.0.1:32290")
    assert r["package_status"] in ("BLOCKED", "READY_FOR_OFFLINE_REVIEW", "READY")
    assert r["archive_verification"] is not None and r["archive_verification"]["issues"] == []
    assert r["cre_observations"] > 0 and r["result"] == "PASS"
