"""CAPA-125: deterministic TIMEOUT-named gate findings must not become transport failures."""
import pytest
from forge_factory.reliability.taxonomy import classify


@pytest.mark.parametrize("raw", [
    "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH",
    "VT:TIMEOUT_SCENARIO_UNOBSERVED:SWR-007",
    "UNIT:TIMEOUT_RETURN_WRONG",
    "HAL_RCC_TIMEOUT_VALUE",
    "HAL_IWDG_TIMEOUT_MS",
    "BUILD_FAIL:TIMEOUT_CALLBACK_UNDECLARED",
])
def test_product_identifiers_do_not_trigger_transport_recovery(raw):
    result = classify(raw)
    assert result.failure_class != "TRANSIENT_DEPENDENCY"
    assert result.error_code != "TRANSIENT_UPSTREAM"
    assert result.route != "RETRY_BOUNDED"


@pytest.mark.parametrize("raw", [
    "MCP request timed out after 30 s",
    "gateway request timeout",
    "CALL_FAILED:ReadTimeout",
    "httpx.ConnectTimeout",
    "socket.timeout",
    "TimeoutError: provider response not received",
    "PoolTimeout",
    "WriteTimeout",
    "TimeoutException",
    "HTTP 429: rate limit",
    "connection reset by peer",
])
def test_actual_transport_failures_remain_retryable(raw):
    result = classify(raw)
    assert (result.failure_class, result.error_code, result.route) == (
        "TRANSIENT_DEPENDENCY", "TRANSIENT_UPSTREAM", "RETRY_BOUNDED")


def test_security_and_budget_findings_still_take_precedence_over_timeout_text():
    assert classify("WRITE_SCOPE_DENIED: request timeout").failure_class == "POLICY_SECURITY"
    assert classify("TOKEN_BUDGET_EXHAUSTED: request timeout").route == "REQUIRES_OFFLINE_ATTENTION"
