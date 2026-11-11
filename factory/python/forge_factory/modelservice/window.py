"""Qualification window controller (feature 017, T014; FR-019 option C; specs/.../window-controls.md).

Until the owner approves a cutover, the model tier may use the GPU only inside a window: the owner lane is held,
drained and stopped as a whole through its existing unsigned controls, the GPU is verified free, the model tier
runs a plan, and the lane is restored. Any failure restores the lane first. A window never touches the production
lane: if any GPU process outside the owner lane is present, the window is refused.

The lane and the tier are adapters (protocols below); the Omniverse2 adapters live in `window_adapters.py`.
The controller is dry-run unless asked otherwise, writes its record after every step, and two windows can never
overlap (host flock).
"""
from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

STEPS = ("drain_requested", "lane_idle", "lane_model_stopped", "gpu_free_verified", "tier_started", "identity_verified",
         "qualification_ran", "tier_stopped", "gpu_free_after_tier", "lane_model_restarted", "lane_resumed")


class LaneControl(Protocol):
    def hold(self) -> None: ...
    def release_hold(self) -> None: ...
    def idle(self) -> tuple[bool, str]: ...
    def suppress_redeploy(self) -> Any: ...  # context manager
    def stop_lane(self) -> None: ...
    def restart_lane(self) -> None: ...


class Tier(Protocol):
    def start(self) -> dict: ...
    def stop(self) -> None: ...


class WindowAbort(RuntimeError):
    pass


def window_lock(state_dir: Path):
    """Exclusive, non-blocking host lock; the returned file must stay open for the window's lifetime."""
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    f = open(Path(state_dir) / "window.lock", "a")  # noqa: SIM115 - held open on purpose
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_window(plan: Callable[[dict], dict], *, lane: LaneControl, tier: Tier, gpu_apps: Callable[[], list[dict]],
               gpu_free_mib: Callable[[], int], owner_cgroup: str, tier_cgroup: str, state_dir: Path,
               max_minutes: int, drain_timeout_s: int = 3600, gpu_free_min_mib: int = 44000,
               gpu_settle_s: int = 120, poll_s: int = 15, dry_run: bool = True,
               clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> dict:
    state_dir = Path(state_dir)
    wid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:6]
    rec: dict = {"window_id": wid, "planned_start": _now_iso(), "max_minutes": max_minutes, "dry_run": dry_run,
                 "steps": [], "outcome": None}
    out = state_dir / "windows" / f"{wid}.json"

    def save():
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, indent=1, sort_keys=True))
        os.replace(tmp, out)

    def step(name, **detail):
        rec["steps"].append({"step": name, "at": _now_iso(), **detail})
        save()

    def finish(outcome, **kw):
        rec.update(outcome=outcome, ended=_now_iso(), **kw)
        save()
        return rec

    lock = window_lock(state_dir)
    if lock is None:
        return finish("REFUSED", refusal="WINDOW_ALREADY_RUNNING")
    try:
        def foreign():
            return [a for a in gpu_apps() if owner_cgroup not in a["cgroup"] and tier_cgroup not in a["cgroup"]]

        if f := foreign():
            return finish("REFUSED", refusal="FOREIGN_GPU_HOLDER:" + ",".join(str(a["pid"]) for a in f))
        for name, part in (("lane", lane), ("tier", tier)):  # readiness is checked before anything is changed
            if hasattr(part, "preflight"):
                ok, why = part.preflight()
                if not ok:
                    return finish("REFUSED", refusal=f"{name.upper()}_NOT_READY:{why}")
        if dry_run:
            ok, why = lane.idle()
            return finish("DRY_RUN", checks={"lane_idle": ok, "lane_idle_detail": why, "foreign_gpu_holders": 0,
                                             "gpu_free_mib": gpu_free_mib()})

        start, hard_end = clock(), clock() + max_minutes * 60
        rec["hard_end_s"] = max_minutes * 60
        lane.hold()
        step("drain_requested")
        while True:
            ok, why = lane.idle()
            if ok:
                break
            if clock() - start > drain_timeout_s:
                lane.release_hold()
                return finish("REFUSED", refusal="LANE_NOT_IDLE", detail=why)
            sleep(poll_s)
        step("lane_idle", detail=why)

        stopped = tier_up = False
        with lane.suppress_redeploy():
            try:
                stopped = True  # a failed stop may leave the lane half down: the restore must still restart it
                lane.stop_lane()
                step("lane_model_stopped")
                _wait_gpu_free(gpu_apps, gpu_free_mib, owner_cgroup, gpu_free_min_mib, gpu_settle_s, poll_s, clock, sleep)
                step("gpu_free_verified", free_mib=gpu_free_mib())
                tier_up = True
                started = tier.start() or {}
                step("tier_started")
                step("identity_verified", identities=started.get("identities"))
                ctx = {"deadline": hard_end, "clock": clock, "sleep": sleep, "window_id": wid,
                       "gpu_apps": gpu_apps, "tier_cgroup": tier_cgroup}  # T044 SC-001 GPU ownership audit
                result = plan(ctx) or {}
                if clock() > hard_end:
                    raise WindowAbort("HARD_END_EXCEEDED")
                step("qualification_ran", result=result)
                tier.stop()
                tier_up = False
                step("tier_stopped")
                _wait_gpu_free(gpu_apps, gpu_free_mib, tier_cgroup, gpu_free_min_mib, gpu_settle_s, poll_s, clock, sleep)
                step("gpu_free_after_tier", free_mib=gpu_free_mib())
                lane.restart_lane()
                stopped = False
                step("lane_model_restarted")
                lane.release_hold()
                step("lane_resumed")
                return finish("COMPLETED")
            except Exception as exc:  # restore the lane first, whatever failed
                rec["error"] = f"{type(exc).__name__}:{exc}"
                save()
                try:
                    if tier_up:
                        tier.stop()
                        _wait_gpu_free(gpu_apps, gpu_free_mib, tier_cgroup, gpu_free_min_mib, gpu_settle_s, poll_s, clock,
                                       sleep)
                    if stopped:
                        lane.restart_lane()
                    lane.release_hold()
                except Exception as rexc:  # the admission hold stays set: nothing races a broken lane
                    rec["restore_error"] = f"{type(rexc).__name__}:{rexc}"
                    inc = state_dir / "incidents" / f"{wid}.json"
                    inc.parent.mkdir(parents=True, exist_ok=True)
                    inc.write_text(json.dumps({"kind": "QUALIFICATION_WINDOW_RESTORE_FAILED", "window_id": wid,
                                               "error": rec["error"], "restore_error": rec["restore_error"],
                                               "at": _now_iso(), "admission_hold": "SET"}, indent=1))
                    return finish("RESTORE_FAILED")
                return finish("ABORTED_RESTORED")
    finally:
        lock.close()


