"""RPR-177 (owner lane, Omniverse2, 2026-11-06/07, L90 SWE.6 CRC HAL attempts): the Ornith think-AFO profile's author
route was measured by utf8_byte_upper_bound, which counts every byte as a token. Requests of 115-123 k bytes were
refused as CAPABILITY_LIMIT although their real size was far below the 262,144-token context; the recovery planner's
eight jobs were refused the same way.

Scenario: the pinned profile local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104 as committed.
Symptom: its gateway measurement policy has no native route for the Ornith author model."""
import sys

SIG = "the pinned think-AFO profile measures the Ornith author by byte count instead of native tokens"
PROFILE = "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"
MODEL = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"


def main() -> int:
    from forge_factory.lrtx import request_measurement as M
    from forge_factory.lrtx.profile import load

    prof = load(PROFILE)
    if MODEL not in (prof.get("models") or {}).get("allowed", {}):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:model not allowed by profile")
        return 2
    if M.policy(prof).get(MODEL) != M.METHOD:
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
