"""Black-box typed pre-native cause loss; unchanged CRE output contract."""
from forge_factory.afo.local_agent import LaunchNotStarted
from forge_factory.afo.durable import Refused

try:
    e = LaunchNotStarted(dict(job_id="CONTROL", nonce="CONTROL"), Refused("GUARD_FAIL", "PRIVATE_CONTROL"))
    assert e.job_id == e.nonce == "CONTROL"
    failure_type = e.failure_type
except Exception:
    print("ERROR:CONSTRUCTOR_OR_PROOF_CONTRACT_CHANGED")
    raise SystemExit(2)
if failure_type == "Refused":
    print("SYMPTOM_PRESENT:typed pre-native refusal cause erased as generic Refused")
    raise SystemExit(1)
if failure_type == "GUARD_FAIL":
    print("SYMPTOM_ABSENT")
    raise SystemExit(0)
print("ERROR:UNRECOGNIZED_CAUSE_TYPE")
raise SystemExit(2)
