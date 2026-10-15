"""Deterministic SWE.2 architecture checks (model-free): structure, SWR allocation, register offsets vs RM0486.

Why: an 8B inspector passed every SWE.2 item on a 127-byte file that held the author's JSON reply (r11).
Checks: the workproduct is markdown with the required sections; every SWE.1 SWR is allocated and no unknown
SWR is referenced; every register in the register table that has an RM0486 section file in the workspace
inputs carries that section's documented address offset. Findings are factual and machine-readable.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ARCH = "workproducts/SWE.2/software_architecture.md"
REQS = "workproducts/SWE.1/software_requirements.md"
SECTIONS_DIR = "inputs/sections/RM0486"
REQUIRED_SECTIONS = {"components": r"component", "interfaces": r"interface", "register_table": r"register\s+table",
                     "requirement_allocation": r"allocation"}
SWR = re.compile(r"SWR-[A-Z0-9][A-Z0-9_.-]*[A-Z0-9]")
HEX = re.compile(r"^(0x[0-9a-fA-F]+|\d+)$")


def is_agent_reply(text: str) -> bool:
    """A workproduct that is only an agent's compact status JSON (contract-shaped object) is never a workproduct."""
    try:
        obj = json.loads(text)
    except ValueError:
        return False
    return isinstance(obj, dict) and "status" in obj and ("next_action" in obj or "artifacts" in obj)


def rm_offsets(ws: Path) -> dict[str, int]:
    """Register name -> documented address offset from the RM0486 section files (`#### ... (RCC_CR)` + offset)."""
    out: dict[str, int] = {}
    d = ws / SECTIONS_DIR
    for f in sorted(d.glob("*.md")) if d.is_dir() else []:
        text = f.read_text(errors="replace")[:2000]
        name = re.search(r"^#+ .*\((RCC_[A-Z0-9_]+)\)\s*$", text, re.M)
        off = re.search(r"Address offset:\s*(0x[0-9a-fA-F]+)", text)
        if name and off:
            out.setdefault(name.group(1), int(off.group(1), 16))
    return out


def _sections(text: str) -> dict[str, str]:
    parts = re.split(r"^(#{1,4} .+)$", text, flags=re.M)
    return {parts[i].lstrip("#").strip().lower(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _rows(body: str) -> list[list[str]]:
    rows = []
    for line in body.splitlines():
        if line.strip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|\s*$", line):
            rows.append([c.strip().strip("`") for c in line.strip().strip("|").split("|")])
    return rows[1:] if rows else []  # drop header row


def check_architecture(ws: Path) -> dict:
    p = ws / ARCH
    findings: list[str] = []
    if not p.is_file():
        return {"verdict": "FAIL", "major_findings": ["SWE2:NO_ARCHITECTURE_FILE"], "stats": {}}
    text = p.read_text(errors="replace")
    if is_agent_reply(text.strip()):
        return {"verdict": "FAIL", "major_findings": ["SWE2:WORKPRODUCT_IS_AGENT_REPLY"], "stats": {}}
    secs = _sections(text)
    found = {}
    for key, pat in REQUIRED_SECTIONS.items():
        found[key] = next((b for h, b in secs.items() if re.search(pat, h)), None)
        if found[key] is None:
            findings.append(f"SWE2:MISSING_SECTION:{key}")
    req_file = ws / REQS
    known = set(SWR.findall(req_file.read_text(errors="replace"))) if req_file.is_file() else set()
    referenced = set(SWR.findall(text))
    allocated = set(SWR.findall(found["requirement_allocation"] or ""))
    findings += [f"SWE2:SWR_NOT_ALLOCATED:{r}" for r in sorted(known - allocated)]
    findings += [f"SWE2:UNKNOWN_SWR:{r}" for r in sorted(referenced - known)] if known else []
    regs = _rows(found["register_table"] or "")
    if found["register_table"] is not None and not regs:
        findings.append("SWE2:EMPTY_REGISTER_TABLE")
    documented, checked = rm_offsets(ws), 0
    for row in regs:
        if len(row) < 2:
            continue
        name, off = row[0].split()[0] if row[0] else "", row[1]
        if not HEX.match(off):
            findings.append(f"SWE2:REGISTER_OFFSET_NOT_NUMERIC:{name}")
            continue
        if name in documented:
            checked += 1
            if (int(off, 16) if off.lower().startswith("0x") else int(off)) != documented[name]:
                findings.append(f"SWE2:REGISTER_OFFSET_MISMATCH:{name}:{off}!=0x{documented[name]:X}")
    return {"verdict": "FAIL" if findings else "PASS", "major_findings": findings,
            "stats": {"swr_known": len(known), "swr_allocated": len(allocated & known), "registers": len(regs),
                      "registers_checked_against_rm": checked}}
