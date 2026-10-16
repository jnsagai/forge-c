"""RPR-016 (gate logs r10-r82): a phase rejected twice with the identical deterministic codes spent its remaining
rework cycle anyway (0 of 14 such phases ever recovered); r82 SWE.3 spent 3 cycles on DEFECT_TEST_CHANGED."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SIG = "identical deterministic rejection does not stop the phase"


def main() -> int:
    ws = Path(tempfile.mkdtemp(prefix="rpr016-"))

    def gate(step, stdin=""):
        return subprocess.run([sys.executable, "-m", "forge_factory.inspection.gate", "--workspace", str(ws),
                               "--phase", "SWE.3", "--step", step], input=stdin.encode(), capture_output=True,
                              env={**os.environ, "FORGE_EVENTS_DIR": str(ws / ".ev")}, timeout=120)
    gate("author", "prose")
    gate("route")
    gate("author", "prose")
    r = gate("route")
    log = (ws / ".forge-run/gates/gate-log.jsonl").read_text() if (ws / ".forge-run/gates/gate-log.jsonl").is_file() else ""
    if r.returncode == 0 or "STUCK" not in log:
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
