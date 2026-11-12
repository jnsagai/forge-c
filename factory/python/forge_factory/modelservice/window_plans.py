# ruff: noqa: E501
"""What a qualification window does once the model tier owns the GPU (feature 017, T042 smoke, T048 qualification).

Each plan is `plan(ctx) -> dict` for `window.run_window`: `ctx` carries the hard deadline, the clock and sleep. A plan
must stop on its own before the deadline (the controller aborts and restores the lane if it does not).

* smoke - the model service works the way production will use it: each catalog model answers with its pinned identity;
  author/inspector hand-overs (Ornith <-> qwen3.8, owner 2026-11-08) alternate so swaps are measured in both directions
  (p95 against SC-011, 30 s); a synthetic neighbour saturates its share while the factory tenant keeps its own (SC-003);
  every answer comes from the model named (SC-009). Metadata only.
* qualification - repeats every baseline order of the qualification set in the qualification lane, unchanged except a
  new order id, resuming from the same predecessor order (copied read-only into the lane's state). Resumable across
  windows: an order with a recorded outcome is not run again.
"""
from __future__ import annotations

import asyncio
import calendar
import json
import os
import shutil
import statistics
import subprocess
import threading
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[4]
STATE = Path("/mnt/data/forge-c/model-service")
TIER = "http://127.0.0.1:18480"
AUTHOR, INSPECTOR = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0", "qwen3.8:27b-q8_0"
SC011_SWAP_P95_S = 30.0
FACTORY_CONTEXT_TOKENS = 65536  # T044/R2: the factory per-agent limit every served model must offer


def _p95(xs: list[float]) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def _keys(path: Path) -> dict[str, str]:
    from model_tier.tenant_gateway import read_secret

    return {t: read_secret(path, t) for t in ("forge-qual", "sim-neighbour")}


def _swaps(outcomes: Path, since: float) -> list[dict]:
    out = []
    for line in outcomes.read_text().splitlines() if outcomes.is_file() else []:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") == "swap" and calendar.timegm(time.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ")) >= since - 1:
            out.append(e)
    return out


