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
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now
from ..inspection.ears import STARTUP_NO_CALL
from . import structured as S
from . import visit as V

VERDICT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "findings", "evidence_checked"],
                  "properties": {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                                 # lrtx7 (2026-10-21): check_inspection accepts at most 10 findings per item
                                 "findings": {"type": "array", "maxItems": 10,
                                              "items": {"type": "string", "minLength": 10}},
                                 "evidence_checked": {"type": "array", "minItems": 1, "items": {"type": "string"}}}}
MAX_FILE_CHARS = 40_000


def _notes(ws: Path, phase: str, item: str) -> list[str]:
    from ..layer import profile
    from ..workflow import prompts

    out = []
    if phase == "SWE.1":  # the agent inspector reads it once for all items (prompts.inspector_prompt); lrtx9: the
        out.append(prompts.OWNER_SCOPE_NOTE)  # SWE1-05 packets lacked it and failed the recorded gaps
        from .c_language_context import for_workspace

        if note := for_workspace(ws):
            out.append(note)
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


# F011-T036 (owner 2026-10-24, "Reference by hash"): the SafeC engine's machine output in a semantic SWE.1 baseline
# (54 kB obligations, 37 kB oracle: over the per-source limit) reaches the inspector as path, hash and size only;
# the deterministic oracle gate checks both files. Baselines without them (Codex/Claude line) are unchanged.
ENGINE_FILES = ("workproducts/SWE.1/register_obligations.json", "workproducts/SWE.1/register_oracle.json")
ENGINE_NOTE = ("SafeC engine output (register obligations / register oracle), checked by the deterministic oracle gate; "
               "listed by hash only, not inspected text: judge the requirements, effects and traceability")


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
    srcs = [S.source(ws, f, max_chars=MAX_FILE_CHARS) for f in files if (Path(ws) / f).is_file() and f not in ENGINE_FILES]
    for f in [f for f in files if f in ENGINE_FILES and (Path(ws) / f).is_file()]:
        data = (Path(ws) / f).read_bytes()
        note = json.dumps({"path": f, "sha256": sha256_bytes(data), "bytes": len(data), "content": ENGINE_NOTE}, indent=1)
        srcs.append({"path": f"{f}#sha256", "text": note, "sha256": sha256_bytes(note.encode())})
    m = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    ctx = json.dumps({"work_order": m["work_order"], "layer": m.get("layer"), "scope": m["scope"], "target": m["target"],
                      "budgets": m["budgets"], "upstream": m.get("upstream")}, indent=1)
    srcs.append({"path": ".forge-run/manifest.json#scope-target-budgets", "text": ctx,
                 "sha256": sha256_bytes(ctx.encode())})
    from ..inspection.assessment_context import view

    context = view(m)
    if context is not None:
        text = json.dumps(context, sort_keys=True)
        srcs.append({"path": ".forge-run/manifest.json#inspection-assessment-context", "text": text,
                     "sha256": sha256_bytes(text.encode())})
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
                    output_reserve=2048, assessment_workspace=Path(ws))


PENDING_RX = re.compile(r"pending|not (?:yet )?allocated|allocation review|no software safety requirement", re.I)
NO_VERIF_RX = re.compile(r"(?:no|without|missing|lacks?|not)\s+(?:explicit\s+)?(?:objective\s+)?verif|not "
                         r"(?:explicitly )?(?:verified|verifiable|measurable)", re.I)

GAP_RX = re.compile(r"NOT_PROVIDED|not (?:been |yet )?provided|upstream (?:coverage )?gap", re.I)
# ... and only about an upstream input (lrtx9: "depends on an upstream budget that has not been provided"); a missing
# verification criterion or test is never an upstream gap
UPSTREAM_RX = re.compile(r"\bHSI\b|\bbudget|\bupstream\b|interface contract|safety allocation", re.I)
LATER_RX = re.compile(r"no test (?:file|procedure|case|script)|test (?:file|procedure)s? (?:is|are)? ?(?:not )?"
                      r"(?:provided|present|available)|no (?:test )?evidence .{0,80}(?:measured|verified)|not "
                      r"(?:explicitly )?measured", re.I)
# A no-write startup invariant refutes only an explicit denial of startup behaviour.
# Register-reset bits/values/semantics are distinct obligations and must retain their findings.
STARTUP_BEHAVIOUR = r"(?:reset(?:/start-?up)?|start-?up)\s+behaviou?r"
NO_STARTUP_RX = re.compile(r"\b(?:no|not|without|missing|lacks?)\s+(?:[\w,]+\s+){0,4}?" + STARTUP_BEHAVIOUR + r"\b|"
                           r"\b" + STARTUP_BEHAVIOUR + r"\s+(?:is|are)\s+(?:not|missing|absent|unspecified)\b", re.I)


