# ruff: noqa: E501
"""Qualification report: the factory on its current setup against the production-like setup (feature 017, US3;
FR-014 to FR-016, FR-030, SC-005; contracts/qualification-report.schema.json).

Both sides are read from evidence that already exists: the per-node model exchange exports (one `run.json` per run,
with per-visit statistics) and the qualification set, which names, per SWE phase, the baseline runs that passed on
today's setup and the candidate runs of the qualification lane. Nothing is replayed. A side without runs is
NOT_RUN, never PASS. A phase that passes on the baseline and fails on the candidate is a blocking finding that
must carry a CAPA. The verdict is never QUALIFIED_FOR_OWNER_REVIEW with an open finding or a NOT_RUN phase.

    python -m forge_factory.modelservice.qualify report --set config/factory/qualification-set.yaml \
        --baseline-export DIR --candidate-export DIR --mirror deploy/recipe/params/omniverse2.yaml \
        --production deploy/recipe/params/production.yaml [--tier-outcomes FILE] --out DIR
"""
from __future__ import annotations

import argparse
import calendar
import json
import time
from collections import defaultdict
from pathlib import Path

import yaml

SCHEMA = Path(__file__).resolve().parents[4] / "config/schemas/model-service/qualification-report.schema.json"
DEVIATION_KEYS = ("reference_precision", "reference_context", "reference_sequences", "reference_kv_cache_tokens",
                  "gpu_vram_mib", "factory_machine", "identity_extension")
OUTCOMES = ("PASS", "FAIL", "BLOCKED")


def run_stats(export: Path) -> dict[str, dict]:
    """run_id -> run.json of a model-exchange export."""
    out = {}
    for f in Path(export).glob("runs/*/run.json") if export and Path(export).is_dir() else []:
        try:
            doc = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        out[doc["run"]["run_id"]] = doc
    return out


def measures(stats: dict[str, dict], run_ids: list[str]) -> dict[str, dict]:
    """Per node, summed over the given runs."""
    agg: dict[str, dict] = defaultdict(lambda: {"run_ids": [], "model_ms": 0, "prompt_tokens": 0, "output_tokens": 0,
                                               "reasoning_tokens": 0, "cache": 0, "retries": 0, "visits": 0})
    for rid in run_ids:
        doc = stats.get(rid)
        if doc is None:
            continue
        for v in doc["visits"].values():
            a = agg[v["node"]]
            if rid not in a["run_ids"]:
                a["run_ids"].append(rid)
            a["visits"] += 1
            for k in ("model_ms", "prompt_tokens", "output_tokens", "reasoning_tokens", "retries"):
                a[k] += int(v.get(k) or 0)
            a["cache"] += int(v.get("cache_reused_tokens") or 0)
    return dict(agg)


def windows(stats: dict[str, dict], run_ids: list[str]) -> list[tuple[float, float]]:
    out = []
    for rid in run_ids:
        r = (stats.get(rid) or {}).get("run") or {}
        if r.get("created_ms"):
            out.append((r["created_ms"], r.get("completed_ms") or time.time() * 1000))
    return out


