"""Owner-obligation coverage for SWE.1 (docs/designs/swe1-owner-obligation-coverage.md; owner 2026-10-31).

A global, author-independent mechanism. When a work order declares an input with role `owner_obligations`
(`forge-c/owner-obligations/1`), every SWE.1 baseline must map each obligation to at least one requirement, or
record it as an obligation gap with a reason. Any author path (structured, semantic or an agent) is held to the same
rule, because the check reads the SWE.1 artifacts, not an author's internal records:

    - **SWR-nnn** <statement>
      - Obligations: OBL-a, OBL-b          (one line per requirement that implements obligations)
    ## Obligation gaps
    - **OBL-x**: <reason the inputs cannot support it>

A critical obligation is never closed by a gap (owner 2026-10-31: "critical obligations can never be gaps"): it needs
an implementing requirement. Work orders without the input keep their behaviour; `status(ws)` reports NOT_DECLARED so
the absence is visible.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROLE = "owner_obligations"
REQS = "workproducts/SWE.1/software_requirements.md"
EFFECTS = "workproducts/SWE.1/register_effects.json"
CSV = "traceability/obligations_to_requirements.csv"
_SWR = re.compile(r"^- \*\*(SWR-\d{3})\*\*")
_LINE = re.compile(r"^\s+- Obligations:\s*(.*)$")
_GAP = re.compile(r"^- \*\*(OBL-[a-z0-9][a-z0-9-]{1,60})\*\*:\s*(.+)$")


class ObligationsInvalid(ValueError):
    pass


def _manifest(ws: Path) -> dict:
    p = Path(ws) / ".forge-run/manifest.json"
    return json.loads(p.read_text()) if p.is_file() else {}


def declared(ws: Path) -> dict | None:
    """The declared obligations document, hash-checked against the manifest and contract-validated; None if the work
    order declares none. A declared but unreadable, changed or invalid input refuses (never silently ignored)."""
    from ..common import sha256_file
    from ..process_lab import contracts

    entries = [i for i in _manifest(ws).get("inputs") or [] if i.get("role") == ROLE]
    if not entries:
        return None
    if len(entries) > 1:
        raise ObligationsInvalid("OWNER_OBLIGATIONS_DECLARED_TWICE")
    entry = entries[0]
    path = Path(ws) / entry["path"]
    if path.is_symlink() or not path.is_file() or sha256_file(path) != entry.get("sha256"):
        raise ObligationsInvalid("OWNER_OBLIGATIONS_INPUT_CHANGED")
    try:
        doc = contracts.require("owner-obligations", json.loads(path.read_text()))
    except (ValueError, contracts.ContractError) as exc:
        raise ObligationsInvalid(f"OWNER_OBLIGATIONS_INVALID:{str(exc)[:160]}") from exc
    ids = [o["id"] for o in doc["obligations"]]
    if len(ids) != len(set(ids)):
        raise ObligationsInvalid("OWNER_OBLIGATIONS_DUPLICATE_ID")
    return {**doc, "_path": entry["path"], "_sha256": entry["sha256"]}


def status(ws: Path) -> dict:
    doc = declared(ws)
    if doc is None:
        return {"status": "NOT_DECLARED"}
    return {"status": "DECLARED", "path": doc["_path"], "sha256": doc["_sha256"], "owner_status": doc["status"],
            "obligations": len(doc["obligations"])}


def source_paths(ws: Path) -> list[str]:
    """Workspace paths an inspector may read to judge obligations: the obligations file and the owner inputs it names
    (resolved among the declared inputs by file name)."""
    doc = declared(ws)
    if doc is None:
        return []
    named = {Path(i["path"]).name: i["path"] for i in _manifest(ws).get("inputs") or []}
    return [doc["_path"]] + [named[n] for n in doc["source_inputs"] if n in named]


def parse(md: str) -> tuple[dict[str, list[str]], dict[str, str]]:
    """{SWR: [obligation ids]} from the requirement lines, and {obligation id: gap reason} from 'Obligation gaps'."""
    mapping: dict[str, list[str]] = {}
    gaps: dict[str, str] = {}
    current, in_gaps = None, False
    for line in md.splitlines():
        if line.startswith("## "):
            in_gaps, current = line.strip().lower() == "## obligation gaps", None
            continue
        if in_gaps:
            m = _GAP.match(line)
            if m:
                gaps[m.group(1)] = m.group(2).strip()
            continue
        m = _SWR.match(line)
        if m:
            current = m.group(1)
            mapping.setdefault(current, [])
            continue
        m = _LINE.match(line)
        if m and current:
            mapping[current] += [x.strip() for x in m.group(1).split(",") if x.strip()]
    return mapping, gaps


def coverage_findings(ws: Path) -> list[str]:
    """The deterministic SWE.1 coverage findings (empty when no obligations are declared)."""
    ws = Path(ws)
    try:
        doc = declared(ws)
    except ObligationsInvalid as exc:
        return [f"SWE1_{exc}"]
    if doc is None:
        return []
    if not (ws / REQS).is_file():
        return ["SWE1_OBLIGATION_REQUIREMENTS_MISSING"]
    mapping, gaps = parse((ws / REQS).read_text())
    known = {o["id"]: o for o in doc["obligations"]}
    out: list[str] = []
    cited: dict[str, list[str]] = {}
    for swr, ids in mapping.items():
        for i in ids:
            if i not in known:
                out.append(f"SWE1_OBLIGATION_UNKNOWN:{swr}:{i}")
            else:
                cited.setdefault(i, []).append(swr)
    out += [f"SWE1_OBLIGATION_UNKNOWN:gap:{i}" for i in gaps if i not in known]
    for i, gap_reason in gaps.items():
        if i in known and known[i].get("critical"):
            out.append(f"SWE1_OBLIGATION_CRITICAL_GAP:{i}: a critical owner obligation cannot be an obligation gap - "
                       f"write the requirement that implements it (owner: {known[i]['statement'][:160]})")
        elif i in known and len(gap_reason) < 10:
            out.append(f"SWE1_OBLIGATION_GAP_REASON_MISSING:{i}")
    effects = json.loads((ws / EFFECTS).read_text()).get("effects", []) if (ws / EFFECTS).is_file() else []
    for i, o in known.items():
        if i not in cited and i not in gaps:
            out.append(f"SWE1_OBLIGATION_UNCOVERED:{i}: no requirement implements it and it is not an obligation gap "
                       f"(owner: {o['statement'][:160]})")
            continue
        for e in o.get("effects") or []:
            if i in cited and not any(x.get("swr") in cited[i] and x.get("register") == e["register"]
                                      and x.get("field") == e["field"] and x.get("op") == e["op"] for x in effects):
                out.append(f"SWE1_OBLIGATION_EFFECT_MISSING:{i}:{e['register']}.{e['field']}.{e['op']}: none of "
                           f"{', '.join(cited[i])} states this register effect")
    return out


def render_lines(ids: list[str]) -> list[str]:
    return [f"  - Obligations: {', '.join(ids)}"] if ids else []


def render_gaps(gaps: list[dict]) -> list[str]:
    if not gaps:
        return []
    return ["", "## Obligation gaps", ""] + [f"- **{g['id']}**: {g['reason'].strip()}" for g in gaps]


def trace_csv(rows: list[dict], gaps: list[dict]) -> str:
    out = ["obligation_id,requirement_id,gap_reason"]
    for r in rows:
        for i in r.get("obligations") or []:
            out.append(f"{i},{r['swr']},")
    for g in gaps:
        reason = g["reason"].strip().replace('"', "'")
        out.append(f'{g["id"]},,"{reason}"')
    return "\n".join(out) + "\n"
