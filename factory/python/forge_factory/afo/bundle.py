"""AFO-T035/T036 (AFO-FR-037/038/039/044/046; AT-026/027/028/033/035/043) - typed FailureBundle from a finished
attempt's authoritative records, and the AFO failure class.

Sources are the deterministic records only (gate log, inspection records, defect register, tool results) as
classified by the 004 CRE importer (`reliability.observe.from_workspace`: failure class, category, stable `cfp1-`
fingerprint). An agent's own "PASS" text is never a verdict. The AFO class adds what CRE's five classes do not:
  * POLICY_SECURITY -> SECURITY;  * a missing authoritative input (HSI, manual, approval) -> SPECIFICATION_GAP;
  * a fingerprint owned by an OPEN/TRIAGED/REOPENED... CAPA (a factory defect under investigation) ->
    FACTORY_CODE_DEFECT - rework would only meet the same defect.
Agent-written text (inspector findings, author replies) enters only as a bounded, secret-redacted excerpt tagged
untrusted (`untrusted_source_refs`): it is data for the planner, never instructions.
F015 (2026-10-25/26): an agent backend that refuses its turns (ACP `prompt_error`, e.g. Codex unavailable at sign-in)
is a TRANSIENT_DEPENDENCY, not product quality: the phase whose latest agent turn errored stopped on unchanged files
(a STUCK route), and a run that failed before any phase BLOCKED gets a bundle at once instead of waiting out the
package deadline (6 h of a one-order queue on 2026-10-25).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..common import sha256_file
from . import contracts

PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")
SPEC_GAP = re.compile(r"MISSING_(AUTHORITATIVE|INPUT)|HSI_(MISSING|CONFLICT)|UPSTREAM_.*NOT_PROVIDED|NOT_APPROVED", re.I)
SECRET = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[:=]\s*\S+|sk-[A-Za-z0-9]{12,}|fabro_dev_[0-9a-f]+")
MAX_SUMMARY = 1500
CAPA_OPEN = {"OPEN", "TRIAGED", "REPRODUCER_PENDING", "CAUSE_VERIFIED", "FIX_CANDIDATE", "PREVENTION_TESTED",
             "REOPENED", "UNRESOLVED"}


def redact(text: str) -> str:
    return SECRET.sub("[REDACTED]", text)


def blocked_phase(ws: Path) -> tuple[str | None, str]:
    """The phase whose route gate BLOCKED (the run stopped there), with the gate's reason."""
    log = ws / ".forge-run/gates/gate-log.jsonl"
    last = None
    for line in log.read_text().splitlines() if log.is_file() else []:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("step") == "route" and (r.get("gate") or {}).get("decision") == "BLOCKED":
            last = r
    return (last["phase"], str(last["gate"].get("reason", ""))) if last else (None, "")


def _node_phase(node: str) -> str | None:
    m = re.match(r"swe(\d)_", node)
    return f"SWE.{m.group(1)}" if m else None


def agent_turns(ws: Path, phase: str | None = None) -> list[dict]:
    """The ACP proxy's turn records (session start, usage, prompt_error) of one phase's agent nodes, oldest first."""
    out = []
    for f in sorted((ws / ".forge-run/acp").glob("*.proxy.jsonl")):
        node = f.name.removesuffix(".proxy.jsonl")
        if phase is not None and _node_phase(node) != phase:
            continue
        for line in f.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("event") in ("session", "usage", "prompt_error"):
                out.append({**r, "node": node})
    return sorted(out, key=lambda r: str(r.get("ts", "")))


def agent_unavailable(ws: Path, phase: str) -> dict | None:
    """The latest prompt_error of `phase` when no agent turn of that phase completed after it."""
    last = None
    for r in agent_turns(ws, phase):
        if r["event"] == "prompt_error":
            last = r
        elif r["event"] == "usage":
            last = None
    return last


def last_phase(ws: Path) -> str:
    log = ws / ".forge-run/gates/gate-log.jsonl"
    ph = "SWE.1"
    for line in log.read_text().splitlines() if log.is_file() else []:
        try:
            ph = json.loads(line).get("phase") or ph
        except ValueError:
            continue
    return ph if ph in PHASES else "UNKNOWN"


def _capa_fingerprints() -> set[str]:
    from ..reliability.capa import CapaRegistry
    from ..reliability.policy import load
    from ..reliability.store import CREStore

    try:
        reg = CapaRegistry(CREStore(), load())
        return {f for c in reg.all() if c["state"] in CAPA_OPEN for f in reg.links(c["capa_id"], "FINGERPRINT")}
    except Exception:  # noqa: BLE001 - an unreadable registry links nothing (the class falls back to CRE's)
        return set()


def afo_class(obs: dict, open_capa: set[str]) -> str:
    if obs["failure_class"] == "POLICY_SECURITY":
        return "SECURITY"
    if SPEC_GAP.search(obs.get("error_code", "")):
        return "SPECIFICATION_GAP"
    if obs["fingerprint"] in open_capa:
        return "FACTORY_CODE_DEFECT"
    return obs["failure_class"] if obs["failure_class"] in ("INFRASTRUCTURE", "TRANSIENT_DEPENDENCY", "PRODUCT_QUALITY") \
        else "UNKNOWN"


