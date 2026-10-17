"""A permanent infrastructure fault must end in REQUIRES_OFFLINE_ATTENTION within the transition bound."""
import json
import os
import sys
from pathlib import Path

os.environ["FORGE_EVENTS_DIR"] = str(Path(sys.argv[1]) / "ev")
from forge_factory.reliability import recovery as R  # noqa: E402
from forge_factory.reliability.policy import load  # noqa: E402
from forge_factory.reliability.store import CREStore  # noqa: E402

ctl = R.RecoveryController(CREStore(Path(sys.argv[1]) / "cre.sqlite3"), load())
ctl.open("bench", "INFRASTRUCTURE")
for _ in range(100):
    if ctl.step("bench", "unhealthy")["state"] in R.TERMINAL:
        break
h = ctl.history("bench")
print(json.dumps({"observed": {"final_state": ctl.get("bench")["state"], "transitions": len(h),
                               "within_bound": len(h) <= 3 * (ctl.max_retries + ctl.max_repairs) + 4}}))
