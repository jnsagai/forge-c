"""RPR-020 (r84): LL functions with a parameter list (volatile uint32_t *rcc) were not instantiated by the
measurement unit, so size/stack stayed 0 and the stack requirement was unverifiable (DEF-005)."""
import sys

SIG = "measurement unit skips LL functions with parameters"
H = ("static inline void LL_RCC_HSI_Enable(volatile uint32_t *rcc)\n{\n    rcc[0U] |= 8U;\n}\n")


def main() -> int:
    from forge_factory import layer

    unit = layer.ll_measure_unit(H) if hasattr(layer, "ll_measure_unit") else None
    if not unit or "LL_RCC_HSI_Enable(rcc)" not in unit:
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
