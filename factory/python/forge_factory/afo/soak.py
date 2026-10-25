"""AFO-T067 (AFO-FR-069; AT-062) - opt-in soak runner: real wall-clock health samples, never extrapolated.

`start` needs an operator authorization ref and a target (24, 72 or 168 h). Each sample appends one line to
<state>/afo/soak/<soak_id>.jsonl (0600): wall UTC, monotonic seconds and the health probes (data volume, Conductor
heartbeat via the independent watchdog check, Fabro, model gateway). `report` counts ONLY intervals between
consecutive samples whose gap is <= 2 x interval and whose wall and monotonic deltas agree (no clock jump, no fake
clock); every other gap is an observation hole and is reported as unknown outage exposure, never as up time.
DEMONSTRATED requires covered hours >= target with every covered sample healthy; anything less is IN_PROGRESS or
NOT_DEMONSTRATED. A soak never changes the AFO mode.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from ..common import state_dir, utc_now

TARGETS = (24, 72, 168)
CLOCK_SKEW_S = 5.0


def path(soak_id: str) -> Path:
    if not re.fullmatch(r"soak-[0-9a-z-]{4,40}", soak_id):
        raise ValueError("bad soak id")
    return state_dir() / "afo/soak" / f"{soak_id}.jsonl"


def _append(p: Path, rec: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def live_probes() -> dict:
    from . import host, watchdog
    from .scheduler import _healthy

    fabro = os.environ.get("FORGE_FABRO_URL", "http://127.0.0.1:32291/api/v1").rstrip("/").rsplit("/api", 1)[0]
    return {
        "data_volume": lambda: host.preflight()["ok"],
        "conductor": lambda: watchdog.check(120)["ok"],
        "fabro": lambda: _healthy(fabro + "/health"),
        "gateway": lambda: _healthy(
            os.environ.get("FORGE_LRTX_GATEWAY_URL", "http://127.0.0.1:11437/v1").rstrip("/").removesuffix("/v1") + "/health"
        ),
    }


def start(soak_id: str, target_h: int, interval_s: float, authorization_ref: str) -> dict:
    if target_h not in TARGETS or not authorization_ref.strip() or not 5 <= interval_s <= 600:
        raise ValueError("target 24|72|168 h, an authorization ref and an interval of 5..600 s are required")
    p = path(soak_id)
    if p.exists():
        raise ValueError("soak exists (append samples with `sample`, never restart a soak id)")
    head = {
        "kind": "start",
        "soak_id": soak_id,
        "target_hours": target_h,
        "interval_s": interval_s,
        "authorization_ref": authorization_ref,
        "utc": utc_now(),
        "wall": time.time(),
        "mono": time.monotonic(),
        "boot_id": _boot_id(),
    }
    _append(p, head)
    return head


def _boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "unknown"


def sample(soak_id: str, probes: dict | None = None) -> dict:
    probes = probes or live_probes()
    res = {}
    for k, f in probes.items():
        try:
            res[k] = bool(f())
        except Exception:  # noqa: BLE001 - a probe error is an unhealthy sample, never a skipped one
            res[k] = False
    rec = {
        "kind": "sample",
        "utc": utc_now(),
        "wall": time.time(),
        "mono": time.monotonic(),
        "boot_id": _boot_id(),
        "healthy": all(res.values()),
        "probes": res,
    }
    _append(path(soak_id), rec)
    return rec


def run(soak_id: str, probes: dict | None = None, max_samples: int | None = None) -> int:
    head = json.loads(path(soak_id).read_text().splitlines()[0])
    n = 0
    while max_samples is None or n < max_samples:
        sample(soak_id, probes)
        n += 1
        if report(soak_id)["status"] == "DEMONSTRATED":
            break
        time.sleep(head["interval_s"])
    return n


def report(soak_id: str) -> dict:
    lines = [json.loads(x) for x in path(soak_id).read_text().splitlines() if x.strip()]
    head, samples = lines[0], [x for x in lines[1:] if x["kind"] == "sample"]
    iv = float(head["interval_s"])
    covered = healthy_s = 0.0
    holes, jumps = [], []
    for a, b in zip(samples, samples[1:], strict=False):
        dw, dm = b["wall"] - a["wall"], b["mono"] - a["mono"]
        if a["boot_id"] != b["boot_id"] or dm < 0 or abs(dw - dm) > CLOCK_SKEW_S:
            jumps.append(
                {
                    "from": a["utc"],
                    "to": b["utc"],
                    "wall_s": round(dw, 1),
                    "mono_s": round(dm, 1) if a["boot_id"] == b["boot_id"] else None,
                }
            )
            continue
        if dw > 2 * iv:
            holes.append({"from": a["utc"], "to": b["utc"], "seconds": round(dw, 1)})
            continue
        covered += dw
        if a["healthy"] and b["healthy"]:
            healthy_s += dw
    unhealthy = sum(not s["healthy"] for s in samples)
    target_s = head["target_hours"] * 3600
    if covered >= target_s and healthy_s == covered and not holes and not jumps:
        status = "DEMONSTRATED"
    elif covered < target_s and not holes and not jumps:
        status = "IN_PROGRESS"
    else:
        status = "NOT_DEMONSTRATED"
    return {
        "soak_id": soak_id,
        "target_hours": head["target_hours"],
        "authorization_ref": head["authorization_ref"],
        "samples": len(samples),
        "covered_hours": round(covered / 3600, 4),
        "healthy_hours": round(healthy_s / 3600, 4),
        "unhealthy_samples": unhealthy,
        "observation_holes": holes[:20],
        "clock_or_boot_jumps": jumps[:20],
        "availability": round(healthy_s / covered, 6) if covered else None,
        "status": status,
        "note": "real wall-clock samples only; holes and jumps are unknown exposure, never up time",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.afo.soak")
    ap.add_argument("cmd", choices=["start", "run", "report"])
    ap.add_argument("soak_id")
    ap.add_argument("--target-hours", type=int, default=24)
    ap.add_argument("--interval", type=float, default=60)
    ap.add_argument("--authorization-ref", default="")
    a = ap.parse_args(argv)
    if a.cmd == "start":
        print(json.dumps(start(a.soak_id, a.target_hours, a.interval, a.authorization_ref)))
    elif a.cmd == "run":
        print(json.dumps({"samples": run(a.soak_id)}))
    if a.cmd != "start":
        print(json.dumps(report(a.soak_id), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
