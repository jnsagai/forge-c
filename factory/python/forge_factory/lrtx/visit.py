"""Shared visit machinery of the local profile's structured authors (feature 010): checkpointed tasks with localized
repair and a visit-wide call budget, role-scoped writes, rework findings since the last visit, and the compact reply
the unchanged author gate reads. Phase-specific task sets live in swe1.py / swe2.py."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..common import pretty_json, utc_now
from ..inspection import outage as O
from . import structured as S

# Admission facts are not malformed model answers. Retrying an identical denied
# request inside its semantic repair loop cannot supply engineering evidence.
# Busy/transport refusals retain their existing bounded retry behavior.
NON_REPAIRABLE_REFUSALS = frozenset("CALL_REFUSED:" + code for code in (
    "JOB_TOKEN_ENVELOPE_EXHAUSTED", "MISSION_TOKEN_CAPACITY_EXHAUSTED", "MISSION_REQUESTS_EXHAUSTED",
    "MISSION_DEADLINE_EXHAUSTED", "REQUEST_NOT_AUTHORIZED", "GENERATION_RETIREMENT_FENCED",
    "EXECUTION_INFERENCE_LEASE_REQUIRED", "REQUEST_START_FENCED", "REQUEST_ORDER_NOT_ACTIVE",
    "REQUEST_AUTHORITY_CHANGED_BEFORE_PROVIDER_SEND",
    "DEVELOPMENT_PHASE_REPAIR_EXHAUSTED",
    # CAPA-191: the factory's own role/trial binding refused the request; repeating it can only be refused again
    "PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED", "PRODUCT_ROLE_TRIAL_CONFIGURATION_CHANGED",
    "PRODUCT_ROLE_TRIAL_BINDING_CHANGED", "PRODUCT_ROLE_TRIAL_ROLES_INVALID", "PRODUCT_ROLE_TRIAL_CHANGED",
    "PRODUCT_ROLE_TRIAL_REFERENCE_INVALID", "PRODUCT_ROLE_TRIAL_CONTEXT_NOT_ALLOCATED",
    "PRODUCT_ROLE_TRIAL_CONTEXT_ALLOCATION_UNBOUND", "PRODUCT_ROLE_TRIAL_NOT_OWNER_SIGNED",
))

def _ckpt(ws: Path, phase: str, task: str) -> Path:
    return Path(ws) / ".forge-run/lrtx" / phase / "packets" / (task.replace(":", "__") + ".json")


def author_call_limit(ws: Path, phase: str, default: int, explicit: int | None = None) -> int:
    """A pinned profile may size this existing visit for more coherent obligations.

    The request/job/mission admission limits still apply independently. This does
    not change the role registry, individual context, inference slots or retries.
    """
    manifest = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    selected = manifest.get("local_profile") or {}
    limits = {}
    if selected.get("id"):
        from .profile import load

        limits = (load(selected["id"]).get("structured") or {}).get("author_max_calls_by_phase") or {}
    if (not isinstance(limits, dict) or any(k not in {f"SWE.{n}" for n in range(1, 7)}
            or type(v) is not int or not 1 <= v <= 4096 for k, v in limits.items())):
        raise ValueError("PROFILE_AUTHOR_CALL_LIMIT_INVALID")
    value = explicit if explicit is not None else limits.get(phase, default)
    if type(value) is not int or not 1 <= value <= 4096:
        raise ValueError("PROFILE_AUTHOR_CALL_LIMIT_INVALID")
    return value


class Continue(Exception):  # noqa: N818 - control flow: the visit's time box is used up, resume in a new node
    """Fabro 0.362 ends a command node with no activity for 1800 s (probes 2026-10-21; stdout does not count). A visit
    therefore stops before a model call that could cross its time box and continues in the next node execution."""


def open_visit(ws: Path, phase: str, resume: bool, findings_fn, max_calls: int, time_budget_s: float | None) -> tuple[
        dict, list[str]]:
    """The visit's shared budget (LRTX-FR-014). A resumed node execution continues the same visit: same call count,
    same rework findings; a new visit starts from the findings addressed to the phase since the last finished visit."""
    sp = Path(ws) / ".forge-run/lrtx" / phase / "visit-state.json"
    st = json.loads(sp.read_text()) if sp.is_file() else None
    if not (resume and st and st.get("open")):
        # a visit that ended FAILED before anything could be assembled leaves no gate finding of its own (the presence
        # gate rejects first): its issues are carried into the next visit so that it repairs instead of repeating
        log = Path(ws) / ".forge-run/lrtx" / phase / "visits.jsonl"
        done = [json.loads(x) for x in (log.read_text().splitlines() if log.is_file() else []) if x.strip()]
        done = [d for d in done if d.get("status") != "CONTINUE" and not d.get("infra_outcome")]  # CAPA-122
        carried = list(done[-1].get("issues") or []) if done and done[-1].get("status") == "FAILED" else []
        st = {"open": True, "started_at": utc_now(), "calls": 0, "continuations": 0,
              "findings": list(dict.fromkeys(findings_fn() + carried))}
    else:
        st["continuations"] = st.get("continuations", 0) + 1
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(pretty_json(st))
    budget = {"calls": st["calls"], "max_calls": max_calls, "state": str(sp),
              "outage_waits": st.get("outage_waits", 0), "outage_waited_s": st.get("outage_waited_s", 0.0),
              "deadline": time.monotonic() + time_budget_s if time_budget_s else None,
              # CAPA-108: which visit and which of its node executions a rework answer was made in
              "visit": st["started_at"], "execution": st.get("continuations", 0)}
    return budget, st["findings"]


def _save_calls(budget: dict) -> None:
    if budget.get("state"):
        sp = Path(budget["state"])
        st = json.loads(sp.read_text())
        st["calls"] = budget["calls"]
        if budget.get("outage_waits"):  # CAPA-122: the outage wait stays bounded across the visit's node executions
            st.update(outage_waits=budget["outage_waits"], outage_waited_s=round(budget.get("outage_waited_s", 0.0), 1))
        sp.write_text(pretty_json(st))


def close_visit(budget: dict | None) -> None:
    if budget and budget.get("state") and Path(budget["state"]).is_file():
        sp = Path(budget["state"])
        st = json.loads(sp.read_text())
        st.update(open=False, closed_at=utc_now(), calls=budget["calls"])
        sp.write_text(pretty_json(st))


def last_finished(ws: Path, phase: str, log: str = "visits.jsonl") -> str:
    """Time of the last visit that ended (CONTINUE records are part of an open visit). CAPA-122: a visit ended by a
    model-call outage was no attempt; the next visit answers the findings the outage visit could not."""
    p = Path(ws) / ".forge-run/lrtx" / phase / log
    done = [json.loads(x) for x in (p.read_text().splitlines() if p.is_file() else []) if x.strip()]
    done = [d for d in done if d.get("status") != "CONTINUE" and not d.get("infra_outcome")]
    return done[-1]["at"] if done else ""


def inherited_task(ws: Path, phase: str, task: str, base: dict, check) -> dict | None:
    """Reuse a validated author task, never an incomplete phase's PASS or inspector.

    The existing resume lineage supplies the sole source workspace. Full packet
    identity, current output schema and current task validator must all match.
    Old attempts/usage remain in their own evidence and the shared mission ledger;
    importing one output neither creates model usage nor grants a phase verdict.
    """
    if base.get("role") != f"swe{phase[-1]}-author":
        return None
    from ..brownfield.resume import source_workspace
    from ..common import sha256_bytes, sha256_file, state_dir

    manifest = Path(ws) / ".forge-run/manifest.json"
    metadata = json.loads(manifest.read_text()) if manifest.is_file() else {}
    lineage = metadata.get("resumed_from")
    fresh = metadata.get("fresh_recovery_from") or {}
    source = (lineage or {}).get("source_work_order")
    fresh_bound = None
    if not source and fresh.get("revalidate_author_tasks") is True:
        source, fresh_bound = fresh.get("work_order"), fresh.get("source_manifest_sha256")
        if not isinstance(fresh_bound, str) or len(fresh_bound) != 64:
            return None
    if not source:
        return None
    try:
        parent = source_workspace(source)
        candidate = _ckpt(parent, phase, task)
        if parent.resolve() == Path(ws).resolve() or not candidate.is_file():
            return None
        root = state_dir() / "workorders"
        if (not parent.resolve().is_relative_to(root.resolve()) or not candidate.resolve().is_relative_to(parent.resolve())
                or any(p.is_symlink() for p in [candidate, *candidate.parents] if p == root or root in p.parents)):
            return None
        if fresh_bound and sha256_file(parent / ".forge-run/manifest.json") != fresh_bound:
            return None
        raw = candidate.read_bytes()
        old = json.loads(raw)
        if (old.get("task") != task or old.get("status") != "VALID" or old.get("base_hash") != base["input_hash"]
                or S.validate(old.get("doc"), base["output_schema"]) or check(old["doc"])):
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None  # Unusable old evidence is not authority to skip the current task.
    return {**old, "inherited_from": {"source_work_order": source,
                                      "record_path": str(candidate.relative_to(parent)),
                                      "record_sha256": sha256_bytes(raw), "validated_at": utc_now()}}


def _rework_mark(budget: dict, findings: list[str] | None) -> dict | None:
    """The identity of a rework answer: its visit, node execution and the exact findings it answered (CAPA-108)."""
    if not findings or not budget.get("visit"):
        return None
    from ..common import canonical_json, sha256_bytes

    return {"visit": budget["visit"], "execution": budget.get("execution", 0),
            "findings_sha256": sha256_bytes(canonical_json(list(findings)))}


def _answered(old: dict | None, mark: dict) -> bool:
    """The checkpoint answered these findings in an EARLIER node execution of this visit. Within one node execution a
    repeated call with the same findings (a joint-check round) still re-runs the task as before."""
    return (isinstance(old, dict) and old.get("visit") == mark["visit"]
            and old.get("findings_sha256") == mark["findings_sha256"]
            and isinstance(old.get("execution"), int) and old["execution"] < mark["execution"])


def _outage_wait(budget: dict, task: str) -> bool:
    """CAPA-122: sleep the next step of the visit's bounded outage schedule (inspection.outage.wait_steps) and return
    True to retry; False when the schedule (or the node's time box) is used up. One progress line per step keeps
    Fabro's inactivity watchdog quiet."""
    steps = O.wait_steps()
    i = budget.get("outage_waits", 0)
    if i >= len(steps):
        return False
    step = steps[i]
    if budget.get("deadline"):
        step = min(step, budget["deadline"] - time.monotonic() - 5)
        if step <= 0:
            return False
    budget["outage_waits"] = i + 1
    budget["outage_waited_s"] = budget.get("outage_waited_s", 0.0) + step
    _save_calls(budget)
    print(json.dumps({"lrtx_progress": task, "outage_wait_s": round(step, 1), "wait": i + 1, "of": len(steps)}),
          flush=True)
    time.sleep(step)
    return True


def _outage_rec(task: str, prev: dict | None, base: dict, attempts: list, budget: dict, doc=None) -> dict:
    """The task result of a visit whose model calls were refused: INVALID with the infrastructure issue, the existing
    checkpoint (a valid answer or the answer under repair) left exactly as it was."""
    keep = doc if doc is not None else (prev or {}).get("doc")
    return {"task": task, "status": "INVALID", "doc": keep,
            "errors": [O.outage_error(str(budget["outage"]), budget.get("outage_waited_s", 0.0))],
            "base_hash": base["input_hash"], "attempts": attempts, "at": utc_now(), "reused": False,
            "outage": str(budget["outage"])[:160]}


def run_task(ws: Path, phase: str, task: str, build, check, budget: dict, findings: list[str] | None = None,
             max_repairs: int = 2) -> dict:
    """Build -> call -> validate -> localized repair, with checkpoint reuse. `build(findings, previous)` returns the
    packet; `check(doc)` returns findings. Every call is counted in `budget` (shared by the whole visit, LRTX-FR-014).
    A VALID checkpoint is reused while the task's base inputs (packet without findings) are unchanged; findings start
    a localized repair of the checkpointed answer instead of a fresh authorship (LRTX-FR-013)."""
    ck = _ckpt(ws, phase, task)
    prev = json.loads(ck.read_text()) if ck.is_file() else None
    base = build(None, None)
    if budget.get("outage"):  # CAPA-122: the visit's model calls are refused; no further call, checkpoint untouched
        return _outage_rec(task, prev, base, [], budget)
    # author tasks only: an inspector's repeated round keeps its existing behaviour (inspection independence)
    author = str(base.get("role", "")).endswith("-author")
    mark = _rework_mark(budget, findings) if author else None
    keep = (budget.get("keep_fixed") or {}).get(task) if author else None
    plain = build

    def build(fi, pr):  # noqa: F811 - a repair packet (findings given) also carries the task's keep-fixed memory
        if not keep or not fi:
            return plain(fi, pr)
        token = S.KEEP_FIXED.set(keep)
        try:
            return plain(fi, pr)
        finally:
            S.KEEP_FIXED.reset(token)
    if (mark and prev and prev.get("status") == "VALID" and prev.get("base_hash") == base["input_hash"]
            and _answered(prev.get("rework"), mark)):
        # CAPA-108 (run WO-F014-CMP-SWE1-RCC-20261102-03): every resumed node execution of a rework visit re-sent the
        # visit's findings to tasks that had already answered them in an earlier node execution; the visit restarted
        # at its first task after each time box and never reached the rest. An answer to the same findings, on the
        # same inputs, in the same visit, is that task's rework result: reuse it like an unchanged task.
        errors = S.validate(prev.get("doc"), base["output_schema"]) or check(prev["doc"])
        if not errors:
            return {**prev, "reused": True}
    if prev is None and not findings:
        prev = inherited_task(ws, phase, task, base, check)
        if prev is not None:
            ck.parent.mkdir(parents=True, exist_ok=True)
            ck.write_text(pretty_json(prev))
    if prev and not findings and prev.get("base_hash") == base["input_hash"] and prev.get("status") == "VALID":
        errors = S.validate(prev.get("doc"), base["output_schema"]) or check(prev["doc"])
        if not errors:
            return {**prev, "reused": True}
        prev = {**prev, "status": "INVALID", "errors": errors}
    if prev and not findings and prev.get("base_hash") == base["input_hash"] and prev.get("doc") is not None:
        findings = prev.get("errors") or None  # an INVALID checkpoint on unchanged inputs: repair it, not restart
    start = prev["doc"] if (prev and findings and prev.get("doc") is not None) else None
    p = build(findings, start) if start is not None else base
    attempts, doc, errs = [], start, list(findings or [])
    limit = max_repairs + 1
    n = -1
    seen_outage = None
    while n + 1 < limit:
        n += 1
        if budget["calls"] >= budget["max_calls"]:
            errs = (errs or []) + ["VISIT_CALL_BUDGET_EXHAUSTED"]
            break
        if budget.get("deadline") and time.monotonic() > budget["deadline"]:
            if attempts:  # keep the progress of this task: the next node execution repairs from here
                ck.parent.mkdir(parents=True, exist_ok=True)
                ck.write_text(pretty_json({"task": task, "status": "INVALID", "doc": doc if doc is not None else
                                           start, "errors": errs, "base_hash": base["input_hash"],
                                           "attempts": attempts, "at": utc_now(), "reused": False}))
            raise Continue(task)
        budget["calls"] += 1
        if "schema_mode" not in budget:  # LRTX-T012: the probed mode of the served model, recorded once per visit
            # G3/D10: the digest the packet identity was hashed with, not the FORGE_LRTX_PROFILE default
            digest = (p.get("identity") or {}).get("model_digest")
            budget["schema_mode"], budget["schema_mode_basis"] = (
                S.schema_mode_for(p["model"], digest) if digest else S.schema_mode_for(p["model"]))
        from ..brownfield.resume import remaining_seconds

        remaining = remaining_seconds(ws)
        r = S.call(p, schema_mode=budget["schema_mode"], **({"timeout": min(3600, remaining)} if remaining else {}))
        code = O.call_outage(r["errors"]) if r["doc"] is None else None
        final = code is None and seen_outage is not None and r["doc"] is None and \
            any(e in NON_REPAIRABLE_REFUSALS for e in r["errors"])
        if final:  # the task's admission allowance went to refused calls: the outcome is still the outage
            code = f"{seen_outage} then {r['errors'][0]}"
        if code is not None:
            # CAPA-122: a refused/unreachable call is no answer and no repair attempt. Wait (bounded, visit-wide) and
            # retry the same packet; when the wait is used up the visit ends on the infrastructure outcome.
            budget["calls"] -= 1
            seen_outage = seen_outage or code
            budget.setdefault("outage_log", []).append({"task": task, "error": code[:160], "at": utc_now()})
            if not final and _outage_wait(budget, task):
                n -= 1
                continue
            budget["outage"] = code
            _save_calls(budget)
            return _outage_rec(task, prev, base, attempts, budget, doc)
        errs = r["errors"] or check(r["doc"])
        if not errs and start is not None and findings and r["doc"] == start:
            # lrtxq1 (2026-10-21): an unchanged answer to the findings re-froze the inspected baseline and spent two
            # rework cycles in seconds; the answer must address them or record why one does not apply
            errs = ["LRTX_FINDING_NOT_ADDRESSED: the answer is identical to the one these findings rejected - change "
                    "the requirements so they address the findings, or, if a finding does not apply, state why in "
                    "open_points (it is rendered into the requirements document for the inspector)"]
        attempts.append({"n": n, "input_hash": p["input_hash"], "accounting": p["accounting"], "usage": r["usage"],
                         "wall_ms": r["wall_ms"], "finish_reason": r["finish_reason"], "errors": errs[:20],
                         "schema_mode": budget["schema_mode"], "schema_mode_basis": budget.get("schema_mode_basis")})
        rejected = r["doc"].get("findings") if errs and isinstance(r["doc"], dict) else None
        if p.get("role", "").endswith("-inspector") and isinstance(rejected, list) and rejected:
            # CAPA-076 (owner option A): a rejected inspector answer's findings stay auditable, so a repair that
            # drops them is visible (lrtx.review reports them as withdrawn_in_repair)
            attempts[-1]["rejected_findings"] = [str(f)[:600] for f in rejected[:10]]
        budget.setdefault("log", []).append({"task": task, **attempts[-1]})
        _save_calls(budget)
        # one line per model call: Fabro's stall watchdog ends a command node that shows no activity for 1800 s
        print(json.dumps({"lrtx_progress": task, "attempt": n, "errors": len(errs), "wall_ms": r["wall_ms"]}),
              flush=True)
        if r["doc"] is not None and not r["errors"]:
            doc = r["doc"]
        if not errs:
            break
        if any(error in NON_REPAIRABLE_REFUSALS for error in errs):
            break
        before = attempts[-2]["errors"] if len(attempts) > 1 else (list(findings or [])[:20] if start is not None else None)
        # only a parsed AUTHOR answer can be stuck (schema or check findings): a call that returned no answer
        # (technical failure, refusal) is retried by design, and an inspector keeping its finding is recorded as
        # contested (lrtx8)
        judged = r["doc"] is not None and p.get("role", "").endswith("-author")
        if judged and before is not None and sorted(errs[:20]) == sorted(before[:20]):
            # CAPA-084 (runs -06/-08): a repair that answers with exactly the findings it was given is stuck; more
            # calls repeated the same finding up to ten times. Stop and report it instead of spending the budget.
            errs = errs + ["LRTX_REPAIR_STUCK: the repair answer has the same findings as the answer it repaired"]
            attempts[-1]["errors"] = errs[:20]
            break
        # bounded extension (at most 2 extra repairs, inside the visit's shared budget) while the answer improves
        if n + 1 == limit and limit < max_repairs + 3 and len(attempts) > 1 and \
                len(attempts[-1]["errors"]) < len(attempts[-2]["errors"]):
            limit += 1
        p = build(errs[:12], r["doc"]) if r["doc"] is not None and not r["errors"] else p
    rec = {"task": task, "status": "VALID" if doc is not None and not errs else "INVALID", "doc": doc,
           "errors": errs, "base_hash": base["input_hash"], "attempts": attempts, "at": utc_now(), "reused": False}
    if mark and rec["status"] == "VALID":
        rec["rework"] = mark
    earlier = ((prev or {}).get("history") or []) + ((prev or {}).get("attempts") or []) if findings else []
    if earlier:  # CAPA-079: a repair round keeps the earlier rounds' attempts (errors, usage), bounded
        rec["history"] = earlier[-12:]
    ck.parent.mkdir(parents=True, exist_ok=True)
    ck.write_text(pretty_json(rec))
    return rec


def write_scoped(ws: Path, files: dict[str, str], node: str) -> None:
    """Every write is decided by the same role authorization the Fabro policy hook applies to the author node.

    CAPA-075: the decision is made against the workspace being WRITTEN. A workspace copy (lrtx/modelcmp, lrtx/seeded,
    lrtx/campaign) keeps the source's binding.json, whose absolute `workspace` would otherwise make the Authorizer
    read and update the source's development-phase state. Node roles and phases still come from the binding."""
    from ..policy.authz import Authorizer, Binding

    bound = Binding.load(Path(ws) / ".forge-run/binding.json")
    auth = Authorizer(Binding(bound.binding_id, str(Path(ws)), bound.nodes))
    for rel, text in files.items():
        d = auth.decide(node, "write_file", {"path": rel, "content": ""})
        if not d.allow:
            raise PermissionError(f"LRTX_WRITE_REFUSED:{rel}:{d.code}")
        p = Path(ws) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def requirement_quote(ws: Path, swr_ids: list[str], fallback: str = "") -> str:
    """CAPA-099 (run WO-F014-SWE6-OBL-20261101-L5): the verbatim text of the first cited requirement, for a CODE/TEST
    declaration (defects.report demands a verbatim quote; the model's own reason was refused)."""
    from ..assurance.register_contract import _requirements

    reqs = _requirements(ws)
    return next((reqs[s].strip()[:300] for s in swr_ids if reqs.get(s, "").strip()), fallback[:300])


NOTES = ("defect filed:", "time box used")


def routable(findings: list[str]) -> list[str]:
    """CAPA-102 (run WO-F014-SWE5-IWDG-20261101-L5): a visit's status notes ('defect filed: DEF-001', 'time box
    used ...') name no file or test; routed as findings they reached every test task, and a passing target file was
    rewritten for ~10 min per call. They are not repair findings."""
    return [f for f in findings if not str(f).startswith(NOTES)]


def offset_index_errors(code: str, block: str, pfx: str) -> list[str]:
    """CAPA-103 (run WO-F014-SWE5-IWDG-20261101-L5): the integration test indexed the register block by the byte
    offset (ll_iwdg_regs[LL_IWDG_PR_OFFSET]); it failed on correct code and the triage filed a wrong CODE defect."""
    from ..brownfield.scope import strip_comments

    return [f"{block}[{m}] indexes the register block by a byte offset: use {block}[{m} / 4U]"
            for m in sorted(set(re.findall(rf"\b{re.escape(block)}\s*\[\s*(LL_{re.escape(pfx)}_\w+_OFFSET)\s*\]",
                                           strip_comments(code))))]


def rework_findings(ws: Path, phase: str, since: str) -> list[str]:
    """Findings addressed to the phase since the last visit: author-gate rejections, failed inspection items and the
    phase's defects in fix. Text only; mapping to tasks happens through the SWR ids they name."""
    ws = Path(ws)
    out: list[str] = []
    log = ws / ".forge-run/gates/gate-log.jsonl"
    for line in log.read_text().splitlines() if log.is_file() else []:
        d = json.loads(line)
        if d.get("phase") == phase and d.get("ts", "") > since and d.get("result") in ("REJECTED", "FAIL", "REWORK"):
            out += [full_issue(ws, phase, str(i)).removeprefix("LRTX_TASK_INVALID:") for i in d.get("issues") or []]
    ins = sorted((ws / "inspection" / phase).glob("INS-*.json")) if (ws / "inspection" / phase).is_dir() else []
    if ins:
        d = json.loads(ins[-1].read_text())
        if d.get("recorded_at", "") > since and d.get("verdict") != "PASS":
            # Published item findings are the repair evidence; detail is a compact display summary.
            # Old inspections and separately supplied findings retain their legacy summary fallback.
            items = d.get("items") or {}
            for finding in d.get("findings") or []:
                item = items.get(finding.get("id"))
                full = item.get("findings") if isinstance(item, dict) and item.get("verdict") == "FAIL" else None
                if isinstance(full, list) and full and all(isinstance(text, str) for text in full):
                    out += [f"{finding.get('id')}: {text}" for text in full]
                else:
                    out.append(f"{finding.get('id')}: {finding.get('detail', '')}")
            if d.get("stale_reason"):
                out.append(f"inspection stale: {d['stale_reason']}")
    for p in sorted((ws / ".forge-run/defects").glob("DEF-*.json")) if (ws / ".forge-run/defects").is_dir() else []:
        d = json.loads(p.read_text())
        if d.get("target_phase") == phase and d.get("status") == "IN_FIX":
            out.append(f"defect {d.get('id')} ({', '.join(d.get('requirement_ids') or [])}): {d.get('summary', '')} "
                       f"{d.get('requirement_quote', '')}".strip())
    return out


KEEP_FIXED_MAX = 20  # per task and repair packet: the most recent are kept, older ones are counted as omitted


def keep_fixed_findings(ws: Path, phase: str) -> list[str]:
    """Owner change 2026-11-02 (run WO-F014-CMP-SWE2-IWDG-20261102-03 and the other cloud-line rework loops): a whole-
    document repair answer can reintroduce what an earlier round fixed. The findings of EARLIER inspection rounds of
    this phase in this run that the latest inspection no longer raises (no latest finding on any item is
    finding_identity.related: same finding, or the same defect wording on other ids), each once in its most recent
    wording, oldest first, '<item>: <full text>'. Author-side memory only: inspector
    packets never receive it (inspection independence)."""
    from ..inspection.engine import Store
    from ..inspection.finding_identity import item_findings, related, same_finding

    st = Store(Path(ws))
    rows = [r for r in st.inspections(phase) if str(r.get("recorded_at") or "") >= st.run_started()]
    if len(rows) < 2:
        return []

    def failed(rec: dict) -> list[tuple[str, str]]:
        if rec.get("verdict") == "PASS":
            return []
        return [(k, t) for k, v in sorted((rec.get("items") or {}).items()) if (v or {}).get("verdict") == "FAIL"
                and not (v or {}).get("not_examined")  # CAPA-123: no product finding to keep fixed
                for t in item_findings(rec, k) if str(t).strip()]

    raised = [t for _k, t in failed(rows[-1])]
    rounds: list[list[tuple[str, str]]] = []  # newest round first; each round in its record order
    for rec in reversed(rows[:-1]):
        seen = [t for r in rounds for _i, t in r]
        rounds.append([])
        for item, text in failed(rec):
            if not any(related(text, r) for r in raised) and not any(
                    same_finding(text, k) for k in seen + [t for _i, t in rounds[-1]]):
                rounds[-1].append((item, text))
    return [f"{item}: {text}" for r in reversed(rounds) for item, text in r]


def attach_keep_fixed(ws: Path, phase: str, budget: dict, route) -> dict[str, dict]:
    """Route the keep-fixed findings with the phase's own rework routing (`route`: findings -> {task: findings}), so each
    reaches the tasks that own it; at most KEEP_FIXED_MAX per task (most recent, the rest counted, never cut). The
    visit's run_task gives them to a task's repair packet; recorded in <phase>/keep-fixed.json."""
    keep = keep_fixed_findings(ws, phase)
    routed = route(keep) if keep else {}
    out = {t: {"findings": fs[-KEEP_FIXED_MAX:], "omitted": max(0, len(fs) - KEEP_FIXED_MAX)}
           for t, fs in routed.items()}
    budget["keep_fixed"] = out
    if keep:
        S.record(ws, f"{phase}/keep-fixed.json", {
            "schema": "forge-c/lrtx-keep-fixed/1", "at": utc_now(), "findings": keep,
            "tasks": {t: {"count": len(v["findings"]), "omitted_by_count": v["omitted"]} for t, v in sorted(out.items())}})
    return out


NOT_AUTHORED = frozenset({"budgets"})  # deterministic work-order rows: no author task can re-author them
_SWR = r"SWR-\d{3,}"
_SWR_RANGE = re.compile(rf"\b({_SWR})\s*(?:\u2013|\u2014|-|\.\.|to|through)\s*(?:SWR-)?(\d{{3,}})\b")
_FIELD_MIN = 4  # a bare field name shorter than this is too likely ordinary text; REG.FIELD is always attributed


def _named_swrs(f: str) -> list[str]:
    """SWR ids a finding names, ranges ('SWR-001-SWR-010', 'SWR-001 to SWR-010') expanded (CAPA-108)."""
    out = re.findall(rf"\b{_SWR}\b", f)
    for m in _SWR_RANGE.finditer(f):
        lo, hi = int(m.group(1)[4:]), int(m.group(2))
        if lo < hi <= lo + 999:
            out += [f"SWR-{n:03d}" for n in range(lo, hi + 1)]
    return list(dict.fromkeys(out))


def _named_tasks(f: str, tasks: dict) -> tuple[set[str], list[str]]:
    """Register tasks a finding names by register, register field or RM section (CAPA-108). Named fields narrow a
    register or section to the split tasks that own them; a register or section alone reaches all of its tasks."""
    found, basis = set(), []
    for reg in sorted({t["register"] for t in tasks.values()}):
        regs = {k for k, t in tasks.items() if t["register"] == reg}
        qualified = set(re.findall(rf"\b{re.escape(reg)}\.([A-Z][A-Z0-9_]*)\b", f))
        bare = {fld for k in regs for fld in tasks[k]["fields"] if len(fld) >= _FIELD_MIN
                and re.search(rf"(?<![A-Za-z0-9_.]){re.escape(fld)}\b", f)}
        owners = {k for k in regs if (qualified | bare) & set(tasks[k]["fields"])}
        section = next(iter({tasks[k]["section"] for k in regs}))
        named = re.search(rf"\b{re.escape(reg)}\b", f) or (
            section.count(".") >= 2 and re.search(rf"(?<![\d.]){re.escape(section)}(?![\d.])", f))
        if owners:
            found |= owners
            basis.append(f"field:{reg}")
        elif named:
            found |= regs
            basis.append(f"register:{reg}")
    return found, basis


def attribute_findings(findings: list[str], amap: dict | None, default: str,
                       tasks: dict[str, dict] | None = None) -> tuple[dict[str, list[str]], list[dict]]:
    """Task -> findings, with one attribution record per finding (CAPA-108).

    A finding reaches the tasks it names: task ids, SWR ids (and ranges) through the assembly map, effect cases,
    open point ids or texts and, with `tasks` ({task: {register, section, fields}}), register/field/section names.
    An open-points mention that names no locatable note reaches the tasks the finding otherwise names. Only a finding
    that names no author task keeps the earlier fan-out (every note origin for an open-points mention, otherwise the
    default task) and is recorded as unattributed; nothing is dropped."""
    out: dict[str, list[str]] = {}
    report: list[dict] = []
    for f in findings:
        text, basis = f, []
        named = set(re.findall(r"\b(requirements:[A-Za-z0-9_]+)", f))  # a visit's own findings name their task
        if named:
            basis.append("task")
        for swr in _named_swrs(f):
            if amap and swr in amap["swr"]:
                t = amap["swr"][swr]
                named.add(t["task"])
                basis.append(f"swr:{swr}")
                text = re.sub(rf"\b{swr}\b(?! \[)", f"{swr} [{t['key']}]", text)
        for case, swr in (amap or {}).get("case", {}).items():
            if re.search(rf"\b{re.escape(case)}\b", f) and swr in (amap or {}).get("swr", {}):
                named.add(amap["swr"][swr]["task"])
                basis.append(f"case:{case}")
        points = (amap or {}).get("open_points") or {}
        mentions_points = re.search(r"\bopen[\s_-]+points?\b", f, re.I)
        owners = set()
        for ident, origin in points.items():
            register = origin.get("register")
            if (ident in f or origin.get("text") and origin["text"] in f
                    or mentions_points and register and re.search(rf"\b{re.escape(register)}\b", f)):
                owners.add(origin["task"])
                basis.append(f"open_point:{ident}")
        named |= owners
        if tasks:
            regs, why = _named_tasks(f, tasks)
            named |= regs
            basis += why
        authored = named - NOT_AUTHORED
        fallback = None
        if not authored:
            # unattributable: keep the earlier route (never drop a finding) and say so
            if mentions_points and points:
                authored, fallback = {o["task"] for o in points.values()} - NOT_AUTHORED, "open_point_origins"
            authored, fallback = (authored, fallback) if authored else ({default}, "default")
        for t in sorted(authored):
            out.setdefault(t, []).append(text)
        report.append({"finding": f[:300], "tasks": sorted(authored), "basis": list(dict.fromkeys(basis)),
                       "unattributed": fallback is not None, **({"fallback": fallback} if fallback else {}),
                       **({"open_points_unlocated": True} if mentions_points and not owners else {})})
    return out, report


def route_findings(findings: list[str], amap: dict | None, default: str,
                   tasks: dict[str, dict] | None = None) -> dict[str, list[str]]:
    """Task -> findings (see attribute_findings)."""
    return attribute_findings(findings, amap, default, tasks)[0]


ISSUE_MAX = 120  # specs/002-self-healing-factory/contracts/agent-output.schema.json issues[].maxLength (protected)


def full_issue(ws: Path, phase: str, issue: str) -> str:
    """The full text of a reply issue the agent-output contract bounded to ISSUE_MAX characters (CAPA-098)."""
    p = Path(ws) / ".forge-run/lrtx" / phase / "reply-issues.json"
    try:
        full = json.loads(p.read_text()).get("issues") or [] if p.is_file() else []
    except ValueError:
        full = []
    if len(issue) < ISSUE_MAX:
        return issue
    return next((f for f in full if f[:ISSUE_MAX] == issue[:ISSUE_MAX]), issue)


def reply(ws: Path, phase: str, status: str, issues: list[str], budget: dict | None = None,
          artifacts: list[str] | None = None) -> dict:
    """The compact author reply the unchanged author gate reads (agent-output contract), plus the visit record."""
    # CAPA-098 (runs WO-F014-SWE2-IWDG-20261101-01, WO-F014-SWE4-IWDG-20261101-L1): issues were cut to 300 characters,
    # beyond the protected agent-output contract (120), so every long rejection also failed AGENT_OUTPUT_SCHEMA and the
    # gate kept 120-character fragments. The reply keeps the contract; the full text is a side record rework reads.
    doc = {"status": status, "artifacts": artifacts or [], "issues": [i[:ISSUE_MAX] for i in issues[:20]],
           "next_action": "next" if status == "PASS" else "rework"}
    S.record(ws, f"{phase}/reply.json", doc)
    S.record(ws, f"{phase}/reply-issues.json", {"issues": [i[:2000] for i in issues[:20]]})
    if status != "CONTINUE":
        close_visit(budget)
    calls = (budget or {}).get("log", [])
    visit_rec = {"at": utc_now(), "status": status, "calls": (budget or {}).get("calls", 0),
                 "max_calls": (budget or {}).get("max_calls"), "issues": doc["issues"][:10],
                 "prompt_tokens": [((c.get("usage") or {}).get("prompt_tokens"), c["accounting"]["estimated_prompt_tokens"])
                                   for c in calls]}
    if status == "FAILED" and (budget or {}).get("outage"):  # CAPA-122: the visit ended on a model-call outage
        visit_rec.update(infra_outcome=O.CODE, outage=str(budget["outage"])[:160],
                         outage_waited_s=round(budget.get("outage_waited_s", 0.0), 1),
                         outage_log=(budget.get("outage_log") or [])[-10:])
    p = Path(ws) / ".forge-run/lrtx" / phase / "visits.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(visit_rec, sort_keys=True) + "\n")
    return doc
