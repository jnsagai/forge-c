"""CPU staged-reproducer fixture for the review/CRE/prevention integration test."""
import json

from forge_factory.common import REPO_ROOT
from forge_factory.offline.disposition import heldout_workorders

SIG = "review intake rejects explicitly registered post-calibration learning baselines as held out"


def main():
    folder = REPO_ROOT / "evidence/014-durable-local-autonomy/stepwise-inspector-20261026"
    spent = {r["workorder"] for r in json.loads((folder / "learning-set-2.json").read_text())["learning_set_2"]}
    frozen = {r["workorder"] for r in json.loads(
        (REPO_ROOT / "evidence/v0.4/runs/F011-T046/testset.json").read_text())["selected"]} - spent
    active = heldout_workorders()
    if spent & active:
        print("SYMPTOM_PRESENT:" + SIG)
        return 1
    assert frozen <= active
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