def _unavailable_bundle(ws: Path, order_id: str, attempt_id: str, phase: str, err: dict | None, reason: str) -> dict:
    from ..reliability.taxonomy import fingerprint

    cls, code = ("TRANSIENT_DEPENDENCY", "AGENT_BACKEND_UNAVAILABLE") if err else ("INFRASTRUCTURE", "RUN_NOT_COMPLETED")
    node = (err or {}).get("node", "")
    summary = redact(f"route: {reason}; " + (f"{node} prompt_error {err.get('code')}: {err.get('message', '')}"
                                             if err else "Fabro run failed before any phase gate BLOCKED"))
    rec = {"schema_version": "1.0", "order_id": order_id, "attempt_id": attempt_id, "phase": phase,
           "failure_class": cls, "fingerprint": fingerprint(cls, node or "fabro-run", code, f"{phase}/agent_turn"),
           "gate_result": "BLOCKED" if reason else "UNKNOWN", "error_code": code, "artifact_refs": [],
           "evidence_refs": [f"workspace:.forge-run/acp/{node}.proxy.jsonl"] if err else
           ["workspace:.forge-run/gates/gate-log.jsonl"], "input_digests": {}, "requirements_refs": [],
           "redacted_summary": summary[:MAX_SUMMARY], "context_truncated": len(summary) > MAX_SUMMARY,
           "untrusted_source_refs": []}
    rec["bundle_id"] = "afo-fb-" + hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:20]
    contracts.require("failure-bundle", rec)
    return rec


def build(ws: Path, order_id: str, attempt_id: str, *, open_capa: set[str] | None = None,
          run_failed: bool = False) -> dict | None:
    """None when no phase BLOCKED and the run did not fail (it reached its package; validation decides)."""
    from ..reliability.observe import from_workspace

    ws = Path(ws)
    phase, reason = blocked_phase(ws)
    if phase is None:
        if not run_failed:
            return None
        ph = last_phase(ws)
        return _unavailable_bundle(ws, order_id, attempt_id, ph, agent_unavailable(ws, ph), "")
    err = agent_unavailable(ws, phase)
    if err:  # the phase stopped on files its errored agent turn never changed: not a product finding
        return _unavailable_bundle(ws, order_id, attempt_id, phase, err, reason)
    obs = sorted((o for o in from_workspace(ws) if o.get("phase") == phase and o.get("disposition") == "ACTIVE"),
                 key=lambda o: (o.get("ts_utc", ""), o["obs_id"]))  # the latest failure dominates
    route = [o for o in obs if o["operation"].endswith("/route")]
    work = [o for o in obs if not o["operation"].endswith("/route")]
    dom = (work or route or [None])[-1]
    if dom is None:
        return None
    open_capa = _capa_fingerprints() if open_capa is None else open_capa
    cls = afo_class(dom, open_capa)
    ins = sorted((ws / "inspection" / phase).glob("INS-*.json"))
    findings, reqs = [], set()
    if ins:
        for f in json.loads(ins[-1].read_text()).get("findings", []):
            findings.append(f"{f.get('id')}: {str(f.get('detail', ''))[:300]}")
            reqs |= set(re.findall(r"\bSWR-\d{3}\b", str(f.get("detail", ""))))
    summary = redact("; ".join([f"route: {reason}"] + findings + [o["excerpt"] for o in work[-3:] if o.get("excerpt")]))
    digests = {}
    for rel in (".forge-run/manifest.json", "workproducts/SWE.1/software_requirements.md", "software/ll/stm32n6xx_ll_rcc.h"):
        if (ws / rel).is_file():
            digests[rel] = sha256_file(ws / rel)
    tools = {}
    tr = ws / "verification/tool-results.jsonl"
    for line in tr.read_text().splitlines() if tr.is_file() else []:
        try:
            r = json.loads(line)
            tools[r.get("op", "?")] = str((r.get("result") or {}).get("tool_version") or "")[:60]
        except ValueError:
            continue
    rec = {"schema_version": "1.0", "order_id": order_id, "attempt_id": attempt_id, "phase": phase,
           "failure_class": cls, "fingerprint": dom["fingerprint"], "gate_result": "BLOCKED",
           "error_code": dom["error_code"][:200], "artifact_refs": [f"workspace:{p.relative_to(ws)}" for p in ins[-1:]],
           "evidence_refs": [f"cre-observation:{o['obs_id']}" for o in (work + route)[-5:]], "input_digests": digests,
           "tool_versions": {k: v for k, v in list(tools.items())[:20] if v}, "requirements_refs": sorted(reqs)[:20],
           "redacted_summary": summary[:MAX_SUMMARY], "context_truncated": len(summary) > MAX_SUMMARY,
           "untrusted_source_refs": [f"workspace:{p.relative_to(ws)}" for p in ins[-1:]] + ["agent_replies"]}
    rec["bundle_id"] = "afo-fb-" + hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:20]
    contracts.require("failure-bundle", rec)
    return rec
