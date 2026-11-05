"""Real M7 timer/VerificationJobs with an earlier finite mission deadline.

Role/native/CRE leaves are explicit deterministic fixtures: no model, provider,
production order, grant, candidate acceptance or source deployment is exercised.
The actual review function, OS timer and persisted CPU queue are under test.
"""
import json
import os
from pathlib import Path
import signal
import tempfile
import time
from types import SimpleNamespace

SIG = "the line maintainer verification uses its later job wall beyond the finite mission deadline"


def main():
    with tempfile.TemporaryDirectory(prefix="rpr154-") as temporary:
        root = Path(temporary)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ.pop("FORGE_DURABLE_AUTONOMY", None)
        from forge_factory.afo import line_maintenance_coordinator as C
        from forge_factory.afo.completion_receipt import Context
        from forge_factory.afo.durable import Refused
        from forge_factory.afo.mission_ledger import MissionLedger
        from forge_factory.afo.queue import Store
        from forge_factory.afo.verification_job import VerificationJobs
        from forge_factory.afo import policy as AP
        from forge_factory.reliability import policy as CP, store as CS

        store = Store(root / "state/supervisor/line-queue.sqlite3")
        ledger = MissionLedger(store)
        case = {"proposal_id": "mnt-rpr154", "base": "a" * 40,
                "incident": {"fingerprint": "rpr154-fixture"}}
        limits = {"max_attempts": 0, "max_jobs": 0, "max_requests": 0,
                  "max_tokens": 0, "max_tools": 0, "max_corrections": 0}

        def job(n, mission_seconds, job_seconds):
            now = time.time()
            mission = "rpr154-mission-" + str(n)
            ledger.register(mission, mission, {**limits, "deadline": now + mission_seconds},
                            "ISOLATED_TIMER_FIXTURE", authorize=lambda *a: True)
            return {"job_id": "afo-agent-" + str(n) * 24, "mission_id": mission,
                    "case": str(root / "mnt-rpr154/case.json"), "case_sha256": "b" * 64,
                    "deadline_epoch": now + job_seconds}

        def authorized(_store, current, _eff):
            # Preserve the actual finite mission check at the review's authorization leaves.
            deadline = ledger.snapshot(current["mission_id"])["limits"]["deadline"]
            if time.time() >= min(deadline, current["deadline_epoch"]):
                raise Refused("LINE_MAINTENANCE_DEADLINE")

        C._authorized = authorized
        C._quiet = lambda *a: True
        Context.from_job = lambda *a: None
        C.M.load_case = lambda *a: dict(case)
        C.M.submission = lambda *a, **k: ({"candidate": "c" * 40}, {})
        AP.load = lambda: SimpleNamespace()
        CP.load = lambda: SimpleNamespace()
        CS.CREStore = lambda: object()
        terminal = {"outcome": "ELIGIBLE_FOR_OFFLINE_REVIEW", "cre_promotion_id": "FIXTURE_ONLY",
                    "auto_deployment_allowed": False}

        # Equal/long deadlines reach the exact controller path before any timer test.
        C.M.process = lambda *a, **k: dict(terminal)
        control = C.review(store, job(1, 10, 10), SimpleNamespace(), fence=lambda: True, client=object())
        if control["status"] != "ELIGIBLE_FOR_OFFLINE_REVIEW":
            print("REPRODUCER_ERROR:CONTROL:review path not reached")
            return 2

        current = job(2, 1.25, 10)
        mission_deadline = ledger.snapshot(current["mission_id"])["limits"]["deadline"]
        observed = {}

        def slow(*a, **k):
            observed["armed_deadline"] = time.time() + signal.getitimer(signal.ITIMER_REAL)[0]
            time.sleep(2.5)
            return dict(terminal)

        C.M.process = slow
        started = time.time()
        try:
            C.review(store, current, SimpleNamespace(), fence=lambda: True, client=object())
            print("REPRODUCER_ERROR:CONTROL:expired mission was accepted")
            return 2
        except (TimeoutError, Refused):
            elapsed = time.time() - started
        if "armed_deadline" not in observed:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:review ended before independent work")
            return 2
        late_timer = observed["armed_deadline"] > mission_deadline + 0.05

        # A pre-existing queue row must also be narrowed, never recreated/refilled.
        queued = job(3, 2, 10)
        queue = VerificationJobs(store)
        queue.ensure(queued["job_id"], queued["case_sha256"], deadline_epoch=queued["deadline_epoch"])
        C.L.directory = lambda _id: root / "review-log"
        C.L.execution_context = lambda _job: {}
        C.subprocess.Popen = lambda *a, **k: None  # queue dispatch fixture; no child is launched
        C._dispatch_review(store, queued)
        row = queue.get(queued["job_id"])
        finite = ledger.snapshot(queued["mission_id"])["limits"]["deadline"]
        late_queue = row["record"]["deadline_epoch"] > finite + 0.001
        if row["record"]["dispatches"] != 1:
            print("REPRODUCER_ERROR:CONTROL:queue identity or dispatch count changed")
            return 2
        print(json.dumps({"timer_late": late_timer, "queue_late": late_queue,
                          "actual_review_seconds": round(elapsed, 3), "fixture_only": True}))
        if late_timer or late_queue:
            print("SYMPTOM_PRESENT:" + SIG)
            return 1
        if elapsed > 2:
            print("REPRODUCER_ERROR:TIMING:mission timer was armed but observed too late")
            return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("REPRODUCER_ERROR:" + type(exc).__name__ + ":" + str(exc)[:160])
        raise SystemExit(2)
