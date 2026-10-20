"""RPR-066 (b008): ST's header-only delivery passed SWE.1-SWE.6, but the package stayed BLOCKED on
missing_required_pattern:software/src/*.c - the C-source view of the release policy had nothing to show."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "header-only delivery leaves the package C-source view empty"
HDR = "#include <stdint.h>\nstatic inline uint32_t LL_X_Get(uint32_t v)\n{\n    return v + 1U;\n}\n"


def main() -> int:
    from forge_factory.release import finalize as F

    with tempfile.TemporaryDirectory() as d:
        ws, stage = Path(d) / "ws", Path(d) / "stage"
        (ws / "software/ll").mkdir(parents=True)
        (ws / ".forge-run/delivery").mkdir(parents=True)
        (ws / "software/ll/ll_x.h").write_text(HDR)
        (ws / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [{"name": "LL_X_Get"}]}))
        (ws / ".forge-run/manifest.json").write_text(json.dumps({
            "layer": "LL", "code_mode": "FROZEN", "delivered": [{"path": "software/ll/ll_x.h", "role": "delivered_code"}],
            "delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis"}}}))
        stage.mkdir()
        if hasattr(F, "stage_delivered_unit"):
            F.stage_delivered_unit(ws, stage)
        staged = sorted(p.name for p in (stage / "software/src").glob("*.c")) if (stage / "software/src").is_dir() else []
    if not staged:
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
