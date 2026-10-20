"""RPR-060 (b006): the target build of a CMSIS delivery failed because the fixed build profile compiles with -Werror and
-Wsign-conversion and the vendor's own CMSIS cache header warns; no object, no flash/RAM measurement (DEF-001)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "delivered CMSIS code fails the target build on vendor-header warnings"
VENDOR = "#include <stdint.h>\nstatic inline uint32_t vendor_conv(int32_t v) { return v; }\n"
DELIVERED = '#include "vendor_dev.h"\nstatic inline uint32_t LL_X_Get(void) { return vendor_conv(-1); }\n'


def main() -> int:
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import build as B

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / ".forge-run/delivery").mkdir(parents=True)
        (ws / "inputs/vendor/include").mkdir(parents=True)
        (ws / "software/ll").mkdir(parents=True)
        (ws / "inputs/vendor/include/vendor_dev.h").write_text(VENDOR)
        (ws / "software/ll/ll_x.h").write_text(DELIVERED)
        (ws / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [{"name": "LL_X_Get"}]}))
        (ws / ".forge-run/manifest.json").write_text(json.dumps({
            "layer": "LL", "code_mode": "FROZEN", "delivered": [{"path": "software/ll/ll_x.h", "role": "delivered_code"}],
            "delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis", "defines": [], "secure": False}}}))
        ctx = sdk.ToolContext("forge-build-mcp", "compile", "swe3-author", "SWE.3", ws, "r")
        r = B.compile_(ctx, B.CompileIn(profile="target-cm55-gcc"))
    if r["status"] != "PASS":
        print(f"compile: {r['status']} {r['issues'][:2]}")
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
