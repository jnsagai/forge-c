"""KPI service: compute + persist immutable snapshots (model-free), baselines (measurement-only), lookup."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..common import state_dir
from .engine import serialize, snapshot
from .sources import collect_all


def kpi_dir() -> Path:
    d = state_dir() / "kpi"
    d.mkdir(parents=True, exist_ok=True)
    return d


def window(days: int = 7, end: datetime | None = None) -> tuple[str, str]:
    end = end or datetime.now(UTC)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (end - timedelta(days=days)).strftime(fmt), end.strftime(fmt)


def load_baselines() -> dict:
    p = kpi_dir() / "baselines.json"
    return json.loads(p.read_text()) if p.is_file() else {"frozen": False, "classes": {}, "mode": "measurement_only"}


def compute_and_store(events: list[dict] | None = None, days: int = 7, release_status: str = "IN_PROGRESS") -> dict:
    evs = events if events is not None else collect_all()
    ws, we = window(days)
    snap = snapshot(evs, ws, we, release_status, load_baselines())
    p = kpi_dir() / f"{snap['snapshot_id']}.json"
    if not p.exists():  # immutable: same id => identical content
        p.write_bytes(serialize(snap))
    (kpi_dir() / "latest").write_text(snap["snapshot_id"])
    return snap


def latest_snapshot() -> dict | None:
    p = kpi_dir() / "latest"
    if not p.is_file():
        return None
    f = kpi_dir() / f"{p.read_text().strip()}.json"
    return json.loads(f.read_text()) if f.is_file() else None


def calibration_dataset(events: list[dict]) -> dict:
    """KPI-T019: measurement-only per-class samples (driver/target/compiler/optimization/safety profile).

    Never invents an SLA or ideal time: a class becomes eligible for freezing only with >= the policy minimum of
    homogeneous samples, and freezing is an explicit, versioned act (`freeze_baseline`), never automatic.
    """
    from .engine import Engine, policy

    minimum = int(policy()["performance_reference"]["provisional_minimum_homogeneous_samples"])
    cls_of = {e["order_id"]: e["payload"]["class"] for e in events if e["type"] == "work_order.admitted"}
    eng = Engine(events, "0000-01-01T00:00:00Z", "9999-12-31T23:59:59Z")
    classes: dict[str, dict] = {}
    for s in eng.segments():
        c = cls_of.get(s["order"])
        if not c:
            continue
        key = "|".join(str(c.get(k)) for k in ("driver_type", "complexity", "target_mcu", "compiler", "optimization",
                                               "safety_profile"))
        d = classes.setdefault(key, {"class": c, "samples": {}})
        d["samples"].setdefault(s["phase"], []).append(round(s["seconds"], 3))
    for d in classes.values():
        d["eligible_for_freeze"] = {p: len(v) >= minimum for p, v in d["samples"].items()}
    return {"mode": "measurement_only", "minimum_homogeneous_samples": minimum, "frozen": False, "classes": classes}


def freeze_baseline(dataset: dict, version: str) -> dict:
    eligible = {k: v for k, v in dataset["classes"].items() if any(v["eligible_for_freeze"].values())}
    if not eligible:
        raise ValueError("INSUFFICIENT_BASELINE: no class has the minimum homogeneous samples")
    return {"mode": "frozen", "version": version, "frozen": True, "classes": eligible}