def fact_conflicts(ws: Path, phase: str, item: str, findings: list[str]) -> list[str]:
    """Findings refuted by facts the evidence states (LRTX-FR-015: false rejections are measured and corrected, never
    waived): an owner's PENDING allocation decision or a recorded NOT_PROVIDED upstream gap judged as a failure, a
    missing verification criterion or startup rule that the document has, tests or measurements demanded at SWE.1, an
    SWR id that does not exist. The inspector re-judges; it may keep any finding these do not refute."""
    ws = Path(ws)
    out = []
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    pending = "PENDING owner allocation review" in str(m["target"].get("safety_allocation", ""))
    req = ws / "workproducts/SWE.1/software_requirements.md"
    text = req.read_text() if req.is_file() else ""
    verif = {s: v for s, v in re.findall(r"\*\*(SWR-\d{3})\*\*.*?\n\s*-\s*Source:.*?\n\s*-\s*Verification:\s*(.+)",
                                         text)}
    known = set(re.findall(r"\*\*(SWR-\d{3})\*\*", text))
    gaps_p = ws / "traceability/upstream_gaps.md"
    recorded_gap = gaps_p.is_file() and "NOT_PROVIDED" in gaps_p.read_text()
    startup = re.search(r"\*\*(SWR-\d{3})\*\*\s+(" + STARTUP_NO_CALL + r"[^\n]*)\n", text, re.I)
    for f in findings:
        # lrtx7 (2026-10-21): the Claude inspector passed SWE1-01..06 of rc1 with the same recorded gaps; the Qwen
        # inspector failed them for the gap itself, for later-phase evidence and for a startup rule the document has
        if phase == "SWE.1" and recorded_gap and GAP_RX.search(f) and UPSTREAM_RX.search(f):
            out.append(f"finding '{f[:80]}...' judges an input the owner recorded as NOT_PROVIDED as a failure: the "
                       "document records the gap in traceability/upstream_gaps.md, which is what the factory requires "
                       "for missing upstream inputs - re-judge the item on the other evidence")
        if phase == "SWE.1" and LATER_RX.search(f):
            out.append(f"finding '{f[:80]}...' asks for tests or measurements: those are SWE.4-SWE.6 work products; at "
                       "SWE.1 judge the verification criterion and whether the constraint is measurable")
        if phase == "SWE.1" and startup and startup.group(1) not in f and NO_STARTUP_RX.search(f):
            out.append(f"finding says reset/startup behaviour is not specified, but {startup.group(1)} specifies it: "
                       f"'{startup.group(2)[:100]}' - re-judge the remaining parts of the item")
        if pending and phase == "SWE.1" and PENDING_RX.search(f):
            out.append(f"finding '{f[:80]}...' judges the owner's recorded PENDING allocation decision as a failure: "
                       "per the note it is a gap recorded in traceability/upstream_gaps.md - re-judge the item on the "
                       "other evidence")
        for s in re.findall(r"SWR-\d{3}", f):
            if s not in known and known:
                out.append(f"finding names {s}, which is not a requirement of the document")
            elif s in verif and NO_VERIF_RX.search(f) and "pass" in verif[s].lower():
                out.append(f"finding says {s} lacks verification, but the document gives: '{verif[s][:100]}' - re-judge")
    return list(dict.fromkeys(out))


def _norm_path(p: str) -> str:
    """lrtx4 (2026-10-21): the model echoed the packet's 'SOURCE <path>' labels ('source safety/...',
    'source/safety/...'); a label or anchor around a provided path is not a wrong source."""
    p = re.sub(r"^(?:source|current artifact)[\s/:]+", "", p.strip().strip("`'\""), flags=re.I)
    return p.split("#", 1)[0].strip().lstrip("./")


def validate_verdict(doc: dict, paths: set[str], ws: Path | None = None, phase: str = "", item: str = "") -> list[str]:
    out = []
    if ws is not None and doc["verdict"] == "FAIL":
        out += fact_conflicts(ws, phase, item, doc["findings"])
    if doc["verdict"] == "FAIL" and not doc["findings"]:
        out.append("a FAIL verdict needs at least one concrete finding")
    if doc["verdict"] == "PASS" and doc["findings"]:
        out.append("a PASS verdict carries no findings (use FAIL when a finding exists)")
    out += [f"evidence_checked names {p}, which is not a provided source" for p in doc["evidence_checked"]
            if _norm_path(p) not in {_norm_path(x) for x in paths}]
    return out


