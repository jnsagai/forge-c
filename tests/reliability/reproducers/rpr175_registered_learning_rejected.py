"""Registered spent baselines must reach learning; unspent frozen cases stay isolated.

Read only protected owner registrations and the public membership function. No
model, grant, key, state mutation or inference. Calibration is not qualification.
"""
import json
from pathlib import Path

from forge_factory.common import REPO_ROOT
from forge_factory.offline.disposition import heldout_workorders

SIG = "review intake rejects explicitly registered post-calibration learning baselines as held out"


def main():
    root = REPO_ROOT / "evidence/014-durable-local-autonomy/stepwise-inspector-20261026"
    spent = json.loads((root / "learning-set-2.json").read_text())
    assert spent["schema"] == "forge-c/feature014-learning-set-2/1"
    expected_learning = {r["workorder"] for r in spent["learning_set_2"]}
    assert len(expected_learning) == 9
    frozen = json.loads((REPO_ROOT / "evidence/v0.4/runs/F011-T046/testset.json").read_text())
    expected_frozen = {r["workorder"] for r in frozen["selected"]} - expected_learning
    assert len(expected_frozen) == 13
    actual = heldout_workorders()
    if expected_learning & actual:
        print("SYMPTOM_PRESENT:" + SIG)
        return 1
    assert expected_frozen <= actual, "UNSPENT_FROZEN_CASES_NOT_ISOLATED"
    spent4 = json.loads((root / "learning-set-4.json").read_text())
    assert not {r["workorder"] for r in spent4["learning_set_4"]} & actual
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
