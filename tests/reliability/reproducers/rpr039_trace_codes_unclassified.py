"""RPR-039 (r120): the trace gate's 'UNIT:SWR_NOT_REFINED:SWR-021 (...)' rejection was classified UNCLASSIFIED, so the
CAPA-031 recurrence in r120 was invisible to evaluate_effectiveness, which moved CAPA-031 to EFFECTIVE."""
import sys

SIG = "trace-gate rejection classified UNCLASSIFIED"
RAW = ("UNIT:SWR_NOT_REFINED:SWR-021 (allocated to SWC_LL but no unit-spec item traces it: add 'Traces: SWR-021' to "
       "the USPEC item(s) of the unit that implements it)")


def main() -> int:
    from forge_factory.reliability.taxonomy import classify

    if classify(RAW).error_code != "UNIT:SWR_NOT_REFINED":
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
