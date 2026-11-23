#!/usr/bin/env python3
"""Scripted stand-in for a coding-agent harness, used by the conductor tests (T028).

Usage: fake_harness.py author|inspector   (prompt on stdin, scenario JSON path in $FAKE_SCENARIO)

Scenario keys:
  author.items            items written on phase "create"
  author.rework           {item_id: {field: value}} applied on phase "rework" of that item
  author.rework_also      {item_id: {field: value}} applied to OTHER items during a rework (must be discarded)
  author.split            {item_id: [new items]} appended on rework of item_id
  author.rework_touch     true: every rework also writes "rework round N" into the item's rationale (a real change)
  author.fix_gates        [{id, field: value}] applied on phase "fix-gates"
  author.fix_open_points  open points written on phase "fix-gates" (replacing the list)
  author.set_fix          {item_id: {field: value}} applied on phase "rework-set"
  author.update           {"patch": {item_id: {field: value}}, "open_points": [...]} applied on phase "update"
  author.skip_create_once the first "create" call writes nothing (an author that forgets the work product)
  author.write_outside    a relative path the author writes on "create" (scope violation)
  author.break_json       phases after which the work product is left as invalid JSON (once per phase); "fix-gates"
                          repairs it ("always" in the list: fix-gates never repairs)
  author.governance       governance package written on phase "governance" (default: one use case serving every
                          STK need of the inputs); "fix-governance" applies author.governance_fix (a full package)
  author.no_use_cases     true: "create" does not tag the items with the use cases (realization gap)
  inspector.item_rounds   list per round of {item_id: [finding]}
  inspector.set_rounds    list per round of [finding]
  inspector.coverage_rounds list per set round of coverage rows returned with the set findings
  inspector.write_file    a relative path the inspector tries to write
  inspector.garbage       reply with prose instead of JSON
Every call is appended to $FAKE_LOG as one JSON line: role, phase, round, items, active_role.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def main() -> int:
    role = sys.argv[1]
    prompt = sys.stdin.read()
    task = json.loads(re.search(r"```hi-task\n(.*?)\n```", prompt, re.S).group(1))
    sc = json.loads(Path(os.environ["FAKE_SCENARIO"]).read_text())
    root = Path.cwd()
    active = root / ".hi" / "active-role.json"
    with open(os.environ["FAKE_LOG"], "a") as fh:
        fh.write(json.dumps({
            "role": role, "phase": task["phase"], "round": task.get("round", 0), "items": task.get("items", []),
            "findings": len(task.get("findings", [])), "changed_inputs": task.get("changed_inputs"),
            "suspect": task.get("suspect"), "notice": task.get("notice"),
            "active_role": json.loads(active.read_text()) if active.exists() else None,
            "env_role": os.environ.get("HI_ROLE"),
        }) + "\n")
    wp = root / task["workproduct"]
    if sc.get(role, {}).get("sleep"):
        import time
        time.sleep(sc[role]["sleep"])
    if role == "author":
        a = sc.get("author", {})
        if task["phase"] in ("governance", "fix-governance"):
            if task["phase"] == "governance":
                needs = sorted({m for f in task["inputs"] if (root / f).is_file()
                                for m in re.findall(r"\bSTK-[A-Z0-9_]+-\d{3}\b", (root / f).read_text())})
                gov = a.get("governance") or {
                    "schema": "forge-c-hi/governance@1", "stage": task["stage"],
                    "actors": [{"id": "ACT-SUP-001", "name": "Application", "description": "The supervised tasks."}],
                    "use_cases": [{"id": "UC-SUP-001", "title": "Supervise", "actor": "ACT-SUP-001",
                                   "goal": "Every failure of a supervised task is noticed.", "needs": needs}],
                    "out_of_scope": [], "assumptions": [], "open_points": []}
            else:
                gov = a.get("governance_fix") or json.loads(wp.read_text())
            wp.parent.mkdir(parents=True, exist_ok=True)
            wp.write_text(json.dumps(gov, indent=1))
            print(json.dumps({"role": "author", "stage": task["stage"], "status": "DONE",
                              "outputs": [task["workproduct"]], "issues": [], "open_points": 0}))
            return 0
        marker = root.parent / f"{root.name}-skipped-create"
        if task["phase"] == "create" and a.get("skip_create_once") and not marker.exists():
            marker.write_text("x")
            print(json.dumps({"role": "author", "stage": task["stage"], "status": "DONE", "outputs": [], "issues": [],
                              "open_points": 0}))
            return 0
        if task["phase"] == "create":
            doc = {"schema": "forge-c-hi/requirement-set@1", "stage": task["stage"], "baseline_id": "BL-1",
                   "status": "draft", "provenance": {
                       "role": "author", "skill": task["skill"], "skill_version": "0.1.0", "harness": "fake",
                       "model": None, "model_family": "fake-a", "input_hashes": {}, "created_utc": "2026-11-22T00:00:00Z",
                       "run_id": os.environ.get("HI_RUN_ID", "x")},
                   "items": a["items"], "open_points": a.get("open_points", [])}
            if task.get("governance") and not a.get("no_use_cases"):
                ucs = [u["id"] for u in json.loads((root / task["governance"]).read_text())["use_cases"]]
                doc["items"] = [dict(i, attributes={**i.get("attributes", {}), "use_cases": ucs[:1]})
                                for i in doc["items"]]
            if a.get("write_outside"):
                (root / a["write_outside"]).parent.mkdir(parents=True, exist_ok=True)
                (root / a["write_outside"]).write_text("x\n")
        else:
            good = root.parent / f"{root.name}-good.json"
            try:
                doc = json.loads(wp.read_text())
            except ValueError:
                if task["phase"] != "fix-gates":
                    raise
                if "always" in a.get("break_json", []):  # an author that cannot repair it: leaves the file as it is
                    print(json.dumps({"role": "author", "stage": task["stage"], "status": "DONE", "outputs": [],
                                      "issues": [], "open_points": 0}))
                    return 0
                doc = json.loads(good.read_text())
            by_id = {i["id"]: i for i in doc["items"]}
            if task["phase"] == "rework":
                iid = task["items"][0]
                by_id[iid].update(a.get("rework", {}).get(iid, {}))
                if a.get("rework_touch"):
                    by_id[iid]["rationale"] = f"rework round {task.get('round', 0)}"
                for other, patch in a.get("rework_also", {}).items():
                    if other in by_id and other != iid:
                        by_id[other].update(patch)
                doc["items"] += a.get("split", {}).get(iid, [])
            elif task["phase"] == "fix-gates":
                for fix in a.get("fix_gates", []):
                    by_id[fix["id"]].update({k: v for k, v in fix.items() if k != "id"})
                if "fix_open_points" in a:
                    doc["open_points"] = a["fix_open_points"]
            elif task["phase"] == "update":
                up = a.get("update", {})
                for iid, patch in up.get("patch", {}).items():
                    by_id[iid].update(patch)
                if "open_points" in up:
                    doc["open_points"] = up["open_points"]
            elif task["phase"] == "rework-set":
                for iid, patch in a.get("set_fix", {}).items():
                    by_id[iid].update(patch)
                if a.get("rework_touch"):
                    doc.setdefault("open_points", [])
                    doc["baseline_id"] = f"BL-set-{task.get('round', 0)}"
        wp.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(doc, indent=1)
        broken = root.parent / f"{root.name}-broken.txt"
        done = broken.read_text().split() if broken.exists() else []
        if task["phase"] in a.get("break_json", []) and task["phase"] not in done:
            (root.parent / f"{root.name}-good.json").write_text(text)
            broken.write_text(" ".join(done + [task["phase"]]))
            text = text.replace("},", "}", 1)
        wp.write_text(text)
        print("Done.\n" + json.dumps({"role": "author", "stage": task["stage"], "status": "DONE",
                                      "outputs": [task["workproduct"]], "issues": [], "open_points": 0}))
        return 0
    i = sc.get("inspector", {})
    if i.get("write_file"):
        (root / i["write_file"]).parent.mkdir(parents=True, exist_ok=True)
        (root / i["write_file"]).write_text("inspector was here\n")
    if i.get("garbage"):
        print("I think it looks fine overall.")
        return 0
    rnd = task.get("round", 1)
    if task["phase"] == "item":
        rounds = i.get("item_rounds", [])
        per = rounds[rnd - 1] if rnd - 1 < len(rounds) else {}
        findings = [dict(f, target_id=iid) for iid in task["items"] for f in per.get(iid, [])]
    else:
        rounds = i.get("set_rounds", [])
        findings = rounds[rnd - 1] if rnd - 1 < len(rounds) else []
    reply = {"status": "DONE", "findings": findings}
    cov = i.get("coverage_rounds", [])
    if task["phase"] == "set" and rnd - 1 < len(cov):
        reply["coverage"] = cov[rnd - 1]
    print("```json\n" + json.dumps(reply) + "\n```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
