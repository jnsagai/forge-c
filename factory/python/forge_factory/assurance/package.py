"""EASA-T057..T060 — assurance inventory in the existing offline review package (no new Release Manager).

`bundle_into(ws, stage, dry_status)` is called by `release/finalize.py` after the CRE bundle and before sealing:
  * assurance/ : observe-only gate log, independence attestation (from the recorded model profile), method
    applicability + capability resolution, hardware-fidelity limitations, CAE claims of the six SWE phases, trace
    matrix coverage, and a hash list of everything in the folder; configuration/model-profile.json is packaged
    (audit finding F-06: the model per role was not substantiable from sealed bytes);
  * technical status (SWE gates) is reported separately from the package status (EASA-FR-058/T058);
  * mode OBSERVE_ONLY/PILOT: findings are recorded as observations, the package status is NEVER changed;
    mode ENFORCING: each blocking finding is added to quality/final-gates.json open_findings, which the existing,
    unchanged v0.5 release policy (require_no_open_findings) turns into a BLOCKED package;
  * safety scope (T059, ADR-0010): QM inapplicability of the two safety documents is written ONLY from an approved
    scope record with a human approver and rationale; ASIL scope never gets N/A; without a record nothing changes.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common import canonical_json, pretty_json, sha256_bytes, utc_now
from . import capability, case, catalog, independence, policy, scope
from . import target as T

SCOPE_FILE = ".forge-run/safety_scope.json"  # written only by an owner decision (never by an agent)
SAFETY_FILES = {"software_safety_analysis": "safety/software_safety_analysis.md",
                "tool_assurance_assessment": "safety/tool_assurance_assessment.md"}
PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")


def _policy() -> dict:
    return policy.active()


def _gate_log(ws: Path) -> list[dict]:
    p = ws / ".forge-run/assurance/gate-log.jsonl"
    out = []
    for line in (p.read_text().splitlines() if p.is_file() else []):
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def attestation(ws: Path) -> dict:
    prof = ws / ".forge-run/model-profile.json"
    p = json.loads(prof.read_text()) if prof.is_file() else {}
    model, prov = p.get("default"), p.get("provider")
    over = set(p.get("nodes") or [])
    au = {"agent_id": "swe-author-nodes", "role": "author", "model": model, "provider": prov}
    ins = {"agent_id": "swe-inspector-nodes", "role": "inspector",
           "model": None if over else model, "provider": None if over else prov}
    return independence.attest(ws.parent.name, au, ins, {"role": "easa-verifier", "kind": "deterministic"}, [])


def phase_claims(gates: dict, gate_log: list[dict]) -> list[dict]:
    """One claim per SWE phase: SUPPORTED needs the 002 gate PASS AND the assurance gate PASS (hash-bound evidence)."""
    last = {}
    for d in gate_log:
        if d.get("phase"):
            last[d["phase"]] = d
    out = []
    for ph in PHASES:
        g002 = (gates.get(ph) or {}).get("decision")
        a = last.get(ph) or {}
        st = "SUPPORTED" if g002 == "PASS" and a.get("state") == "PASS" else \
            ("CONTESTED" if a.get("state") == "FAIL" else ("UNSUPPORTED" if g002 == "PASS" else "UNKNOWN"))
        out.append({"claim_id": f"CLM-{ph}", "phase": ph, "assertion": f"{ph} objectives met by independent evidence",
                    "status": st, "gate_002": g002, "assurance_gate": a.get("state", "NOT_RUN"),
                    "open_requirements": sorted(k for k, v in (a.get("requirements") or {}).items() if v != "PASS"),
                    "safety_conclusion": None})
    return out


def scope_dispositions(ws: Path, stage: Path) -> dict:
    p = ws / SCOPE_FILE
    if not p.is_file():
        return {"status": "NO_APPROVED_SCOPE", "note": "product ASIL/QM scope not recorded by the owner; safety "
                "documents stay required (gaps unchanged)"}
    rec = json.loads(p.read_text())
    sc, na, docs = rec.get("scope") or {}, rec.get("na") or {}, {}
    for key, rel in SAFETY_FILES.items():
        f = stage / rel
        docs[key] = rel if f.is_file() and f.stat().st_size else None
    ev = scope.evaluate(sc, docs, na)
    if sc.get("target_asil") == "QM" and ev["state"] == "SATISFIED":
        for key, rel in SAFETY_FILES.items():
            if ev["dispositions"].get(key) == "NOT_APPLICABLE_QM" and not docs[key]:
                n = na[key]
                f = stage / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(f"# {key.replace('_', ' ').title()} - NOT APPLICABLE (QM scope)\n\n"
                             f"- Scope: {sc.get('scope_id')} - target {sc['target_asil']} from {sc['product_asil_source']}\n"
                             f"- Approved by: {n['approved_by']} ({n.get('approved_at', 'date not recorded')})\n"
                             f"- Rationale: {n['rationale']}\n\n"
                             "This statement records an owner-approved scope decision. It is not a safety analysis "
                             "and not a safety approval.\n")
    return {"status": ev["state"], "issues": ev["issues"], "dispositions": ev["dispositions"],
            "target_asil": sc.get("target_asil")}


def bundle_into(ws: Path, stage: Path, dry_status: str) -> dict:
    ws, stage = Path(ws), Path(stage)
    pol = _policy()
    mode = pol["mode"]
    files: dict[str, bytes] = {}
    prof = ws / ".forge-run/model-profile.json"
    if prof.is_file():
        (stage / "configuration").mkdir(parents=True, exist_ok=True)
        (stage / "configuration/model-profile.json").write_bytes(prof.read_bytes())
    quality_p = stage / "quality/final-gates.json"
    quality = json.loads(quality_p.read_text()) if quality_p.is_file() else {}
    checks = quality.get("checks") or {}  # the packaged quality report records each phase gate as sweN_inspection
    gates = {f"SWE.{n}": {"decision": "PASS" if checks.get(f"swe{n}_inspection") else "FAIL"} for n in range(1, 7)}
    log = _gate_log(ws)
    cat = catalog.load()
    att = attestation(ws)
    claims = phase_claims(gates, log)
    scope_rec = scope_dispositions(ws, stage)
    model_txt = (Path(__file__).resolve().parents[3] / "sim/stm32n6/rcc_model.py")
    lim = T.limitations(ws, model_txt.read_text() if model_txt.is_file() else "")
    matrices = sorted(p.name for p in ws.glob("workproducts/SWE.*/traceability/matrix_*.csv"))
    blocking = []
    if att["decision"] in ("NOT_INDEPENDENT", "UNKNOWN"):
        blocking.append(f"EASA:INDEPENDENCE_{att['decision']}")
    blocking += [f"EASA:{c['claim_id']}:{c['status']}" for c in claims if c["status"] in ("CONTESTED", "UNSUPPORTED")]
    if scope_rec["status"] == "BLOCKED":
        blocking += [f"EASA:{i}" for i in scope_rec["issues"]]
    technical = "PASS" if all((gates.get(p) or {}).get("decision") == "PASS" for p in PHASES) else "NOT_PASS"
    summary = {"schema": "forge-c/easa-package/0.1", "generated_at": utc_now(), "mode": mode, "profile": pol["profile"],
               "policy_sha": policy.policy_sha(pol), "catalog_sha": catalog.digest(cat),
               "catalog_status": catalog.status(cat), "technical_status": technical, "package_status_before": dry_status,
               "enforced": mode == "ENFORCING", "blocking_findings": blocking,
               "observations_only": mode != "ENFORCING", "matrices": matrices, "safety_scope": scope_rec,
               "statement": "Bounded engineering evidence for offline human review; no ISO 26262 / ASPICE conformance, "
                            "no ASIL approval, no safety sign-off."}
    files["assurance/summary.json"] = pretty_json(summary).encode()
    files["assurance/gate-log.jsonl"] = "".join(json.dumps(d, sort_keys=True) + "\n" for d in log).encode()
    files["assurance/independence.json"] = pretty_json(att).encode()
    files["assurance/claims.json"] = pretty_json(claims).encode()
    appl = capability.resolve(cat)
    fid = {"limitations": lim, "environments": ["HOST", "RENODE"], "hil": "NOT_AVAILABLE", "physical": "NOT_AVAILABLE"}
    files["assurance/applicability.json"] = pretty_json(appl).encode()
    files["assurance/fidelity.json"] = pretty_json(fid).encode()
    md, case_meta = case.render(summary, claims, att, appl, fid)  # EASA-T063: reviewer-readable case
    files["assurance/ASSURANCE-CASE.md"] = md.encode()
    files["assurance/case.json"] = pretty_json(case_meta).encode()
    for rel, data in files.items():
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        (stage / rel).write_bytes(data)
    hashes = {rel: sha256_bytes(data) for rel, data in sorted(files.items())}
    (stage / "assurance/hashes.json").write_text(pretty_json({"files": hashes,
                                                              "bundle_sha256": sha256_bytes(canonical_json(hashes))}))
    if mode == "ENFORCING" and blocking and quality_p.is_file():
        quality["open_findings"] = list(quality.get("open_findings") or []) + \
            [{"id": b, "severity": "major", "detail": "enhanced assurance (EASA) evidence missing or contradicted"}
             for b in blocking]
        quality_p.write_text(pretty_json(quality))
    return summary
