"""RPR-034 (r112, r114): SWE.1 was BLOCKED after three cycles repeating a qualified EARS subject ('The RCC LL driver
compiled for the Cortex-M55 target shall ...'); the major finding was a bare EARS_UNKNOWN_SYSTEM_NAME."""
import sys

SIG = "unknown EARS system name without an actionable major hint"


def main() -> int:
    from forge_factory.inspection.ears import check_document

    md = "- **SWR-020** The RCC LL driver compiled for the Cortex-M55 target shall use no more than 4096 bytes of flash.\n"
    major = check_document(md, {"RCC LL driver", "RCC driver"})["major_findings"]
    ok = any("SYSTEM_NAME_HINT" in x and "RCC LL driver compiled for the Cortex-M55 target" in x for x in major)
    print("SYMPTOM_ABSENT" if ok else f"SYMPTOM_PRESENT:{SIG}")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