def visit(ws: Path, phase: str, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    """One inspection (or its continuation after a time box). Verdicts already judged for this baseline are reused."""
    from ..registry.agents import load_agents

    role = f"swe{phase[-1]}-inspector"
    budget, _f = V.open_visit(Path(ws), phase + "-inspect", resume, list,
                              max_calls or {a.id: a for a in load_agents()[0]}[role].max_turns, time_budget_s)
    try:
        return _visit(Path(ws), phase, model, budget)
    except V.Continue as c:
        return _reply(Path(ws), phase, "CONTINUE", [f"time box used; resumes at {c}"], budget)


def _visit(ws: Path, phase: str, model: str, budget: dict) -> dict:
    from ..inspection.engine import Store
    from . import tools as T

    ws = Path(ws)
    role = f"swe{phase[-1]}-inspector"
    st = Store(ws)
    try:
        bl, srcs = evidence(ws, phase)
    except (ValueError, S.PacketRefused) as exc:
        return _reply(ws, phase, "FAILED", [str(exc)])
    items = [c for c in st.applicable(st.checklist(phase))["checks"]
             if c.get("required") and not c.get("deterministic_check")]
    paths = {s["path"] for s in srcs}
    verdicts, issues, contested = {}, [], {}
    for it in items:
        # the checkpoint key binds the verdict to the baseline it judged: a new baseline is a new task
        task = f"inspect:{bl['baseline_hash'][:16]}:{it['id']}"
        rec = V.run_task(ws, phase, task, lambda fi, pr, it=it: item_packet(ws, phase, it, bl, srcs, model, fi, pr),
                         lambda d, it=it: validate_verdict(d, paths, ws, phase, it["id"]), budget)
        d = rec["doc"]
        if rec["status"] != "VALID":
            # lrtx8 (2026-10-21): an inspector that keeps a finding the evidence refutes after its repairs. The verdict
            # is recorded as given with ALL its findings (LRTX-FR-015: never waived); the refutations are recorded
            # beside it as contested, measured false-rejection candidates. Any other defect leaves the item missing.
            conf = fact_conflicts(ws, phase, it["id"], d["findings"]) if isinstance(d, dict) and \
                isinstance(d.get("findings"), list) else []
            if not (conf and set(rec["errors"]) <= set(conf) and not S.validate(d, VERDICT_SCHEMA)
                    and not validate_verdict(d, paths)):
                issues += [f"{it['id']}: {e}" for e in rec["errors"][:3]]
                continue
            contested[it["id"]] = conf
        verdicts[it["id"]] = {"verdict": d["verdict"], "findings": list(d["findings"]),
                              "evidence_refs": [f"configuration/baselines/{phase}/{bl['baseline_id']}.json",
                                                *d["evidence_checked"][:8]]}
    if issues:  # incomplete: nothing is recorded (an aggregate never invents a verdict)
        return _reply(ws, phase, "FAILED", issues, budget)
    if st.latest_baseline(phase)["baseline_hash"] != bl["baseline_hash"]:
        return _reply(ws, phase, "FAILED", ["BASELINE_CHANGED_DURING_INSPECTION"], budget)
    try:
        res = T.call(ws, "forge-evidence-mcp", "check_inspection",
                     {"phase": phase, "baseline_id": bl["baseline_id"], "verdicts": verdicts}, role, phase)
    except ValueError as exc:  # pydantic ValidationError: a contract mismatch is a factory finding, not a crash
        return _reply(ws, phase, "FAILED", [f"LRTX_INSPECTION_RECORD_REFUSED:{' '.join(str(exc).split())[:240]}"],
                      budget)
    S.record(ws, f"{phase}/inspection-record.json", {"at": utc_now(), "baseline_id": bl["baseline_id"],
                                                     "result": res, "items": sorted(verdicts),
                                                     "contested_findings": contested})
    status = "PASS" if res["status"] == "PASS" else "REWORK"
    notes = [f"LRTX_INSPECTOR_FINDING_CONTESTED:{i}: {c}" for i, cs in contested.items() for c in cs]
    return _reply(ws, phase, status, list(res.get("issues") or []) + notes, budget,
                  list(res.get("artifact_refs") or []))


def _reply(ws: Path, phase: str, status: str, issues: list[str], budget: dict | None = None,
           artifacts: list[str] | None = None) -> dict:
    doc = {"status": status, "artifacts": artifacts or [], "issues": [i[:300] for i in issues[:20]],
           "next_action": "next" if status == "PASS" else "rework"}
    S.record(ws, f"{phase}/inspect-reply.json", doc)
    if status != "CONTINUE":
        V.close_visit(budget)
    p = Path(ws) / ".forge-run/lrtx" / phase / "inspections.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"at": utc_now(), "status": status, "calls": (budget or {}).get("calls", 0),
                            "issues": doc["issues"][:10]}, sort_keys=True) + "\n")
    return doc
