"""Persistent transient failure + a restart before every call: admitted retries must equal the policy budget."""
import json
import os
import sys
from pathlib import Path

os.environ["FORGE_EVENTS_DIR"] = str(Path(sys.argv[1]) / "ev")
from forge_factory.reliability import recovery as R  # noqa: E402
from forge_factory.reliability.policy import load  # noqa: E402
from forge_factory.reliability.store import CREStore  # noqa: E402

db, pol, admitted, last = Path(sys.argv[1]) / "cre.sqlite3", load(), 0, ""
for i in range(6):
    d = R.RetryAdmission(CREStore(db), pol).admit("bench|op", failure_class="TRANSIENT_DEPENDENCY",
                                                  replay_class="REPLAY_WITH_IDEMPOTENCY_KEY", now=1000.0 + 1000 * i)
    admitted += d.allowed
    last = d.reason
print(json.dumps({"observed": {"admitted": admitted, "budget": pol.get("recovery.max_transient_retries_per_operation"),
                               "final_reason": last.split(":")[0]}}))
