"""Valid and invalid sample instances for each contract schema (T005)."""
from __future__ import annotations

import copy

H = "a" * 64

PROV = {
    "role": "author",
    "skill": "hi-sys-req-author",
    "skill_version": "0.1.0",
    "harness": "claude-code",
    "model": None,
    "model_family": "claude",
    "input_hashes": {"needs/stakeholder-needs.md": H},
    "created_utc": "2026-11-22T12:00:00Z",
    "run_id": "r-0001",
}

REQ = {
    "id": "SYS-WDM-001",
    "level": "system",
    "text": "The system shall request the safe state within 50 ms after a supervised task misses its alive indication.",
    "sources": [{"kind": "upstream", "id": "STK-WDM-001"}],
    "derived": False,
    "verification_method": "test",
    "status": "proposed",
}

VALID = {
    "project": {
        "schema": "forge-c-hi/project@1",
        "project_id": "safety-supervisor",
        "integrity_level": "HI-2",
        "input_class": "natural_language",
        "entry_stage": "sys-req",
        "inputs": [{"path": "needs/stakeholder-needs.md", "kind": "needs"}],
        "roles": {
            "author": {"harness": "claude-code", "command": ["claude", "-p"], "model_family": "claude"},
            "inspector": {"harness": "codex", "command": ["codex", "exec"], "model_family": "gpt", "read_only": True},
        },
    },
    "requirement-set": {
        "schema": "forge-c-hi/requirement-set@1",
        "stage": "sys-req",
        "baseline_id": "SYS-BL-1",
        "status": "draft",
        "provenance": PROV,
        "items": [REQ],
        "open_points": [],
    },
    "trace": {
        "schema": "forge-c-hi/trace@1",
        "links": [{"from": "STK-WDM-001", "to": "SYS-WDM-001", "type": "derives", "status": "valid"}],
    },
    "finding": {
        "id": "F-001",
        "phase": "item",
        "checklist_item": "IQ-03",
        "target_id": "SYS-WDM-001",
        "severity": "major",
        "description": "Term 'quickly' is ambiguous.",
        "round": 1,
        "status": "open",
    },
    "gate-result": {
        "gate": "trace",
        "verdict": "NOT_RUN",
        "tool": {"name": "hi", "version": "0.1.0"},
        "exit_code": None,
        "evidence": [],
        "issues": [],
        "not_run_reason": "pdftotext not installed",
        "profile": "generic",
        "integrity_level": "HI-2",
    },
    "agent-status": {
        "role": "inspector",
        "stage": "sw-req",
        "status": "NEEDS_REWORK",
        "outputs": [],
        "issues": [{"code": "IQ-05", "target_id": "SWR-WDM-003"}],
        "open_points": 0,
    },
    "review-manifest": {
        "schema": "forge-c-hi/review-manifest@1",
        "run_id": "r-0001",
        "status": "BLOCKED",
        "gaps": [{"code": "NOT_RUN", "source": "sw-req/gates/doc-sources", "message": "no PDF tools"}],
        "files": [{"path": "hi/sys-req/requirements.json", "sha256": H}],
        "profile": "generic",
        "integrity_level": "HI-2",
        "provenance_summary": [],
        "tool_versions": {"hi": "0.1.0"},
        "disclaimer": "Not a certification, approval or production release.",
        "created_utc": "2026-11-22T12:00:00Z",
    },
}


def _mut(name, fn):
    doc = copy.deepcopy(VALID[name])
    fn(doc)
    return doc


INVALID = [
    ("project", _mut("project", lambda d: d.update(integrity_level="ASIL-B")), "level must be neutral HI-n"),
    ("project", _mut("project", lambda d: d["roles"].pop("inspector")), "inspector role required"),
    ("project", _mut("project", lambda d: d.update(extra=1)), "no unknown keys"),
    ("requirement-set", _mut("requirement-set", lambda d: d["items"][0].update(id="REQ1")), "id pattern"),
    ("requirement-set", _mut("requirement-set", lambda d: d["items"][0].update(sources=[])), "at least one source"),
    ("requirement-set", _mut("requirement-set", lambda d: d["items"][0].update(derived=True)), "derived needs rationale"),
    (
        "requirement-set",
        _mut("requirement-set", lambda d: d["items"][0].update(sources=[{"kind": "document", "doc_id": "RM"}])),
        "document source needs section and page",
    ),
    ("trace", _mut("trace", lambda d: d["links"][0].update(type="relates")), "link type enum"),
    ("finding", _mut("finding", lambda d: d.update(checklist_item="iq3")), "checklist id pattern"),
    ("gate-result", _mut("gate-result", lambda d: d.update(verdict="SKIPPED")), "verdict enum"),
    ("agent-status", _mut("agent-status", lambda d: d.update(outputs=["x"] * 21)), "compact: max 20 outputs"),
    (
        "review-manifest",
        _mut("review-manifest", lambda d: d.update(status="READY_FOR_OFFLINE_REVIEW")),
        "READY must have zero gaps",
    ),
    ("review-manifest", _mut("review-manifest", lambda d: d["files"][0].update(sha256="xyz")), "sha256 pattern"),
]
