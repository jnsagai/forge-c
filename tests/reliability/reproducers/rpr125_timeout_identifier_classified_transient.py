"""RPR-125: real deterministic timeout-path finding routed as a transient transport outage.

No workspace mutation or network. The scenario calls the actual CRE classifier for the CRC HAL finding
recorded in WO-F014-SWE2-CRCHAL-20261103-L26, and a target verification timeout-scenario finding. Controls
require genuine transport timeouts to remain retryable and policy denials to stay fail-closed.
"""
import sys

SIG = "a deterministic timeout-named gate finding is classified as a transient upstream outage"


def main():
    from forge_factory.reliability.taxonomy import classify

    for raw in ("MCP request timed out after 30 s", "CALL_FAILED:ReadTimeout", "TimeoutError: provider response"):
        result = classify(raw)
        if (result.failure_class, result.error_code, result.route) != (
                "TRANSIENT_DEPENDENCY", "TRANSIENT_UPSTREAM", "RETRY_BOUNDED"):
            print("REPRODUCER_ERROR:CONTROL_CHANGED:real transport timeout no longer retries")
            return 2
    if classify("WRITE_SCOPE_DENIED: request timeout").failure_class != "POLICY_SECURITY":
        print("REPRODUCER_ERROR:CONTROL_CHANGED:policy denial lost precedence")
        return 2
    findings = ("VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH", "VT:TIMEOUT_SCENARIO_UNOBSERVED:SWR-007")
    hits = [raw for raw in findings if classify(raw).failure_class == "TRANSIENT_DEPENDENCY"]
    if hits:
        print("observed: " + ", ".join(hits))
        print("SYMPTOM_PRESENT:" + SIG)
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("REPRODUCER_ERROR:" + type(exc).__name__ + ":" + str(exc)[:160])
        sys.exit(2)
