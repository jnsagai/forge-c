"""Deterministic EARS (Easy Approach to Requirements Syntax) conformance checker for SWE.1.

Backs checklist item SWE1-07 (v0.4 overlay). No model inference: pure pattern rules after
Mavin et al., "EARS" (RE'09). Patterns (case-insensitive keywords, one `shall` per requirement):

  UBIQUITOUS    The <system> shall <response>.
  STATE         While <state>, the <system> shall <response>.
  EVENT         When <trigger>, the <system> shall <response>.
  OPTIONAL      Where <feature>, the <system> shall <response>.
  UNWANTED      If <condition>, then the <system> shall <response>.
  COMPLEX       Ordered combination of preconditions: [Where …,] [While …,] (When …, | If …, then) the <system> shall …

Requirement lines are recognised as `- **SWR-001** <statement>` or markdown table rows
`| SWR-001 | <statement> | ...`. Findings are factual and machine-readable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REQ_ID = r"(SWR-[A-Z0-9][A-Z0-9_.-]*)"
_BULLET = re.compile(rf"^\s*(?:[-*]\s*)?\*\*{REQ_ID}\*\*\s*[:\-–]?\s*(?:\(EARS:\s*[a-z]+\)\s*)?(.+?)\s*$")
_TABLE = re.compile(rf"^\s*\|\s*{REQ_ID}\s*\|\s*([^|]+?)\s*\|")

# Reset events may name their controller/domain or reset type. These are
# language classifiers, not evidence that the physical reset behavior is correct.
# Exclude reset-control/reset_code identifiers from the event noun.
RESET_AFTER = r"\bafter\s+(?:(?:a|an|the)\s+)?(?:[A-Za-z_][\w-]*\s+){0,3}reset(?![\w-])"
STARTUP_NO_CALL = r"While\s+no\b[^.\n]*" + RESET_AFTER

_SYS = r"the\s+(?P<system>[A-Za-z0-9][\w ./-]{1,60}?)\s+shall\s+(?P<response>.+)"
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("COMPLEX", re.compile(
        r"^(?:where\s+[^,]+,\s*)?(?:while\s+[^,]+,\s*)?(?:when\s+[^,]+,\s*|if\s+[^,]+,\s*then\s+)" + _SYS + r"$",
        re.I)),
    ("UNWANTED", re.compile(r"^if\s+(?P<pre>[^,]+),\s*then\s+" + _SYS + r"$", re.I)),
    ("EVENT", re.compile(r"^when\s+(?P<pre>[^,]+),\s*" + _SYS + r"$", re.I)),
    ("STATE", re.compile(r"^while\s+(?P<pre>[^,]+),\s*" + _SYS + r"$", re.I)),
    ("OPTIONAL", re.compile(r"^where\s+(?P<pre>[^,]+),\s*" + _SYS + r"$", re.I)),
    ("UBIQUITOUS", re.compile(r"^" + _SYS + r"$", re.I)),
]
WEAK_MODALS = re.compile(r"\b(should|may|might|could|will|must|can)\b", re.I)
VAGUE = re.compile(r"\b(fast|quickly|efficient(ly)?|user[- ]friendly|as appropriate|as required|"
                   r"if possible|etc\.?|and/or|TBD|TBC|approximately|adequate|sufficient)\b", re.I)


@dataclass
class Requirement:
    req_id: str
    text: str
    line: int
    pattern: str | None = None
    findings: list[str] = field(default_factory=list)


def match(statement: str) -> tuple[str, re.Match[str]] | None:
    s = statement.strip().rstrip(".").strip()
    if not s:
        return None
    pre = [m.group(1).lower() for m in re.finditer(r"(?:^|,\s*)(where|while|when|if)\b", s, re.I)]
    for name, pat in PATTERNS:
        m = pat.match(s)
        if m:
            if name == "COMPLEX" and len(pre) < 2:
                continue
            return name, m
    return None


def classify(statement: str) -> str | None:
    found = match(statement)
    return found[0] if found else None


def check_statement(req: Requirement, systems: set[str] | None = None) -> Requirement:
    text = req.text.strip()
    shall_count = len(re.findall(r"\bshall\b", text, re.I))
    if shall_count == 0:
        req.findings.append(f"{req.req_id}:EARS_NO_SHALL")
    elif shall_count > 1:
        req.findings.append(f"{req.req_id}:EARS_NOT_ATOMIC_{shall_count}_SHALL")
    found = match(text) if shall_count == 1 else None
    req.pattern = found[0] if found else None
    if shall_count == 1 and req.pattern is None:
        req.findings.append(f"{req.req_id}:EARS_PATTERN_NONCONFORMANT")
    if weak := WEAK_MODALS.search(text):
        req.findings.append(f"{req.req_id}:EARS_WEAK_MODAL:{weak.group(1).lower()}")
    if vague := VAGUE.search(text):
        req.findings.append(f"{req.req_id}:EARS_VAGUE_TERM:{vague.group(0).lower()}")
    if not text.endswith("."):
        req.findings.append(f"{req.req_id}:EARS_MISSING_TERMINATOR")
    if systems and found:
        name = found[1].group("system").strip()
        if name.lower() not in {s.lower() for s in systems}:
            req.findings.append(f"{req.req_id}:EARS_UNKNOWN_SYSTEM_NAME")
            # CAPA-032 (r112/r114): the bare code gave no clue and the author repeated a qualified subject 3x
            req.findings.append(f"{req.req_id}:EARS_SYSTEM_NAME_HINT:subject '{name[:60]}' is not a system name; write "
                                f"'the <name> shall' with <name> exactly one of: {', '.join(sorted(systems))}; move "
                                "qualifiers (target, call chain, build) into the condition clause")
    return req


def extract(markdown: str) -> list[Requirement]:
    reqs: list[Requirement] = []
    for n, line in enumerate(markdown.splitlines(), 1):
        m = _BULLET.match(line) or _TABLE.match(line)
        if m:
            reqs.append(Requirement(m.group(1), m.group(2).strip(), n))
    return reqs


def check_document(markdown: str, systems: set[str] | None = None) -> dict:
    reqs = [check_statement(r, systems) for r in extract(markdown)]
    findings = [f for r in reqs for f in r.findings]
    seen: dict[str, int] = {}
    for r in reqs:
        if r.req_id in seen:
            findings.append(f"{r.req_id}:DUPLICATE_ID")
        seen[r.req_id] = r.line
    if not reqs:
        findings.append("SWE1:NO_REQUIREMENTS_FOUND")
    counts: dict[str, int] = {}
    for r in reqs:
        counts[r.pattern or "NONCONFORMANT"] = counts.get(r.pattern or "NONCONFORMANT", 0) + 1
    major = [f for f in findings if any(k in f for k in ("NO_SHALL", "NOT_ATOMIC", "NONCONFORMANT",
                                                          "DUPLICATE", "NO_REQUIREMENTS", "UNKNOWN_SYSTEM",
                                                          "SYSTEM_NAME_HINT"))]  # CAPA-032: hint reaches author
    return {
        "check_id": "SWE1-07",
        "verdict": "PASS" if not major else "FAIL",
        "requirements": len(reqs),
        "pattern_counts": dict(sorted(counts.items())),
        "major_findings": major,
        "minor_findings": [f for f in findings if f not in major],
        "per_requirement": [{"id": r.req_id, "line": r.line, "pattern": r.pattern, "findings": r.findings}
                            for r in reqs],
    }


def check_file(path: Path, systems: set[str] | None = None) -> dict:
    return check_document(path.read_text(encoding="utf-8"), systems)
