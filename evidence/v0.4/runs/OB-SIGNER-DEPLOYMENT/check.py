"""Read-only verification of the namespace fix as deployed, including the actual owner signatures."""
import subprocess
from pathlib import Path

from forge_factory.onboarding import onboarding_dir
from forge_factory.onboarding.approval import verify

properties = subprocess.check_output(
    ["systemctl", "--user", "show", "forge-conductor", "-p", "ActiveState", "-p", "WorkingDirectory", "-p", "MainPID"],
    text=True,
)
service = dict(line.split("=", 1) for line in properties.splitlines() if "=" in line)
assert service["ActiveState"] == "active"
runtime = Path(service["WorkingDirectory"])
assert subprocess.check_output(["git", "-C", str(runtime), "rev-parse", "HEAD"], text=True).strip() == \
    "9fa4664798183218184a6cf1a650ab1985087ea4"
assert Path(f"/proc/{service['MainPID']}/cwd").resolve() == runtime
cloud = subprocess.check_output(
    ["systemctl", "--user", "show", "forge-llm-gateway-cloud", "-p", "ActiveState", "-p", "UnitFileState"], text=True,
)
assert dict(line.split("=", 1) for line in cloud.splitlines() if "=" in line) == \
    {"ActiveState": "inactive", "UnitFileState": "disabled"}
for key in ("0010e-st-cube-gpio-hal-ob", "0011e-st-cube-spi-hal-ob", "0012e-st-cube-usart-hal-ob",
            "0013e-st-cube-tim-hal-ob"):
    result = verify(onboarding_dir(key), runtime / "config/factory/afo-allowed-signers")
    assert result["code"] == "APPROVAL_OK", result
    print(key, result["code"], result["approval"]["approval_id"])
print("PASS deployed revision 9fa4664; owner signatures accepted; cloud gateway disabled")
