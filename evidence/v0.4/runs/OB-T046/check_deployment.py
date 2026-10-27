"""Read-only verification of the F016 conductor deployment and its approved source."""
import json
import subprocess
from pathlib import Path

from forge_factory.common import REPO_ROOT

REVISION = "5fb0a8673944c7e919ceffc78daaf6f3b782d71e"
DECISION = "pd-fcc8a2759b12bdd516ac"


def properties(unit, names):
    result = subprocess.run(
        ["systemctl", "--user", "show", unit, *[f"--property={name}" for name in names]],
        capture_output=True, text=True, check=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


decision_path = REPO_ROOT / f"evidence/cre/decisions/{DECISION}.json"
decision = json.loads(decision_path.read_text())
assert decision["candidate_revision"] == REVISION
assert decision["decision"] == "ELIGIBLE_FOR_OFFLINE_REVIEW"
conductor = properties("forge-conductor", ["ActiveState", "MainPID", "WorkingDirectory", "Environment"])
assert conductor["ActiveState"] == "active", conductor
worktree = Path(conductor["WorkingDirectory"])
revision = subprocess.check_output(["git", "-C", str(worktree), "rev-parse", "HEAD"], text=True).strip()
assert revision == REVISION, revision
assert Path(f"/proc/{conductor['MainPID']}/cwd").resolve() == worktree
assert f"FORGE_REPO_ROOT={worktree}" in conductor["Environment"]
assert f"PYTHONPATH={worktree}/factory/python" in conductor["Environment"]
cloud = properties("forge-llm-gateway-cloud", ["ActiveState", "UnitFileState"])
assert cloud == {"ActiveState": "inactive", "UnitFileState": "disabled"}, cloud
print(f"PASS conductor active at {revision}, cwd and import path match {worktree}")
print(f"PASS CRE {DECISION} frozen before deployment")
print("PASS cloud gateway inactive and disabled")
