"""Brownfield safety drafts (US5, FR-015): a software safety analysis and a tool assurance assessment of the delivered
code, generated deterministically from the work order's records (no model): the delivered scope functions and their
register effects, conformance findings, escalated defects and the tools that actually ran.

They are written to `safety/drafts/` with the draft marker, never to the owner-signed paths, so they can never
unblock a package; the owner reviews, completes and signs a version through the signed-document register."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import utc_now
from . import DELIVERY_DIR, is_brownfield, manifest_of

DRAFTS = "safety/drafts"
MARK = "**DRAFT — factory-generated from records, not reviewed, not approved**"


def _facts(ws: Path) -> list[dict]:
    p = ws / "workproducts/SWE.3/delivered_code_facts.json"
    return json.loads(p.read_text()).get("functions", []) if p.is_file() else []


def _fault_modes(f: dict) -> list[tuple[str, str, str]]:
    """(fault mode, effect, open point) rows for one delivered function, from its register effects."""
    rows = []
    writes = [e for e in f.get("register_effects", []) if e["op"] != "read"]
    reads = [e for e in f.get("register_effects", []) if e["op"] == "read"]
    for e in writes:
        reg = e["via"] or e["register"]
        if e["via"]:
            rows.append((f"write to alias {e['via']} has no effect", f"{e['register']} bits {e['bits']} not {e['op']}",
                        "no read-back in the function: the caller verifies (assumption of use)"))
        else:
            rows.append((f"lost update of {reg} (read-modify-write interrupted)",
                         f"other bits of {reg} changed by a concurrent writer",
                         "callers serialise every writer of the register (assumption of use)"))
            rows.append((f"write to {reg} ignored (access rights, bus error)", f"bits {e['bits']} not {e['op']}",
                         "no read-back in the function: the caller verifies (assumption of use)"))
    for e in reads:
        rows.append((f"stale or stuck read of {e['register']}", "wrong status returned to the caller",
                     "system-level monitoring (assumption of use)"))
    return rows or [("function has no register access", "-", "-")]


def write(ws: Path) -> list[str]:
    ws = Path(ws)
    m = manifest_of(ws)
    if not is_brownfield(m):
        return []
    d = m["delivery"]
    facts = _facts(ws)
    conf = []
    p = ws / DELIVERY_DIR / "conformance.json"
    if p.is_file():
        conf = json.loads(p.read_text()).get("findings", [])
    defects = []
    for q in sorted((ws / ".forge-run/defects").glob("DEF-*.json")):
        x = json.loads(q.read_text())
        if x.get("kind") == "CODE":
            defects.append(x)
    target = m.get("safety_target")
    level = f"ASIL {target}" if target in ("A", "B", "C", "D") else "not set by an owner safety scope"
    files = "\n".join(f"| `{x['path']}` | `{x['sha256']}` | {x['role']} |" for x in m.get("delivered") or [])
    head = (f"| Field | Value |\n|---|---|\n| Status | {MARK} |\n| Work order | {m.get('work_order')} |\n"
            f"| Delivered code | origin {d.get('origin')}; licence {d.get('licence')}; mode {m.get('code_mode')} |\n"
            f"| Target safety level | {level} |\n| Generated | {utc_now()} |\n\n"
            "> Draft for the owner's review. It becomes a factory input only when a reviewed version is signed and "
            "registered (config/factory/safety-documents/README.md). It is not a safety analysis approval, a safety "
            "approval or a certification.\n\n"
            f"## Delivered files\n\n| File | SHA-256 | Role |\n|---|---|---|\n{files}\n")
    fm = []
    for f in facts:
        for mode, eff, open_ in _fault_modes(f):
            fm.append(f"| {f['function']} | FM-{len(fm) + 1:02d} | {mode} | {eff} | {open_} |")
    cf = "\n".join(f"| {x['id']} | {x['kind']} | {x['function'] or '-'} | {x['requirement'] or '-'} | "
                   f"{x['evidence'][:140]} |" for x in conf) or "| - | none | - | - | - |"
    dl = "\n".join(f"| {x['id']} | {x.get('status')} | {x.get('summary', '')[:120]} |" for x in defects) or \
        "| - | none | - |"
    ssa = (f"# Software Safety Analysis — delivered code (draft)\n\n{head}\n"
           "## Method\n\nFor each delivered scope function the factory applied fault guide words (omission, wrong "
           "register or bit, lost update, ignored write, stale read) to the register effects it extracted from the "
           "delivered source (workproducts/SWE.3/delivered_code_facts.json). The reviewer adds the safety context: "
           "allocated or assumed safety requirements, the system effect of each fault mode and the safety measures.\n\n"
           "## Fault modes per delivered function\n\n| Function | ID | Fault mode | Effect at the driver boundary | "
           "Open point |\n|---|---|---|---|---|\n" + ("\n".join(fm) or "| - | - | no facts recorded | - | - |") +
           "\n\n## Conformance findings (delivered code vs requirements)\n\n| ID | Kind | Function | Requirement | "
           f"Evidence |\n|---|---|---|---|---|\n{cf}\n\n## Defects against the delivered code\n\n| Defect | Status | "
           f"Summary |\n|---|---|---|\n{dl}\n\n## Open questions for the reviewer\n\n"
           "- Which safety requirements (allocated or assumed) apply to the delivered functions?\n"
           "- Which fault modes above can violate them, and which measure covers each?\n"
           "- Are the conformance findings and escalated defects acceptable as deviations?\n\n"
           "## Review and signature\n\n| Field | Value |\n|---|---|\n| Reviewed by | |\n| Decision | |\n| Date | |\n")
    tools = {}
    tr = ws / "evidence/tool-results.jsonl"
    if tr.is_file():
        for ln in tr.read_text().splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            res = r.get("result") or {}
            prov = res.get("provenance") or {}
            key = f"{r.get('server')}.{r.get('op')}"
            tools[key] = (prov.get("tool") or prov.get("tool_id") or "-", prov.get("tool_version") or
                          prov.get("version") or "-", res.get("status", "-"))
    trows = "\n".join(f"| {k} | {v[0]} | {v[1]} | last status {v[2]} | to assess | to assess |"
                      for k, v in sorted(tools.items())) or "| - | no tool results recorded | - | - | - | - |"
    taa = (f"# Tool Assurance Assessment — delivered-code verification (draft)\n\n{head}\n"
           "## Tools used on the delivered code\n\nEvery tool operation recorded in this work order "
           "(evidence/tool-results.jsonl). For delivered code the tools only verify: a tool error can let a defect "
           "in the delivered code go unnoticed (tool impact), never put one into it, except in FIX_ALLOWED mode "
           "where the compiler also builds corrected code.\n\n| Operation | Tool | Version | Use | Tool impact | "
           f"Error detection |\n|---|---|---|---|---|---|\n{trows}\n\n## Open questions for the reviewer\n\n"
           "- Tool impact, error detection and confidence level for each tool (see the signed TAA of the product for "
           "the reasoning used so far).\n- Which measure justifies each tool above the lowest confidence level?\n\n"
           "## Review and signature\n\n| Field | Value |\n|---|---|\n| Reviewed by | |\n| Decision | |\n| Date | |\n")
    out = ws / DRAFTS
    out.mkdir(parents=True, exist_ok=True)
    (out / "software_safety_analysis.md").write_text(ssa)
    (out / "tool_assurance_assessment.md").write_text(taa)
    return [f"{DRAFTS}/software_safety_analysis.md", f"{DRAFTS}/tool_assurance_assessment.md"]
