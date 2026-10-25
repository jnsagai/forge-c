"""Brownfield package contents (FR-009, FR-017): the delivery record, the delivered-code verification at packaging,
conformance and delivered-code findings as unresolved findings (package gaps), and the FIX_ALLOWED change report."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import pretty_json
from . import DELIVERY_DIR, code_mode, is_brownfield, manifest_of


def _load(ws: Path, name: str) -> dict:
    p = Path(ws) / DELIVERY_DIR / name
    try:
        return json.loads(p.read_text()) if p.is_file() else {}
    except ValueError:
        return {}


def findings(ws: Path) -> list[dict]:
    """Unresolved brownfield findings for quality/final-gates.json (each one is a package gap)."""
    ws = Path(ws)
    m = manifest_of(ws)
    if not is_brownfield(m):
        return []
    from .verify import verify

    out = []
    if not (ws / DELIVERY_DIR / "injection.json").is_file():
        out.append({"id": "DELIVERY:NOT_INJECTED", "severity": "major",
                    "detail": "the delivered code never entered the workspace (SWE.1 not passed)"})
        return out
    v = verify(ws, "package")
    out += [{"id": f"DELIVERY:{i}", "severity": "major", "detail": "delivered code fingerprint"} for i in v["issues"]]
    from .conformance import check

    cf = check(ws, "package")
    out += [{"id": f"CONFORMANCE:{f['id']}:{f['kind']}:{f['function'] or '-'}:{f['requirement'] or '-'}",
             "severity": "major", "detail": f["evidence"][:200]} for f in cf["findings"] if f["status"] == "OPEN"]
    if cf["status"] == "NOT_RUN":
        out.append({"id": "CONFORMANCE:NOT_RUN", "severity": "major", "detail": "; ".join(cf["issues"])[:200]})
    style = (m.get("delivery") or {}).get("build", {}).get("style", "forge")
    if code_mode(m) == "FROZEN" or style != "forge":  # OD-2026-10-20-02: vendor findings are owner gaps in any mode
        cc = (_load(ws, "code_findings.json").get("code_checks") or {}).get("findings") or []
        out += [{"id": f"DELIVERED_CODE:{x[:120]}", "severity": "major",
                 "detail": f"delivered code check ({code_mode(m)}, {style} style)"} for x in cc
                if disposition_of(ws, x) is None]  # OD-2026-10-20-07: an owner disposition settles the finding
    return out


def disposition_of(ws: Path, finding: str) -> dict | None:
    """The owner disposition (verification-dispositions.yaml, copied read-only by prepare) whose delivered_finding_regex
    matches this recorded delivered-code finding; never written by an agent."""
    import re

    from ..inspection.defects import owner_dispositions

    for d in owner_dispositions(ws):
        rx = d.get("delivered_finding_regex")
        if rx and re.search(rx, finding):
            return d
    return None


def dispositioned(ws: Path) -> list[str]:
    """Limitation lines for the delivered-code findings an owner disposition settles."""
    cc = (_load(ws, "code_findings.json").get("code_checks") or {}).get("findings") or []
    out = []
    for x in cc:
        d = disposition_of(ws, x)
        if d is not None:
            out.append(f"DELIVERED_CODE finding {x} dispositioned by {d['id']} ({d['disposition']}; {d['approved_by']}, "
                       f"{d['approved_at']}): {' '.join(str(d['limitation']).split())}")
    return out


def stage(ws: Path, stage_dir: Path) -> list[str]:
    """Write the delivery records into the package and return limitation lines."""
    ws, stage_dir = Path(ws), Path(stage_dir)
    m = manifest_of(ws)
    if not is_brownfield(m):
        return []
    d = m["delivery"]
    scope = _load(ws, "scope.json")
    rec = {"schema": "forge-c/package-delivery/0.1", "code_mode": m.get("code_mode"), "origin": d.get("origin"),
           "licence": d.get("licence"), "licence_allows_modification": d.get("licence_allows_modification"),
           "files": m.get("delivered"), "scope": {"functions": d["scope"]["functions"],
                                                   "excluded_count": scope.get("excluded_count")},
           "intake": _load(ws, "intake.json").get("status"),
           "injection": {k: _load(ws, "injection.json").get(k) for k in ("swe1_baseline_id", "injected_at")},
           "verification": _load(ws, "verification-package.json").get("status")}
    out = stage_dir / "configuration"
    out.mkdir(parents=True, exist_ok=True)
    (out / "delivery.json").write_text(pretty_json(rec))
    for name in ("intake.json", "scope.json", "injection.json", "conformance.json", "code_findings.json",
                 "change_report.json", "verification-package.json"):
        src = ws / DELIVERY_DIR / name
        if src.is_file():
            (stage_dir / "delivery").mkdir(parents=True, exist_ok=True)
            (stage_dir / "delivery" / name).write_bytes(src.read_bytes())
    cf = _load(ws, "conformance.json").get("findings") or []
    op = [f for f in cf if f.get("status", "OPEN") == "OPEN"]
    lines = [f"- Delivered code (brownfield, {m.get('code_mode')}): origin {d.get('origin')}; licence {d.get('licence')}; "
             f"{len(m.get('delivered') or [])} delivered files fingerprinted (configuration/delivery.json); "
             f"{len(d['scope']['functions'])} scope functions, {scope.get('excluded_count', 0)} excluded.",
             f"- The requirements were frozen before the delivered code entered the work order (SWE.1 baseline "
             f"{rec['injection'].get('swe1_baseline_id')}).",
             f"- Delivered code at packaging: {rec['verification'] or 'NOT_CHECKED'}.",
             f"- Conformance findings (delivered code vs requirements): {len(op)} "
             f"({', '.join(sorted({f['kind'] for f in op})) or 'none'})."]
    dfr = [f for f in cf if f.get("status") == "DEFERRED"]
    if dfr:  # feature 015: a value the delivered code computes is not decided statically
        lines.append(f"- Conformance checks not decidable statically, left to the requirement-based tests: {len(dfr)} ("
                     + "; ".join(f"{f['function']} {f['requirement']}" for f in dfr[:8]) + ").")
    if m.get("code_mode") == "FIX_ALLOWED":
        ch = _load(ws, "change_report.json").get("changes") or []
        lines.append(f"- Corrections of the delivered code: {len(ch)} file(s), each linked to a CODE defect "
                     "(delivery/change_report.json).")
    lines += [f"- {x}" for x in dispositioned(ws)]  # OD-2026-10-20-07: stated in every package, never hidden
    return lines
