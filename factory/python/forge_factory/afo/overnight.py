"""Finite, pre-approved serial intake and Git status recording; Conductor owns all execution.

No inference, retry scheduler, allowance renewal or source promotion here. Failed
orders keep their original accounting. The factory survives this window's end.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from ..common import REPO_ROOT, utc_now
from .durable import immutable_json, strict_json
from .queue import Store


def run(plan_path):
    from .cli import approve
    from .mission_admin import register
    from .operations import Intent
    from .policy import load

    plan = strict_json(Path(plan_path).read_bytes(), 4 * 1024 * 1024)
    if (
        plan.get("schema") != "forge-c/overnight-intake/1"
        or not 0 < len(plan["orders"]) <= 8
        or not 0 < plan["deadline_epoch"] - plan["started_epoch"] <= 28800
    ):
        raise ValueError("FINITE_PREAPPROVED_WINDOW_REQUIRED")
    if subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True).strip() != plan["source_revision"]:
        raise ValueError("OVERNIGHT_SOURCE_REVISION_CHANGED")
    out = Path(plan["progress_repo"])
    out.mkdir(parents=True, exist_ok=True)

    def git(*args, check=True):
        return subprocess.run(["git", "-C", str(out), *args], capture_output=True, text=True, timeout=25, check=check)

    if not (out / ".git").is_dir():
        git("init", "-b", plan["progress_branch"])
        git("config", "user.name", "Forge-C Overnight Recorder")
        git("config", "user.email", "forge-c-mission@localhost")
        git("remote", "add", "origin", "git@github.com:jnsagai/forge-c.git")
    immutable_json(out / "plan.json", plan)
    store = Store()
    last_commit = 0
    while time.time() < plan["deadline_epoch"]:
        intent = Intent().read()
        states = {row["order_id"]: row["state"] for row in store.orders()}
        pending = next((entry for entry in plan["orders"] if entry["order_id"] not in states), None)
        prior = [entry for entry in plan["orders"] if entry["order_id"] in states]
        terminal = {"BLOCKED", "FAILED", "CANCELLED", "READY_FOR_OFFLINE_REVIEW"}
        if pending and intent["mode"] == "RUNNING" and all(states[e["order_id"]] in terminal for e in prior):
            eff = load()
            with Intent().lock():
                now_intent = Intent().read()
                if now_intent["mode"] == "RUNNING" and now_intent["epoch"] == intent["epoch"]:
                    # Serialize QUEUED publication and mission binding against admission.
                    env = pending["envelope"]
                    oid, _ = store.submit(
                        env,
                        repo=REPO_ROOT,
                        max_queued=int(eff.get("queue.max_queued_orders")),
                        approve=lambda item, eff=eff: approve(item, eff),
                    )
                    mission = dict(pending["mission"])
                    mission["limits"] = {
                        **mission["limits"],
                        "deadline": min(
                            plan["deadline_epoch"], time.time() + float(eff.get("budgets.max_order_wall_seconds")) - 5
                        ),
                    }
                    # A restart adopts existing mission bytes; it cannot refresh its deadline.
                    with store.tx() as c:
                        existing = c.execute(
                            "SELECT record FROM afo_missions WHERE mission_id=?", (mission["mission_id"],)
                        ).fetchone()
                    if existing:
                        mission["limits"] = json.loads(existing[0])["limits"]
                    register(store, mission, eff)
                    if oid != pending["order_id"]:
                        raise ValueError("PREAPPROVED_ORDER_ID_CHANGED")
        snapshot = {
            "captured_utc": utc_now(),
            "deadline_epoch": plan["deadline_epoch"],
            "source_revision": plan["source_revision"],
            "intent": {k: intent[k] for k in ("mode", "epoch")},
            "orders": [
                {
                    "order_id": e["order_id"],
                    "state": (store.order(e["order_id"]) or {}).get("state", "NOT_SUBMITTED"),
                    "attempts": store.attempts(e["order_id"]),
                }
                for e in plan["orders"]
            ],
            "claim": "EXPERIMENTAL_WORK_ONLY;NATIVE_GATES_AND_OFFLINE_REVIEW_REMAIN_REQUIRED",
        }
        # No raw prompts, model reasoning, private inputs, credentials or full job records are published.
        for entry in snapshot["orders"]:
            entry["attempts"] = [{k: a[k] for k in ("attempt_id", "seq", "state")} for a in entry["attempts"]]
        with store.tx() as c:
            snapshot["requests"] = c.execute("SELECT count(*) FROM afo_request_ledger").fetchone()[0]
            snapshot["native_ownership"] = [
                dict(r) for r in c.execute("SELECT resource,holder,epoch FROM afo_resource_ownership")
            ]
        tmp = out / ".progress.tmp"
        tmp.write_text(json.dumps(snapshot, indent=2) + "\n")
        os.replace(tmp, out / "progress.json")
        if time.time() - last_commit >= 300:
            git("add", "plan.json", "progress.json")
            if git("diff", "--cached", "--quiet", check=False).returncode:
                git("commit", "-m", "Record bounded Qwen overnight progress " + snapshot["captured_utc"])
            published = git("push", "-u", "origin", plan["progress_branch"], check=False).returncode == 0
            print(
                json.dumps({"at": snapshot["captured_utc"], "published": published, "requests": snapshot["requests"]}), flush=True
            )
            last_commit = time.time()
        time.sleep(min(30, max(0, plan["deadline_epoch"] - time.time())))
    print(json.dumps({"status": "WINDOW_FINISHED", "factory": "LEFT_RUNNING", "at": utc_now()}), flush=True)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", type=Path)
    raise SystemExit(run(ap.parse_args().plan))
