"""Feature 015 (F015-T080): AFO launches the production line (Codex authors, Claude inspectors) and recovers a
delivered-code (FROZEN brownfield) order with a fresh work order, because main refuses --resume-from for delivered code.
The benchmark envelopes pass the AFO intake schema and are scoped by the owner's authorization."""
import json

import pytest
from forge_factory.afo import contracts, runtime
from forge_factory.benchmark import afo_orders
from forge_factory.benchmark import queue as Q


@pytest.fixture()
def calls(monkeypatch):
    seen = []

    def run(example, wo, **kw):
        seen.append({"example": example.name, "wo": wo, **kw})
        return {"fabro_run_id": "R1"}
    monkeypatch.setattr("forge_factory.workorder.run", run)
    return seen


def test_the_codex_claude_profile_launches_codex_authors_and_claude_inspectors(calls):
    r = runtime.launcher({"example": "examples/0014c-st-cube-crc", "model_profile": "codex-claude"}, "WO-AFO-x-a1", {})
    assert r["fabro_run_id"] == "R1" and set(runtime.PROFILES) == {"codex-claude"}
    c = calls[0]
    assert (c["acp_authors"], c["acp_inspectors"], c["resume"]) == ("codex", "claude", None)
    with pytest.raises(ValueError, match="MODEL_PROFILE_UNKNOWN"):
        runtime.launcher({"example": "examples/0014c-st-cube-crc", "model_profile": "deepseek-flash"}, "WO-x", {})


def test_a_delivered_code_recovery_attempt_is_a_fresh_work_order(calls):
    runtime.launcher({"example": "examples/0014c-st-cube-crc", "model_profile": "codex-claude",
                      "resume_from": "WO-AFO-x-a1", "resume_upto": "SWE.4"}, "WO-AFO-x-a2", {"afo_attempt": "A2"})
    runtime.launcher({"example": "examples/0002b-arm_55_rcc_hal", "model_profile": "codex-claude",
                      "resume_from": "WO-AFO-y-a1", "resume_upto": "SWE.3"}, "WO-AFO-y-a2", {})
    bf, green = calls
    assert bf["resume"] is None and bf["resume_upto"] is None and bf["labels"]["afo_brownfield_fresh_attempt"] == "1"
    assert green["resume"] == "WO-AFO-y-a1" and green["resume_upto"] == "SWE.3"  # greenfield resume unchanged


def test_benchmark_envelopes_pass_the_intake_schema_and_the_authorization_scope():
    envs = afo_orders.envelopes(Q.load(), "jnsagai", "AUTH-AFO-PILOT-20261025")
    assert envs and envs[0]["request_id"] == "BENCH-CRC-ST"
    rec = json.loads((afo_orders.REPO_ROOT / "config/factory/afo-authorizations/AUTH-AFO-PILOT-20261025.json")
                     .read_text())
    for e in envs:
        assert contracts.errors("work-order", e) == []
        if e["request_id"].endswith("-HAL"):  # F015-T065: ST HAL items are their own driver classes (a separate scope)
            assert e["driver_class"] == f"STM32N6_{e['request_id'].split('-')[1]}_HAL_ST"
        else:
            assert e["driver_class"] in rec["scope"]["driver_classes"]
        assert e["model_profile"] in rec["scope"]["models"]
        m = json.loads((afo_orders.REPO_ROOT / e["input_manifest_ref"]).read_text())
        assert m["model_profile"] == "codex-claude" and (afo_orders.REPO_ROOT / m["example"] / "workorder.json").is_file()


def test_an_all_acp_profile_is_admitted_without_the_deepseek_gateway():
    """Owner 2026-10-25: "a codex - claude based AFO, without deepseek". The codex-claude profile routes no agent node
    through a model gateway, so admission does not probe the cloud (DeepSeek) gateway; a profile this module does not
    define keeps the gateway check."""
    from forge_factory.afo import scheduler

    class Eff:
        def get(self, k, d=None):
            return {"engineering.allowed_model_profiles": ["codex-claude", "other"],
                    "budgets.max_order_attempts": 3}.get(k, d)

    class Store:
        def attempts(self, oid):
            return []

    probed = []
    probes = {"mount": lambda: True, "fabro": lambda: True, "mcp": lambda: True,
              "gateway": lambda: probed.append(1) or False}
    order = {"order_id": "afo-x", "envelope": json.dumps({"model_profile": "codex-claude"})}
    assert scheduler.preflight(order, Eff(), Store(), probes) == [] and probed == []
    assert runtime.model_gateway("codex-claude") is None and runtime.model_gateway("other") == runtime.CLOUD_GATEWAY
    other = {"order_id": "afo-y", "envelope": json.dumps({"model_profile": "other"})}
    assert scheduler.preflight(other, Eff(), Store(), probes) == ["MODEL_GATEWAY_UNAVAILABLE"] and probed == [1]