def smoke(ctx: dict, *, http: httpx.Client | None = None, keys: dict | None = None, catalog: dict | None = None,
          outcomes: Path = STATE / "tier-state/outcomes.jsonl", hand_overs: int = 10, neighbour_s: float = 600,
          evidence: Path | None = None) -> dict:
    http = http or httpx.Client(timeout=httpx.Timeout(30.0, read=900.0))
    keys = keys or _keys(STATE / "secrets/model-service.secrets")
    cat = catalog or yaml.safe_load((ROOT / "deploy/recipe/model-tier/catalog.yaml").read_text())
    pinned = {m["model"]: m["identity"]["revision_fingerprint"][:16] for m in cat["models"]}
    engines = {m["model"]: m.get("engine_url") for m in cat["models"]}
    hq = {"Authorization": f"Bearer {keys['forge-qual']}"}
    t0, res = time.time(), {"identities": {}, "calls": [], "wrong_model": 0, "failed": 0, "kv": {},
                            "gpu_samples": 0, "gpu_violations": [], "kv_served": {}}
    probe, tier_cg = ctx.get("gpu_apps"), ctx.get("tier_cgroup")

    def gpu_audit():  # T044 SC-001: during the plan only the model tier holds the GPU (no factory server or lock)
        if probe is None or not tier_cg:
            return
        res["gpu_samples"] += 1
        res["gpu_violations"] += [a["cgroup"] for a in probe() if tier_cg not in a["cgroup"]][:3]

    def ask(model: str, text: str) -> dict:
        r = http.post(TIER + "/v1/chat/completions", headers=hq, json={"model": model, "max_tokens": 16,
                                                                       "messages": [{"role": "user", "content": text}]})
        ident = r.headers.get("x-forge-model-identity")
        rec = {"model": model, "status": r.status_code, "identity": ident, "swap_ms": int(r.headers.get("x-forge-swap-ms") or 0),
               "queue_ms": int(r.headers.get("x-forge-queue-ms") or 0)}
        res["calls"].append(rec)
        gpu_audit()
        if r.status_code == 200 and model not in res["kv_served"] and engines.get(model):
            try:  # T044 KV capacity: the loaded engine's own context (llama.cpp /props), per sequence
                props = http.get(engines[model] + "/props", timeout=10).json()
                n_ctx = (props.get("default_generation_settings") or {}).get("n_ctx") or props.get("n_ctx")
                if n_ctx:
                    res["kv_served"][model] = int(n_ctx) // max(1, int(props.get("total_slots") or 1))
            except (httpx.HTTPError, ValueError, TypeError):
                pass
        res["failed"] += r.status_code != 200
        res["wrong_model"] += r.status_code == 200 and ident != pinned[model]
        return rec

    # 1. every model answers with its pinned identity
    for m in pinned:
        got = http.get(TIER + "/forge/v1/identity", params={"model": m}, headers=hq).json()
        res["identities"][m] = got.get("revision_fingerprint", "")[:16] == pinned[m]
        res["kv"][m] = got.get("context_limit")  # T044: served KV capacity per sequence
    # 2. author/inspector hand-overs: each one may swap; measured from the service's own swap records
    for i in range(hand_overs):
        if ctx["clock"]() > ctx["deadline"] - 900:
            break
        ask(AUTHOR, f"Write one sentence about requirement {i}.")
        ask(INSPECTOR, f"Inspect requirement {i} in one word.")
    swaps = [e for e in _swaps(outcomes, t0) if e.get("outcome") == "OK"]
    per_dir: dict[str, list[float]] = {}
    for e in swaps:
        if e.get("from_model"):
            per_dir.setdefault(f"{e['from_model']} -> {e['to_model']}", []).append((e["unload_ms"] + e["load_ms"]) / 1000)
    res["swap_s"] = {k: {"n": len(v), "p95": _p95(v), "median": statistics.median(v)} for k, v in per_dir.items()}
    res["sc011_pass"] = bool(per_dir) and all((_p95(v) or 1e9) <= SC011_SWAP_P95_S for v in per_dir.values())
    res["cold_swaps"] = sum(1 for e in swaps if not e.get("warm"))
    # T044 SC-010: every model change of the alternating run is a swap in the service's own records
    seq = [c["model"] for c in res["calls"]]
    res["model_changes"] = sum(1 for i, m in enumerate(seq) if i == 0 or m != seq[i - 1])
    res["sc010_pass"] = bool(seq) and res["failed"] == 0 and len(swaps) >= res["model_changes"]
    # 3. a saturating neighbour while the factory tenant keeps working (SC-003)
    from model_tier import neighbour

    nb: dict = {}
    run_s = max(0.0, min(neighbour_s, ctx["deadline"] - ctx["clock"]() - 600))
    if run_s > 30:
        cfg = neighbour.NeighbourConfig(base_url=TIER + "/v1", api_key=keys["sim-neighbour"], model=INSPECTOR, concurrency=4,
                                        prompt_tokens=2000, max_tokens=64, duration_s=run_s)
        th = threading.Thread(target=lambda: nb.update(asyncio.run(neighbour.run(cfg))))
        th.start()
        end = time.monotonic() + run_s
        while time.monotonic() < end:
            ask(INSPECTOR, "One word: OK?")
        th.join()
    res["neighbour"] = {k: nb.get(k) for k in ("requests", "ok", "by_status", "latency_ms")}
    res["sc003_pass"] = res["failed"] == 0
    # T044 SC-002: every answered call carries the served-model fingerprint
    res["sc002_pass"] = all(c["identity"] for c in res["calls"] if c["status"] == 200)
    # served measurement where the engine reports it, else the declared (catalog) identity, with its basis
    res["kv_basis"] = {m: ("served" if m in res["kv_served"] else "declared") for m in res["kv"]}
    res["kv"] = {m: res["kv_served"].get(m, v) for m, v in res["kv"].items()}
    res["kv_pass"] = bool(res["kv"]) and all((v or 0) >= FACTORY_CONTEXT_TOKENS for v in res["kv"].values())
    res["sc001_pass"] = None if not res["gpu_samples"] else not res["gpu_violations"]  # no probe: NOT_RUN
    # T044 per-tenant latency from the service's own request records of this plan
    lat: dict[str, list[dict]] = {}
    for line in outcomes.read_text().splitlines() if outcomes.is_file() else []:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not e.get("kind") and e.get("tenant_id") and \
                calendar.timegm(time.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ")) >= t0 - 1:
            lat.setdefault(e["tenant_id"], []).append(e)
    res["tenant_latency"] = {t: {"n": len(v), "ok": sum(1 for e in v if e.get("status") == 200),
                                 "p50_total_ms": statistics.median([e.get("total_ms") or 0 for e in v]),
                                 "p95_total_ms": _p95([e.get("total_ms") or 0 for e in v]),
                                 "p95_queue_ms": _p95([e.get("queue_ms") or 0 for e in v])} for t, v in lat.items()}
    res["sc009_pass"] = res["wrong_model"] == 0 and res["failed"] == 0
    res["identities_pass"] = all(res["identities"].values())
    res["calls"] = len(res["calls"])
    if evidence:
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "smoke.json").write_text(json.dumps(res, indent=1))
    return res


# ---- qualification (T048) ------------------------------------------------------------------------------------------------
def orders(qset: dict, stamp: str) -> list[dict]:
    """One qualification order per phase with a baseline: the baseline's launch with a new id."""
    out = []
    for ph in qset["phases"]:
        launch = (ph.get("baseline") or {}).get("launch")
        if not launch or not launch.get("example"):
            continue
        base = ph["baseline"]["order"]
        out.append({"phase": ph["phase"], "baseline": base, "wo": base.replace("WO-F014-", "WO-F017Q-").rsplit("-", 2)[0] + f"-{stamp}",
                    **launch})
    return out


