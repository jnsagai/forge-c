"""Probe the shipped signer permissions using a disposable key, never the owner's key."""
import subprocess
import tempfile
from pathlib import Path

from forge_factory.onboarding import approval

SIGNATURE = "factory signer policy rejects the onboarding approval namespace"


def probe():
    entry = next(line for line in approval.ALLOWED_SIGNERS.read_text().splitlines()
                 if line.startswith("jnsagai "))
    permissions = entry.split(" ssh-ed25519 ", 1)[0]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        key = root / "throwaway"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        allowed = root / "allowed"
        allowed.write_text(permissions + " " + key.with_suffix(".pub").read_text())
        results = {}
        for namespace in (approval.NAMESPACE, "forge-afo-authorization", "forge-unrelated"):
            message = root / namespace
            message.write_text("disposable signer namespace regression fixture\n")
            subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", namespace, str(message)],
                           check=True, capture_output=True)
            result = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I", "jnsagai", "-n",
                                     namespace, "-s", str(message) + ".sig"], input=message.read_bytes(),
                                    capture_output=True)
            results[namespace] = result.returncode == 0
    return results


if __name__ == "__main__":
    result = probe()
    if not result["forge-afo-authorization"] or result["forge-unrelated"]:
        raise SystemExit("REPRODUCER_ERROR:unrelated signer permission regression")
    if not result[approval.NAMESPACE]:
        print("SYMPTOM_PRESENT:" + SIGNATURE)
        raise SystemExit(1)
    print("SYMPTOM_ABSENT")