def _wait_gpu_free(gpu_apps, gpu_free_mib, cgroup, min_mib, settle_s, poll_s, clock, sleep):
    t0 = clock()
    while any(cgroup in a["cgroup"] for a in gpu_apps()) or gpu_free_mib() < min_mib:
        if clock() - t0 > settle_s:
            raise WindowAbort(f"GPU_NOT_FREE:{cgroup}")
        sleep(poll_s)


def main(argv: list[str] | None = None) -> int:
    """python -m forge_factory.modelservice.window run --plan smoke|qualification --max-minutes N [--execute]"""
    import argparse

    from model_tier import gpu

    from .window_adapters import ModelTier, OwnerLane

    ap = argparse.ArgumentParser(prog="window")
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--plan", choices=["smoke", "qualification", "none"], default="none")
    ap.add_argument("--max-minutes", type=int, required=True)
    ap.add_argument("--state", type=Path, default=Path("/mnt/data/forge-c/model-service/windows-state"))
    ap.add_argument("--execute", action="store_true", help="really drain the lane and use the GPU (default: dry run)")
    a = ap.parse_args(argv)
    repo = Path(__file__).resolve().parents[4]
    wid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    lane = OwnerLane(work=a.state / "work", window_id="w" + wid.replace("T", "").replace("Z", ""),
                     deadline=time.time() + a.max_minutes * 60)
    tier = ModelTier(repo=repo, window_id=wid)
    if a.plan == "none":
        def plan(ctx):
            return {}
    else:
        from . import window_plans
        plan = getattr(window_plans, a.plan)
    rec = run_window(plan, lane=lane, tier=tier, gpu_apps=gpu.compute_apps, gpu_free_mib=lambda: gpu.memory_mib()["free"],
                     owner_cgroup="forge-c-owner-development-", tier_cgroup="forge-model-tier", state_dir=a.state,
                     max_minutes=a.max_minutes, dry_run=not a.execute)
    print(json.dumps({k: rec.get(k) for k in ("window_id", "outcome", "refusal", "checks", "error")}, indent=1))
    return 0 if rec["outcome"] in ("COMPLETED", "DRY_RUN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