def argv_of(o: dict, model: str = AUTHOR) -> list[str]:
    a = ["python", "-m", "forge_factory.workorder", "--example", o["example"], "--wo", o["wo"], "--model", model]
    if o.get("purpose"):
        a += ["--purpose", o["purpose"]]
    if o.get("stop_after"):
        a += ["--stop-after", o["stop_after"]]
    if o.get("resume_from"):
        a += ["--resume-from", o["resume_from"]]
    if o.get("provided_from"):
        a += ["--provided-from", o["provided_from"]]
    if o.get("profile"):
        a += ["--profile", o["profile"]]
    return a


def seed_lane(o: dict, owner_workorders: Path, lane_workorders: Path) -> list[str]:
    """Copy (read-only source) the predecessor and provided orders the new order resumes from into the lane's state."""
    copied = []
    for wo in (o.get("resume_from"), o.get("provided_from")):
        if wo and not (lane_workorders / wo).exists():
            shutil.copytree(owner_workorders / wo, lane_workorders / wo, symlinks=True)
            copied.append(wo)
    return copied


def qualification(ctx: dict, *, qset_path: Path = ROOT / "config/factory/qualification-set.yaml",
                  owner_workorders: Path = Path("/mnt/data/forge-c/swe1-fabro-20261031/lrtx/state/workorders"),
                  lane_root: Path = STATE / "qual-lane", env: dict | None = None, run=None,
                  stamp: str | None = None, blocked_profiles: dict | None = None) -> dict:
    """Without an injected `run`, each order runs in the qualification lane's own namespace (lane_run.LaneRunner):
    the lane must have been bootstrapped outside the window, and the relay to the tier lives for this plan only."""
    qset = yaml.safe_load(Path(qset_path).read_text())
    if run is None:
        from .lane import LaneConfig
        from .lane_run import LaneRunner

        profiles = sorted({(ph.get("baseline") or {}).get("launch", {}).get("profile") for ph in qset["phases"]} - {None})
        if not profiles:
            return {"ran": [], "refused": "QUALIFICATION_SET_WITHOUT_PROFILE"}
        runners = {pid: LaneRunner(LaneConfig(root=Path(lane_root)), pid) for pid in profiles}
        why = {pid: w for pid, r in runners.items() if (w := r.ready())}
        if len(why) == len(runners):
            return {"ran": [], "refused": "; ".join(f"{w}:{pid}" for pid, w in sorted(why.items()))}

        def run_in_lane(argv, **kw):  # each order runs under its own baseline profile
            return runners[argv[argv.index("--profile") + 1]].run(argv, **kw)
        first = next(r for pid, r in runners.items() if pid not in why)
        with first.relay():
            return qualification(ctx, qset_path=qset_path, owner_workorders=owner_workorders, lane_root=lane_root,
                                 env=first.env(), run=run_in_lane, stamp=stamp, blocked_profiles=why)
    ledger_path = lane_root / "qualification-ledger.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.is_file() else {"stamp": stamp or time.strftime("%Y%m%d"), "orders": {}}
    lane_wos = lane_root / "state/workorders"
    lane_wos.mkdir(parents=True, exist_ok=True)
    env = env or {**os.environ, "FORGE_STATE_DIR": str(lane_root / "state"), "FORGE_LRTX_ROOT": str(lane_root)}
    done, left, blocked = [], [], {}
    for o in orders(qset, ledger["stamp"]):
        if o["wo"] in ledger["orders"]:
            continue
        if (blocked_profiles or {}).get(o.get("profile")):  # explicit, not ledgered: it runs once the lane can
            blocked[o["wo"]] = blocked_profiles[o["profile"]]
            continue
        if ctx["clock"]() > ctx["deadline"] - 3600:  # never start an order that cannot finish inside the window
            left.append(o["wo"])
            continue
        o["seeded"] = seed_lane(o, owner_workorders, lane_wos)
        t0 = time.time()
        p = run(argv_of(o), cwd=str(ROOT), env=env, capture_output=True, text=True,
                timeout=max(60, int(ctx["deadline"] - ctx["clock"]() - 600)))
        logs = lane_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / f"{o['wo']}.out").write_text(f"{getattr(p, 'stdout', '') or ''}\n--- stderr ---\n{getattr(p, 'stderr', '') or ''}")
        ledger["orders"][o["wo"]] = {"phase": o["phase"], "baseline": o["baseline"], "exit": p.returncode,
                                     "status": _order_status(getattr(p, "stdout", "") or ""),
                                     "wall_s": round(time.time() - t0), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        ledger_path.write_text(json.dumps(ledger, indent=1))
        done.append(o["wo"])
    out = {"ran": done, "not_started_for_time": left, "ledger": str(ledger_path)}
    if blocked:
        out["blocked"] = blocked
    return out


def _order_status(stdout: str) -> str | None:
    """The work order's own verdict (its last JSON line): exit 0 also ends a BLOCKED order."""
    for line in reversed(stdout.strip().splitlines()):
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if isinstance(doc, dict) and "status" in doc:
            return str(doc["status"])
    return None
