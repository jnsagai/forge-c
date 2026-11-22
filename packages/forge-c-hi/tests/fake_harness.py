#!/usr/bin/env python3
"""Scripted stand-in for a coding-agent harness, used by the conductor tests (T028).

Usage: fake_harness.py author|inspector   (prompt on stdin, scenario JSON path in $FAKE_SCENARIO)

Scenario keys:
  author.items            items written on phase "create"
  author.rework           {item_id: {field: value}} applied on phase "rework" of that item
  author.rework_also      {item_id: {field: value}} applied to OTHER items during a rework (must be discarded)
  author.split            {item_id: [new items]} appended on rework of item_id
  author.fix_gates        [{id, field: value}] applied on phase "fix-gates"
  author.set_fix          {item_id: {field: value}} applied on phase "rework-set"
  author.update           {"patch": {item_id: {field: value}}, "open_points": [...]} applied on phase "update"
  author.write_outside    a relative path the author writes on "create" (scope violation)
  inspector.item_rounds   list per round of {item_id: [finding]}
  inspector.set_rounds    list per round of [finding]
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
            "suspect": task.get("suspect"),
            "active_role": json.loads(active.read_text()) if active.exists() else None,
            "env_role": os.environ.get("HI_ROLE"),
        }) + "\n")
    wp = root / task["workproduct"]
    if role == "author":
        a = sc.get("author", {})
        if task["phase"] == "create":
            doc = {"schema": "forge-c-hi/requirement-set@1", "stage": task["stage"], "baseline_id": "BL-1",
                   "status": "draft", "provenance": {
                       "role": "author", "skill": task["skill"], "skill_version": "0.1.0", "harness": "fake",
                       "model": None, "model_family": "fake-a", "input_hashes": {}, "created_utc": "2026-11-22T00:00:00Z",
                       "run_id": os.environ.get("HI_RUN_ID", "x")},
                   "items": a["items"], "open_points": a.get("open_points", [])}
            if a.get("write_outside"):
                (root / a["write_outside"]).parent.mkdir(parents=True, exist_ok=True)
                (root / a["write_outside"]).write_text("x\n")
        else:
            doc = json.loads(wp.read_text())
            by_id = {i["id"]: i for i in doc["items"]}
            if task["phase"] == "rework":
                iid = task["items"][0]
                by_id[iid].update(a.get("rework", {}).get(iid, {}))
                for other, patch in a.get("rework_also", {}).items():
                    if other in by_id and other != iid:
                        by_id[other].update(patch)
                doc["items"] += a.get("split", {}).get(iid, [])
            elif task["phase"] == "fix-gates":
                for fix in a.get("fix_gates", []):
                    by_id[fix["id"]].update({k: v for k, v in fix.items() if k != "id"})
            elif task["phase"] == "update":
                up = a.get("update", {})
                for iid, patch in up.get("patch", {}).items():
                    by_id[iid].update(patch)
                if "open_points" in up:
                    doc["open_points"] = up["open_points"]
            elif task["phase"] == "rework-set":
                for iid, patch in a.get("set_fix", {}).items():
                    by_id[iid].update(patch)
        wp.parent.mkdir(parents=True, exist_ok=True)
        wp.write_text(json.dumps(doc, indent=1))
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
    print("```json\n" + json.dumps({"status": "DONE", "findings": findings}) + "\n```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
