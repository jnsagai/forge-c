"""LRTX-T019 (LRTX-FR-015): independent structured inspection for the local profile.

One packet per required judgment item of the phase checklist, each with the item's full criterion text, the inspector
notes the agent prompt already carries, and the primary evidence: the files of the frozen baseline (never the author's
packets, checkpoints or answers). Each verdict is checkpointed with the baseline hash it judged. Only a complete set of
verdicts for the CURRENT baseline is aggregated, and it is recorded through the unchanged `check_inspection` operation
(same refusal of missing verdicts, same record, same gate). Deterministic items are recomputed by the engine as always.
Same-family models in separate contexts do not prove independence of model errors; that remains an open limitation.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import structured as S
from . import visit as V

VERDICT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "findings", "evidence_checked"],
                  "properties": {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                                 "findings": {"type": "array", "items": {"type": "string", "minLength": 10}},
                                 "evidence_checked": {"type": "array", "minItems": 1, "items": {"type": "string"}}}}
MAX_FILE_CHARS = 40_000


def _notes(ws: Path, phase: str, item: str) -> list[str]:
    from ..layer import profile
    from ..workflow import prompts

    out = []
    if phase == "SWE.1" and item == "SWE1-01":
        out.append(prompts.OWNER_SCOPE_NOTE)
    if phase in ("SWE.2", "SWE.3"):  # the work order's peripheral (feature 009), as the builder sets it for agents
        prof = profile(ws)
        saved = prompts.PERIPHERAL["profile"]
        prompts.PERIPHERAL["profile"] = prof if prof["id"] != "rcc" else None
        try:
            out.append(prompts.peripheralize(prompts.REGISTER_BLOCK_NOTE))
        finally:
            prompts.PERIPHERAL["profile"] = saved
    if phase in ("SWE.4", "SWE.5", "SWE.6"):
        out.append(prompts.WORK_ORDER_SCOPE_NOTE)
    return out


def evidence(ws: Path, phase: str) -> tuple[dict, list[dict]]:
    """The newest frozen baseline of the phase and its files (plus the upstream SWE.1 requirements for SWE.2+)."""
    from ..inspection.engine import Store

    st = Store(Path(ws))
    bl = st.latest_baseline(phase)
    if bl is None:
        raise ValueError(f"NO_BASELINE:{phase}")
    files = [f for f in bl["files"] if not f.endswith((".svg", ".reqif"))]
    if phase != "SWE.1":
        files += [f for f in ("workproducts/SWE.1/software_requirements.md", "workproducts/SWE.1/register_effects.json")
                  if f not in files]
    srcs = [S.source(ws, f, max_chars=MAX_FILE_CHARS) for f in files if (Path(ws) / f).is_file()]
    m = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    ctx = json.dumps({"work_order": m["work_order"], "layer": m.get("layer"), "scope": m["scope"], "target": m["target"],
                      "budgets": m["budgets"], "upstream": m.get("upstream")}, indent=1)
    srcs.append({"path": ".forge-run/manifest.json#scope-target-budgets", "text": ctx,
                 "sha256": sha256_bytes(ctx.encode())})
    return bl, srcs


def item_packet(ws: Path, phase: str, item: dict, bl: dict, srcs: list[dict], model: str, findings=None,
                previous=None) -> dict:
    instr = (f"Inspect checklist item {item['id']} of {phase} on the frozen baseline {bl['baseline_id']} (hash "
             f"{bl['baseline_hash'][:16]}). Criterion (full text): {' '.join(str(item['criterion']).split())} "
             "Judge ONLY this criterion, ONLY from the SOURCES below (the frozen work products and the work-order "
             "context). verdict PASS only when the evidence satisfies the whole criterion; otherwise FAIL with one "
             "concrete finding per problem that names the requirement, section or file it concerns. Do not judge other "
             "criteria. evidence_checked lists the source paths you used. " + " ".join(_notes(ws, phase, item["id"])))
    return S.packet(phase=phase, task=f"inspect:{item['id']}", role=f"swe{phase[-1]}-inspector", instructions=instr,
                    sources=srcs, criteria=[f"{item['id']}: {' '.join(str(item['criterion']).split())}"],
                    output_schema=VERDICT_SCHEMA, model=model, findings=findings, previous=previous,
                    output_reserve=2048)


def validate_verdict(doc: dict, paths: set[str]) -> list[str]:
    out = []
    if doc["verdict"] == "FAIL" and not doc["findings"]:
        out.append("a FAIL verdict needs at least one concrete finding")
    if doc["verdict"] == "PASS" and doc["findings"]:
        out.append("a PASS verdict carries no findings (use FAIL when a finding exists)")
    out += [f"evidence_checked names {p}, which is not a provided source" for p in doc["evidence_checked"]
            if p not in paths]
    return out


def visit(ws: Path, phase: str, model: str, max_calls: int | None = None) -> dict:
    from ..inspection.engine import Store
    from ..mcp.sdk import ToolContext
    from ..mcp.servers import evidence as EV
    from ..registry.agents import load_agents

    ws = Path(ws)
    role = f"swe{phase[-1]}-inspector"
    st = Store(ws)
    try:
        bl, srcs = evidence(ws, phase)
    except (ValueError, S.PacketRefused) as exc:
        return _reply(ws, phase, "FAILED", [str(exc)])
    items = [c for c in st.applicable(st.checklist(phase))["checks"]
             if c.get("required") and not c.get("deterministic_check")]
    budget = {"calls": 0, "max_calls": max_calls or {a.id: a for a in load_agents()[0]}[role].max_turns,
              "schema_mode": "json_schema"}
    paths = {s["path"] for s in srcs}
    verdicts, issues = {}, []
    for it in items:
        # the checkpoint key binds the verdict to the baseline it judged: a new baseline is a new task
        task = f"inspect:{bl['baseline_hash'][:16]}:{it['id']}"
        rec = V.run_task(ws, phase, task, lambda fi, pr, it=it: item_packet(ws, phase, it, bl, srcs, model, fi, pr),
                         lambda d: validate_verdict(d, paths), budget)
        if rec["status"] != "VALID":
            issues += [f"{it['id']}: {e}" for e in rec["errors"][:3]]
            continue
        d = rec["doc"]
        verdicts[it["id"]] = {"verdict": d["verdict"], "findings": [f[:200] for f in d["findings"]],
                              "evidence_refs": [f"configuration/baselines/{phase}/{bl['baseline_id']}.json",
                                                *d["evidence_checked"][:8]]}
    if issues:  # incomplete: nothing is recorded (an aggregate never invents a verdict)
        return _reply(ws, phase, "FAILED", issues, budget)
    if st.latest_baseline(phase)["baseline_hash"] != bl["baseline_hash"]:
        return _reply(ws, phase, "FAILED", ["BASELINE_CHANGED_DURING_INSPECTION"], budget)
    ctx = ToolContext(server="forge-evidence-mcp", op="check_inspection", role=role, phase=phase, workspace=ws,
                      run_id=json.loads((ws / ".forge-run/manifest.json").read_text())["work_order"])
    res = EV.check_inspection(ctx, EV.InspectIn(phase=phase, baseline_id=bl["baseline_id"], verdicts=verdicts))
    S.record(ws, f"{phase}/inspection-record.json", {"at": utc_now(), "baseline_id": bl["baseline_id"],
                                                     "result": res, "items": sorted(verdicts)})
    status = "PASS" if res["status"] == "PASS" else "REWORK"
    return _reply(ws, phase, status, list(res.get("issues") or []), budget, list(res.get("artifact_refs") or []))


def _reply(ws: Path, phase: str, status: str, issues: list[str], budget: dict | None = None,
           artifacts: list[str] | None = None) -> dict:
    doc = {"status": status, "artifacts": artifacts or [], "issues": [i[:300] for i in issues[:20]],
           "next_action": "next" if status == "PASS" else "rework"}
    S.record(ws, f"{phase}/inspect-reply.json", doc)
    p = Path(ws) / ".forge-run/lrtx" / phase / "inspections.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"at": utc_now(), "status": status, "calls": (budget or {}).get("calls", 0),
                            "issues": doc["issues"][:10]}, sort_keys=True) + "\n")
    return doc
