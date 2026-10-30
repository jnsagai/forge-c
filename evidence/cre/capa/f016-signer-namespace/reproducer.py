import shlex
from forge_factory.onboarding.approval import ALLOWED_SIGNERS, NAMESPACE
entry = next(shlex.split(line) for line in ALLOWED_SIGNERS.read_text().splitlines() if line.startswith("jnsagai "))
assert entry[2] == "ssh-ed25519"
assert entry[1].startswith("namespaces=")
permitted = set(entry[1].split("=", 1)[1].split(","))
assert "forge-afo-authorization" in permitted
assert not (permitted - {"forge-afo-authorization", NAMESPACE})
if NAMESPACE not in permitted:
    print("SYMPTOM_PRESENT:factory signer policy rejects the onboarding approval namespace")
    raise SystemExit(1)
print("SYMPTOM_ABSENT")
