"""The generic SWE.2 register-access clause must match a HAL's provided CMSIS LL.

CRC/WWDG frozen architectures invented a linker register array and their SWE.5 host tests could not link.
The real builder reproduces that mandate for a provided HAL. A hash-pinned greenfield graph is the control.
No network/GPU/model call or production workspace is used.
"""
import hashlib
import re
import sys

SIG = "the provided CMSIS HAL architecture prompt mandates a fabricated register-block array"
GREEN_SHA = "c39528d3ce72965d96c70928d980575bf332d1d71eba3e5e274cfe0848150c5a"


def graph(api=None):
    from forge_factory.workflow import builder

    dot, _ = builder.build("WO-RPR143", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral="crc",
                           uspec_gtest=True, **({"provided_api": api} if api else {}))
    return dot.replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")


def prompt(dot, name):
    return dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', dot)).get(name, "")


def main():
    green = graph()
    if hashlib.sha256(green.encode()).hexdigest() != GREEN_SHA:
        print("REPRODUCER_ERROR:CONTROL_CHANGED:greenfield HAL graph is not byte-identical")
        return 2
    clause = "extern volatile uint32_t register-block array placed at the CRC base by the linker"
    if clause not in prompt(green, "swe2_author"):
        print("REPRODUCER_ERROR:CONTROL_CHANGED:greenfield architecture lost its register array")
        return 2
    api = {"instance": "CRC", "functions": ["LL_CRC_ReadData32"],
           "calls": {"LL_CRC_ReadData32": "LL_CRC_ReadData32(CRC)"},
           "signatures": {"LL_CRC_ReadData32": "uint32_t LL_CRC_ReadData32(const CRC_TypeDef *CRCx)"}}
    architecture = prompt(graph(api), "swe2_author")
    if "PROVIDED LL" not in architecture:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:provided HAL architecture not built")
        return 2
    if clause in architecture:
        print("SYMPTOM_PRESENT:" + SIG)
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        raise SystemExit(2)
