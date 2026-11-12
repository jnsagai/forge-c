"""DA-AT-055 protocol check (deterministic, no model): the registered calibration runs of the stepwise inspector are
complete and honest. It checks the published records only; it never judges the measured rates.

usage (repository root): python3 evidence/014-durable-local-autonomy/stepwise-inspector-20261026/verify_calibration.py

Checks, per DA-FR-055:
1. the 9-baseline subset (calibration-subset.json) was measured in 3 complete runs (calibration-runs.json);
2. the refreshed held-out test set 2 (f015-split.json, seed 20261026, Feature 015 drivers) was registered in a commit
   before its first run started, and its file hash is the one the run script pins;
3. every learning set passed at the deployed revision before test set 2 was measured (learning-round-<rev>.json);
4. every test-set-2 run deployed that same revision, verified the test trees UNCHANGED, recorded the unit tests
   (remote skip count and the loop10 record) and the truthful preflight before inference, and exited 0;
5. every run has one row per registered work order and case, and its summary equals the counts of its rows
   (misses, false alarms and empty inspections reported per run).
"""
import collections
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPLIT_SHA = "71987543d98664eea28269170125a84315f9563e66df8c919641aa7b9cafe22e"
CASES = ["BASELINE", "S1-OMIT", "S1-QM", "S1-EFFECT", "S1-NOSTART", "S1-GAPROW", "S1-NOBUDGET"]
ON, GATE = "inspection (on target)", "deterministic gate"
errors = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        errors.append(msg)


def load(name):
    return json.loads((HERE / name).read_text())


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def counts(rows):
    seeded = [r for r in rows if r["case"] != "BASELINE"]
    base = [r for r in rows if r["case"] == "BASELINE"]
    return {"seeded": len(seeded), "semantic_detection_on_target": sum(r["detected_by"] == ON for r in seeded),
            "deterministic_detection": sum(r["detected_by"] == GATE for r in seeded),
            "inspection_fail_off_target": sum(r["detected_by"] == "inspection (off target)" for r in seeded),
            "missed": sum(r["detected_by"] == "MISSED" for r in seeded),
            "false_rejections": sum(r["detected_by"].startswith("FALSE_REJECTION") for r in base),
            "baselines": len(base),
            "no_inspection": sum(r["detected_by"].startswith("NO_INSPECTION") for r in rows)}


def complete(run, holdouts, label):
    keys = collections.Counter((r["holdout"], r["case"]) for r in run["rows"])
    want = {(h, c) for h in holdouts for c in CASES}
    check(set(keys) == want and all(v == 1 for v in keys.values()),
          f"{label} {run['run']}: one row per registered work order and case ({len(run['rows'])}/{len(want)})")
    check(counts(run["rows"]) == run["summary"], f"{label} {run['run']}: summary equals the counts of its rows")
    check(any(l.startswith("exit=0 ") for l in run["log_lines"]), f"{label} {run['run']}: exited 0")


# 1. the registered subset
subset = [x["workorder"] for x in load("calibration-subset.json")["subset"]]
s3 = load("calibration-runs.json")["runs"]
check(len(s3) == 3, f"subset: 3 registered runs ({len(s3)})")
for r in s3:
    complete(r, subset, "subset")

# 2. registration of test set 2 before measurement
split = HERE / "f015-split.json"
check(hashlib.sha256(split.read_bytes()).hexdigest() == SPLIT_SHA, "test set 2: split file hash is the pinned one")
rel = str(split.relative_to(ROOT))
first = subprocess.run(["git", "log", "--diff-filter=A", "--format=%H %cI", "--", rel], cwd=ROOT, text=True,
                       capture_output=True).stdout.split()
t2 = load("calibration-t2-runs.json")["runs"]
starts = [ts(next(l for l in r["log_lines"] if l.startswith("start ")).split()[1]) for r in t2]
check(bool(first) and datetime.fromisoformat(first[1]) < min(starts),
      f"test set 2: registered in {first[0][:7] if first else '?'} before the first run started")
test = [x["workorder"] for x in json.loads(split.read_text())["test_set_2"]]
learn3 = [x["workorder"] for x in json.loads(split.read_text())["learning_set_3"]]
check(not set(test) & set(learn3) and len(test) == 2, "test set 2: disjoint from learning set 3")

# 3. learning sets passed at the deployed revision
revs = {next(l for l in r["log_lines"] if l.startswith("start ")).split()[2] for r in t2}
check(len(revs) == 1, f"test set 2: all runs deployed one revision {sorted(revs)}")
rev = sorted(revs)[0]
lr = load(f"learning-round-{rev[:7]}.json")["runs"]
for r in lr:
    head = next(l for l in r["log_lines"] if l.startswith("start ")).split()
    s = r["summary"]
    check(head[2] == rev and all(s[k] == 0 for k in ("missed", "inspection_fail_off_target", "false_rejections",
                                                       "no_inspection")),
          f"learning {r['run']}: perfect at {rev[:7]} ({s['seeded']} seeded, {s['baselines']} baselines)")
    check(ts(next(l for l in r["log_lines"] if l.startswith("exit=")).split()[1]) <= min(starts),
          f"learning {r['run']}: ended before test set 2 started")
check({r["run"] for r in lr} >= {"learning-19", "learning2-5", "learning3-2"}, "learning sets 1, 2 and 3 all ran")
complete(next(r for r in lr if r["run"] == "learning3-2"), learn3, "learning")

# 4. and 5. the test-set-2 runs
check(len(t2) == 3, f"test set 2: 3 registered runs ({len(t2)})")
unit = (HERE / f"unit-local-{rev}.txt").read_text().splitlines()
check(f"rev={rev}" in unit[0] and "skipped=0" in unit[0] and "passed" in unit[-1] and "failed" not in unit[-1],
      f"loop10 unit record for {rev[:7]}: {unit[-1]}")
for r in t2:
    lines = r["log_lines"]
    check(any('"status": "UNCHANGED"' in l and '"test_set_2_status": "UNCHANGED"' in l for l in lines),
          f"test set 2 {r['run']}: integrity verified UNCHANGED before inference")
    check(any(l.startswith("unit tests (remote):") and "skipped=" in l and "local:" in l for l in lines),
          f"test set 2 {r['run']}: unit tests recorded with the skip count")
    check(r["preflight"] is not None and r["preflight"]["model_calls"] == 0 and
          any(l.startswith("preflight (recorded):") for l in lines),
          f"test set 2 {r['run']}: truthful preflight recorded ({r['preflight']['status']})")
    check(r["inspector_options"]["sampling"] == {"seed": 1, "temperature": 0} and r["inspector_options"]["stepwise"],
          f"test set 2 {r['run']}: stepwise, temperature 0, seed 1")
    complete(r, test, "test set 2")

print("RESULT", "PASS" if not errors else f"FAIL ({len(errors)})")
sys.exit(1 if errors else 0)
