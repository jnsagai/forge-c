"""EASA-T063 — reviewer-readable assurance case summary (assurance/ASSURANCE-CASE.md in the review package).

Rendered ONLY from the records the finalizer already wrote (summary, phase claims, independence attestation, method
applicability, fidelity limits). It states what is supported, what remains open and which evidence is missing; it
never upgrades a claim. Deterministic: no timestamps in the text, inputs listed by hash. Invalid input is reported in
the case and makes it UNSUPPORTED, never silently passes. The rendered text is checked for conformance/approval
assertions before it is returned (EASA-FR-058).
"""
from __future__ import annotations

from ..common import canonical_json, sha256_bytes
from .normative import compliance_assertions

STATES = ("SUPPORTED", "CONTESTED", "UNSUPPORTED", "UNKNOWN")
STATEMENT = ("Bounded engineering evidence for offline human review. This is not an ISO 26262 or Automotive SPICE "
             "conformance statement, not an ASIL approval and not a safety sign-off; no agent approves anything here.")


def _invalid(claims: list) -> list[str]:
    out = []
    if not isinstance(claims, list) or not claims:
        return ["NO_CLAIMS"]
    for i, c in enumerate(claims):
        if not isinstance(c, dict) or not c.get("claim_id"):
            out.append(f"INVALID_CLAIM_RECORD:#{i}")
        elif c.get("status") not in STATES:
            out.append(f"INVALID_CLAIM_STATUS:{c.get('claim_id')}:{c.get('status')}")
        elif c.get("safety_conclusion"):
            out.append(f"SAFETY_CONCLUSION_IN_CLAIM:{c['claim_id']}")
    return out


def overall(claims: list, attestation: dict, invalid: list[str]) -> str:
    if invalid:
        return "UNSUPPORTED"
    sts = {c["status"] for c in claims}
    if "CONTESTED" in sts:
        return "CONTESTED"
    if sts == {"SUPPORTED"} and attestation.get("decision") == "SUPPORTED":
        return "SUPPORTED"
    return "UNSUPPORTED" if "UNSUPPORTED" in sts or attestation.get("decision") != "SUPPORTED" else "UNKNOWN"


def render(summary: dict, claims: list, attestation: dict, applicability: list, fidelity: dict) -> tuple[str, dict]:
    invalid = _invalid(claims)
    valid = [c for c in claims if isinstance(c, dict) and c.get("claim_id") and c.get("status") in STATES] \
        if isinstance(claims, list) else []
    state = overall(valid, attestation or {}, invalid)
    inputs = {k: sha256_bytes(canonical_json(v)) for k, v in
              (("summary", {k: v for k, v in (summary or {}).items() if k != "generated_at"}), ("claims", claims),
               ("independence", attestation), ("applicability", applicability), ("fidelity", fidelity))}
    L = ["# Assurance case summary", "", f"**Work order:** {(attestation or {}).get('work_order_id', 'UNKNOWN')}  ",
         f"**Overall state:** {state}  ", f"**Mode / profile:** {summary.get('mode')} / {summary.get('profile')}  ",
         f"**Method catalog:** {summary.get('catalog_status')} (normative verification BLOCKED until a licensed source "
         "is registered and reconciled by a competent human reviewer)", "", f"> {STATEMENT}", ""]
    if invalid:
        L += ["## Invalid inputs (the case is UNSUPPORTED until they are fixed)", ""] + [f"- `{i}`" for i in invalid] + [""]
    L += ["## Claims", "", "| Claim | State | 002 gate | Assurance gate | Open requirements |", "|---|---|---|---|---|"]
    for c in valid:
        L.append(f"| {c['claim_id']}: {c.get('assertion', '')} | {c['status']} | {c.get('gate_002') or 'NOT_RUN'} | "
                 f"{c.get('assurance_gate', 'NOT_RUN')} | {', '.join(c.get('open_requirements') or []) or '-'} |")
    open_ = [c for c in valid if c["status"] != "SUPPORTED"]
    L += ["", "## Remaining claims and missing evidence", ""]
    if not open_:
        L.append("- None recorded. A reviewer still has to confirm each claim against its evidence.")
    for c in open_:
        why = {"CONTESTED": "counterevidence recorded (a failing verifier or gate)",
               "UNSUPPORTED": "the 002 gate passed but the independent assurance evidence is missing or not accepted",
               "UNKNOWN": "the phase did not complete or was not evaluated"}[c["status"]]
        req = ", ".join(c.get("open_requirements") or []) or "none listed"
        L.append(f"- **{c['claim_id']}** {c['status']}: {why}. Open evidence requirements: {req}.")
    blk = summary.get("blocking_findings") or []
    L += ["", "## Findings that would block in ENFORCING mode", ""] + ([f"- `{b}`" for b in blk] or ["- None."])
    L += ["", "## Independence", "",
          f"- Decision: **{(attestation or {}).get('decision', 'UNKNOWN')}**",
          "- Common-cause references: " + (", ".join((attestation or {}).get("shared_common_cause_refs") or []) or "none")]
    unsup = sorted(m["method_id"] for m in applicability or [] if m.get("resolution") == "NOT_SUPPORTED")
    partial = sorted(m["method_id"] for m in applicability or [] if m.get("resolution") == "PARTIAL")
    L += ["", "## Methods without full tool support", "",
          f"- NOT_SUPPORTED ({len(unsup)}): " + (", ".join(unsup) or "none"),
          f"- PARTIAL ({len(partial)}): " + (", ".join(partial) or "none")]
    lim = (fidelity or {}).get("limitations") or []
    L += ["", "## Hardware-fidelity limits", "",
          f"- Environments: {', '.join((fidelity or {}).get('environments') or [])}; HIL: "
          f"{(fidelity or {}).get('hil', 'UNKNOWN')}; physical target: {(fidelity or {}).get('physical', 'UNKNOWN')}"]
    L += [f"- {x if isinstance(x, str) else canonical_json(x).decode()[:200]}" for x in lim[:20]]
    scope = (summary or {}).get("safety_scope") or {}
    why = scope.get("note") or ", ".join(scope.get("issues") or []) or "-"
    L += ["", "## Safety scope", "", f"- {scope.get('status', 'UNKNOWN')}: {why}",
          "", "## Inputs (sha256 of the canonical records)", ""] + [f"- {k}: `{v}`" for k, v in inputs.items()] + [""]
    md = "\n".join(L)
    bad = compliance_assertions(md)
    if bad:  # never emit a case that asserts conformance/approval
        raise ValueError(f"ASSURANCE_CASE_ASSERTS_COMPLIANCE:{bad[:3]}")
    return md, {"state": state, "invalid": invalid, "open_claims": [c["claim_id"] for c in open_], "inputs": inputs}