def swaps_in(outcomes: Path | None, spans: list[tuple[float, float]]) -> tuple[int, float]:
    """Model-tier swaps (FR-030) that fell inside the candidate runs' time spans, and their total wait."""
    if not outcomes or not Path(outcomes).is_file() or not spans:
        return 0, 0.0
    n, wait = 0, 0.0
    for line in Path(outcomes).read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") != "swap" or e.get("outcome") != "OK":
            continue
        t = calendar.timegm(time.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ")) * 1000
        if any(a <= t <= b for a, b in spans):
            n += 1
            wait += (e.get("drain_ms", 0) + e.get("unload_ms", 0) + e.get("load_ms", 0)) / 1000
    return n, round(wait, 1)


def _side(entry: dict | None, node_stats: dict | None, status_default: str) -> dict:
    status = (entry or {}).get("gate_outcome")
    status = status if status in OUTCOMES and (entry or {}).get("runs") else status_default
    m: dict = {"status": status}
    if (entry or {}).get("gate_outcome"):
        m["gate_outcome"] = entry["gate_outcome"]
    if node_stats:
        p = node_stats["prompt_tokens"]
        m.update(run_ids=node_stats["run_ids"], model_time_s=round(node_stats["model_ms"] / 1000, 1), prompt_tokens=p,
                 output_tokens=node_stats["output_tokens"], reasoning_tokens=node_stats["reasoning_tokens"],
                 retries=node_stats["retries"], reworks=max(0, node_stats["visits"] - len(node_stats["run_ids"])),
                 cache_reuse_ratio=round(node_stats["cache"] / p, 3) if p else 0.0)
    return m


def deviations(mirror: dict, prod: dict) -> list[dict]:
    mv = {k: v["value"] for k, v in mirror["parameters"].items()}
    pv = {k: v["value"] for k, v in prod["parameters"].items()}
    out = []
    for k in DEVIATION_KEYS:
        if k in mv and mv.get(k) != pv.get(k):
            out.append({"property": k, "mirror_value": mv.get(k), "production_value": pv.get(k),
                        **({"note": "production value not yet confirmed"} if not prod["parameters"].get(k, {}).get("confirmed", True)
                           else {})})
    for note in mirror.get("not_proven_here") or []:
        out.append({"property": "not_proven_here", "mirror_value": note, "production_value": "proven only on production hardware"})
    return out


def build(qset: dict, baseline_export: Path, candidate_export: Path, mirror: dict, prod: dict,
          tier_outcomes: Path | None = None) -> dict:
    bstats, cstats = run_stats(baseline_export), run_stats(candidate_export)
    rows, findings, statuses = [], [], []
    for ph in qset["phases"]:
        b, c = ph.get("baseline") or {}, ph.get("candidate") or {}
        bm, cm = measures(bstats, b.get("runs") or []), measures(cstats, c.get("runs") or [])
        bsum, csum = _side(b, None, "NOT_RUN")["status"], _side(c, None, "NOT_RUN")["status"]
        statuses.append((bsum, csum))
        nswaps, wait = swaps_in(tier_outcomes, windows(cstats, c.get("runs") or []))
        for node in sorted(set(bm) | set(cm)) or ["(phase)"]:
            cand = _side(c, cm.get(node), "NOT_RUN")
            if cm.get(node):
                cand.update(swaps=nswaps, swap_wait_s=wait)
            rows.append({"phase": ph["phase"], "node": node, "baseline": _side(b, bm.get(node), "NOT_RUN"), "candidate": cand})
        if bsum == "PASS" and csum in ("FAIL", "BLOCKED"):
            ratio = f" (candidate samples passed {c['pass_ratio']})" if c.get("pass_ratio") else ""
            findings.append({"phase": ph["phase"], "summary": f"{ph['phase']} ({ph.get('lineage', '')}) passes on the current setup and "
                             f"is {csum} on the production-like setup{ratio}", "capa_id": ph.get("capa") or "CAPA-PENDING",
                             "evidence": [*(b.get("evidence") and [b["evidence"]] or []), *(c.get("evidence") and [c["evidence"]] or [])],
                             "status": ph.get("capa_status", "OPEN")})
    open_findings = [f for f in findings if f["status"] == "OPEN"]
    if any(s == "NOT_RUN" for pair in statuses for s in pair):
        verdict = "INCOMPLETE"
    elif open_findings or any(c != "PASS" for _, c in statuses):
        verdict = "NOT_QUALIFIED"
    else:
        verdict = "QUALIFIED_FOR_OWNER_REVIEW"
    report = {"report_id": "qual-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
              "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "baseline_setup": qset["baseline_setup"], "candidate_setup": qset["candidate_setup"],
              "rows": rows, "deviations": deviations(mirror, prod), "blocking_findings": findings, "verdict": verdict}
    validate(report)
    return report


def validate(report: dict) -> None:
    from jsonschema import Draft202012Validator

    errors = list(Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(report))
    if errors:
        raise ValueError("QUALIFICATION_REPORT_INVALID:" + "; ".join(e.message for e in errors[:3]))


def gate_outcome(workspace: Path) -> str | None:
    """The phase verdict of one order: PASS when its last inspection passed; BLOCKED when its phase stopped (a route or
    gate decided BLOCKED, e.g. rework budget exhausted) or its last inspection did not pass; None without a gate log.
    (Qualification window 4, 2026-11-12: a phase that ran out of rework rounds ended on REWORK, which the report showed
    as NOT_RUN.)"""
    log = Path(workspace) / ".forge-run/gates/gate-log.jsonl"
    if not log.is_file():
        return None
    last, blocked, any_entry = None, False, False
    for line in log.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        any_entry = True
        g = e.get("gate") if isinstance(e.get("gate"), dict) else {}
        if e.get("step") == "inspect" and g:
            last = g.get("decision")
            blocked = False  # only a stop after the last inspection counts
        if g.get("decision") == "BLOCKED":
            blocked = True
    if last == "PASS" and not blocked:
        return "PASS"
    return "BLOCKED" if any_entry else None


def fill_candidates(qset: dict, ledgers: list[Path]) -> dict:
    """The candidate side of every phase from the qualification lane's ledgers (the current one and kept earlier
    windows whose gate logs are genuine). Several samples of one phase: PASS only if every sample passed, else the
    worst outcome; each sample is listed (order, Fabro run, outcome) with the pass ratio."""
    samples: dict[str, list[dict]] = defaultdict(list)
    for ledger in ledgers:
        doc = json.loads(Path(ledger).read_text())
        for wo, rec in doc.get("orders", {}).items():
            ws = next((w for w in (Path(ledger).parent / "state/workorders" / wo / "workspace",
                                   Path(ledger).parent / wo / "workspace") if w.is_dir()), None)
            if ws is None:
                continue
            rid_f = ws / ".forge-run/fabro_run_id"
            samples[rec["phase"]].append({"order": wo, "run": rid_f.read_text().strip() if rid_f.is_file() else None,
                                          "outcome": gate_outcome(ws) or "BLOCKED", "at": rec.get("at")})
    rank = {"PASS": 0, "FAIL": 1, "BLOCKED": 2}
    for ph in qset["phases"]:
        got = sorted(samples.get(ph["phase"], []), key=lambda x: x.get("at") or "")
        if not got:
            ph["candidate"] = {"runs": [], "gate_outcome": None}
            continue
        worst = max((x["outcome"] for x in got), key=lambda o: rank.get(o, 2))
        ph["candidate"] = {"runs": [x["run"] for x in got if x["run"]], "gate_outcome": worst,
                           "samples": got, "pass_ratio": f"{sum(x['outcome'] == 'PASS' for x in got)}/{len(got)}"}
    return qset


def launch_of(workorders: Path, wo: str, queue: Path | None = None) -> dict:
    """How a baseline order was launched, from its manifest (and its queue envelope for the example target): enough to
    repeat exactly the same order under a new id in the qualification lane."""
    import sqlite3

    mf = Path(workorders) / wo / "workspace/.forge-run/manifest.json"
    if not mf.is_file():
        return {}  # no manifest: the order cannot be repeated exactly, so the plan skips it (never guessed)
    m = json.loads(mf.read_text())
    r = m.get("resumed_from") or {}
    provided = [p.get("from") or p.get("source_work_order") for p in (m.get("provided") or []) if isinstance(p, dict)]
    target = None
    if queue and Path(queue).is_file():
        with sqlite3.connect(f"file:{queue}?mode=ro", uri=True) as c:
            row = c.execute("SELECT envelope FROM afo_work_orders WHERE request_id=?", (wo,)).fetchone()
        target = json.loads(row[0]).get("target") if row else None
    prof = Path(((m.get("local_profile") or {}).get("config")) or "").stem or None
    return {"example": f"examples/{target}" if target else None, "purpose": m.get("purpose"),
            "stop_after": (m.get("phase_scope") or {}).get("stop_after"), "resume_from": r.get("source_work_order"),
            "provided_from": next((p for p in provided if p), None), "profile": prof}


def build_set(export: Path, workorders: Path, spec: list[dict], baseline: dict, candidate: dict, queue: Path | None = None) -> dict:
    """The qualification set from evidence: per spec entry {phase, lineage, patterns}, the newest run of a matching
    order that both succeeded and whose gate decided PASS. An entry without such a run stays without baseline runs
    (NOT_RUN), never assumed."""
    stats = sorted(run_stats(export).values(), key=lambda d: d["run"].get("created_ms") or 0)
    phases = []
    for item in spec:
        hit = None
        for doc in stats:
            r = doc["run"]
            wo = r.get("wo") or ""
            if r.get("status") != "succeeded" or not any(p in wo for p in item["patterns"]):
                continue
            if gate_outcome(Path(workorders) / wo / "workspace") == "PASS":
                hit = (wo, r["run_id"])
        phases.append({"phase": item["phase"], "lineage": item["lineage"],
                       "baseline": {"runs": [hit[1]], "gate_outcome": "PASS", "order": hit[0],
                                    "evidence": f"state/workorders/{hit[0]}/workspace/.forge-run/gates/gate-log.jsonl",
                                    "launch": {**launch_of(workorders, hit[0], queue),
                                               **({"example": item["example"]} if item.get("example") and not launch_of(workorders, hit[0], queue).get("example") else {})}} if hit
                       else {"runs": [], "gate_outcome": None},
                       "candidate": {"runs": [], "gate_outcome": None}})
    return {"baseline_setup": baseline, "candidate_setup": candidate, "phases": phases}


def render_md(r: dict) -> str:
    out = [f"# Qualification report {r['report_id']}", "",
           f"**Verdict: {r['verdict']}** - baseline `{r['baseline_setup']['label']}` against candidate `{r['candidate_setup']['label']}`.",
           "", "This is an input to the owner's cutover decision (FR-020), not an approval. NOT_RUN is never counted as PASS.", "",
           "| Phase | Node | Baseline | Candidate | Prompt tokens (b/c) | Output tokens (b/c) | Model time s (b/c) | Cache reuse (b/c) | Swaps |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in r["rows"]:
        b, c = row["baseline"], row["candidate"]
        out.append(f"| {row['phase']} | {row['node']} | {b['status']} | {c['status']} | {b.get('prompt_tokens', '-')}/{c.get('prompt_tokens', '-')} | "
                   f"{b.get('output_tokens', '-')}/{c.get('output_tokens', '-')} | {b.get('model_time_s', '-')}/{c.get('model_time_s', '-')} | "
                   f"{b.get('cache_reuse_ratio', '-')}/{c.get('cache_reuse_ratio', '-')} | {c.get('swaps', '-')} |")
    out += ["", "## Differences from production", ""]
    out += [f"- {d['property']}: mirror {d['mirror_value']} / production {d['production_value']}"
            + (f" ({d['note']})" if d.get("note") else "") for d in r["deviations"]] or ["- none"]
    out += ["", "## Blocking findings", ""]
    out += [f"- {f['phase']}: {f['summary']} - {f['capa_id']} ({f['status']})" for f in r["blocking_findings"]] or ["- none"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qualify")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("report")
    for k in ("set", "baseline-export", "candidate-export", "mirror", "production", "out"):
        rp.add_argument(f"--{k}", required=True, type=Path)
    rp.add_argument("--tier-outcomes", type=Path)
    sp = sub.add_parser("set")
    for k in ("export", "workorders", "spec", "out"):
        sp.add_argument(f"--{k}", required=True, type=Path)
    sp.add_argument("--queue", type=Path, help="the owner lane line queue (read-only), for each order's example target")
    cp = sub.add_parser("candidates")
    cp.add_argument("--set", required=True, type=Path)
    cp.add_argument("--ledger", required=True, type=Path, action="append", help="a lane ledger; repeat for kept windows")
    cp.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "candidates":
        doc = fill_candidates(yaml.safe_load(a.set.read_text()), a.ledger)
        a.out.write_text("# Candidate side filled by forge_factory.modelservice.qualify candidates (feature 017, T049) from the\n"
                         "# qualification lane ledgers; PASS only when every sample of a phase passed.\n"
                         + yaml.safe_dump(doc, sort_keys=False, width=140))
        print(json.dumps({p["phase"]: (p["candidate"].get("gate_outcome"), p["candidate"].get("pass_ratio")) for p in doc["phases"]}))
        return 0
    if a.cmd == "set":
        spec = yaml.safe_load(a.spec.read_text())
        doc = build_set(a.export, a.workorders, spec["phases"], spec["baseline_setup"], spec["candidate_setup"], a.queue)
        a.out.write_text("# Generated by forge_factory.modelservice.qualify set (feature 017, T045) from the per-node export and\n"
                         "# each order's gate log: only runs that succeeded AND whose gate decided PASS are baselines.\n"
                         + yaml.safe_dump(doc, sort_keys=False, width=140))
        print(json.dumps({p["phase"] + " " + p["lineage"]: (p["baseline"].get("order") or "NOT_RUN") for p in doc["phases"]}))
        return 0
    rep = build(yaml.safe_load(a.set.read_text()), a.baseline_export, a.candidate_export, yaml.safe_load(a.mirror.read_text()),
                yaml.safe_load(a.production.read_text()), a.tier_outcomes)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(rep, indent=1))
    (a.out / "report.md").write_text(render_md(rep))
    print(json.dumps({"verdict": rep["verdict"], "rows": len(rep["rows"]), "findings": len(rep["blocking_findings"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
