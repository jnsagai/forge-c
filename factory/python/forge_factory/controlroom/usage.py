"""Model usage and cost (CR-T031; research R7).

Records per agent stage execution:
  * native Fabro stages: the KPI source events `agent.usage_recorded` (provider-reported; basis reported:fabro);
  * ACP stages (Codex authors, Claude inspectors): Fabro reports no model or tokens for them, so the forge ACP proxy
    writes one usage line per prompt result to .forge-run/acp/<node>.proxy.jsonl (basis reported:acp-proxy);
    a completed ACP stage without such a line counts as `not_reported` - never as zero tokens.
Cost is computed only from the configured price table; a model without a price (and the subscription-backed ACP
models) shows NOT_MEASURED with the reason. Tokens: `new` = input + output (non-cached), cache reads separate.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


def role_of(node: str) -> str:
    if node.endswith(("_author", "_triage")) or "_author" in node:
        return "author"
    if node.endswith("_inspector"):
        return "inspector"
    if node == "release_manager":
        return "release"
    return "other"


def station_of(node: str) -> str:
    m = re.match(r"^swe(\d)_", node)
    return f"SWE.{m.group(1)}" if m else ("SHIPPING" if node == "release_manager" else "OTHER")


def _profile(ws: Path) -> dict:
    try:
        return json.loads((ws / ".forge-run/model-profile.json").read_text())
    except (OSError, ValueError):
        return {}


def _proxy_usage(ws: Path, node: str) -> list[dict]:
    p = ws / ".forge-run/acp" / f"{node}.proxy.jsonl"
    out = []
    try:
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("event") == "usage":
                out.append(r)
    except OSError:
        pass
    return out


def cost(model: str, tokens_in: int | None, tokens_out: int | None, prices: dict, acp: bool) -> dict:
    p = prices.get(model)
    if not p:
        return {"status": "NOT_MEASURED", "reason": "subscription; no per-token price" if acp else
                "no per-token price configured (config/factory/controlroom.yaml prices)"}
    if tokens_in is None or tokens_out is None:
        return {"status": "NOT_MEASURED", "reason": "token counts not reported"}
    v = tokens_in / 1e6 * p["input_per_mtok"] + tokens_out / 1e6 * p["output_per_mtok"]
    return {"status": "MEASURED", "value": round(v, 4), "currency": p["currency"], "source": "config price table"}


def records(ws: Path, events: list[dict]) -> list[dict]:
    """Usage records of one attempt workspace; `events` are its KPI source events."""
    wo = ws.parent.name
    prof = _profile(ws)
    acp_models = {}
    for key in ("acp_authors", "acp_inspectors"):
        a = prof.get(key) or {}
        for n in a.get("nodes") or []:
            acp_models[n] = (a.get("model"), a.get("provider"))
    out = []
    for e in events:
        if e["type"] == "agent.usage_recorded":
            pl = e["payload"]
            out.append({"work_order": wo, "node": pl["stage"], "station": station_of(pl["stage"]),
                        "role": role_of(pl["stage"]), "model": pl["model"], "provider": prof.get("provider"),
                        "tokens_new": pl.get("tokens_new"), "cache_read": pl.get("cache_read"),
                        "tokens_in": None, "tokens_out": None, "basis": "reported:fabro", "acp": False})
    runs = defaultdict(int)  # completed executions per ACP node
    for e in events:
        if e["type"] == "stage.completed" and (e["payload"].get("node") in acp_models):
            runs[e["payload"]["node"]] += 1
    for node, n in sorted(runs.items()):
        model, provider = acp_models[node]
        recs = _proxy_usage(ws, node)
        for r in recs[:n]:
            ti, to = r.get("input"), r.get("output")
            out.append({"work_order": wo, "node": node, "station": station_of(node), "role": role_of(node),
                        "model": r.get("model") or model, "provider": provider,
                        "tokens_new": None if ti is None and to is None else (ti or 0) + (to or 0),
                        "cache_read": r.get("cache_read"), "tokens_in": ti, "tokens_out": to,
                        "basis": "reported:acp-proxy", "acp": True})
        for _ in range(max(0, n - len(recs))):
            out.append({"work_order": wo, "node": node, "station": station_of(node), "role": role_of(node),
                        "model": model, "provider": provider, "tokens_new": None, "cache_read": None,
                        "tokens_in": None, "tokens_out": None, "basis": "not_reported", "acp": True})
    return out


def summary(recs: list[dict], ready_packages: int, prices: dict) -> dict:
    def agg(key):
        g: dict = defaultdict(lambda: {"stages": 0, "reported": 0, "tokens_new": 0, "cache_read": 0, "runs": set(),
                                       "acp": False, "provider": None})
        for r in recs:
            k = tuple(r[x] for x in key)
            a = g[k]
            a["stages"] += 1
            a["runs"].add(r["work_order"])
            a["acp"] = a["acp"] or r["acp"]
            a["provider"] = a["provider"] or r["provider"]
            if r["basis"] != "not_reported" and r["tokens_new"] is not None:
                a["reported"] += 1
                a["tokens_new"] += r["tokens_new"]
                a["cache_read"] += r["cache_read"] or 0
        out = []
        for k, a in sorted(g.items(), key=lambda kv: -kv[1]["tokens_new"]):
            row = dict(zip(key, k, strict=True))
            row.update({"stages": a["stages"], "runs": len(a["runs"]), "provider": a["provider"],
                        "reported_stages": a["reported"], "not_reported_stages": a["stages"] - a["reported"],
                        "tokens_new": a["tokens_new"] if a["reported"] else None,
                        "cache_read": a["cache_read"] if a["reported"] else None,
                        "complete": a["reported"] == a["stages"]})
            if "model" in row:
                ins = sum(r["tokens_in"] or 0 for r in recs if r["model"] == row["model"] and r["tokens_in"] is not None)
                outs = sum(r["tokens_out"] or 0 for r in recs if r["model"] == row["model"] and r["tokens_out"] is not None)
                has_split = any(r["tokens_in"] is not None for r in recs if r["model"] == row["model"])
                row["cost"] = cost(row["model"], ins if has_split else None, outs if has_split else None, prices,
                                   a["acp"])
            out.append(row)
        return out
    total = len(recs)
    reported = [r for r in recs if r["basis"] != "not_reported" and r["tokens_new"] is not None]
    tok = sum(r["tokens_new"] for r in reported)
    return {"stages": total, "reported_stages": len(reported),
            "not_reported_share": round(1 - len(reported) / total, 4) if total else None,
            "tokens_new_reported": tok if reported else None,
            "tokens_per_ready_package": {"status": "MEASURED", "value": round(tok / ready_packages, 1),
                                         "complete": len(reported) == total} if ready_packages and reported else
            {"status": "NOT_MEASURED", "reason": "0 READY packages in the window" if not ready_packages
             else "no reported usage"},
            "by_model": agg(("model", "role")), "by_station": agg(("station",)), "by_role": agg(("role",))}


def window_usage(cache, start: str, end: str, cohort: str, prices: dict) -> dict:
    """Usage of the attempts admitted in [start, end] of the cohort, from the scorecard's event cache."""
    cache.refresh()
    by_attempt: dict[str, list] = defaultdict(list)
    ws_of: dict[str, Path] = {}
    with cache._lock:
        items = list(cache._c.items())
    for ws, c in items:
        if cohort not in ("all", c["cohort"]):
            continue
        for e in c["events"]:
            by_attempt[e["attempt_id"]].append(e)
            ws_of[e["attempt_id"]] = ws
    recs, ready = [], 0
    for att, evs in by_attempt.items():
        adm = next((e["ts_utc"] for e in evs if e["type"] == "work_order.admitted"), None)
        if not adm or not (start <= adm <= end):
            continue
        recs += records(ws_of[att], evs)
        ready += any(e["type"] == "work_order.closed" and e["payload"].get("outcome") in
                     ("READY_FOR_OFFLINE_REVIEW", "READY") for e in evs)
    out = summary(recs, ready, prices)
    out["records"] = recs[:500]
    out["note"] = ("ACP stages (Codex authors, Claude inspectors) are counted from the forge ACP proxy's usage lines; "
                   "runs before that recording show them as not reported. Tokens 'new' = input + output, cache reads "
                   "separate.")
    return out

