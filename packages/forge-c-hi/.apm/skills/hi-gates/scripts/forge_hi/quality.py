"""Deterministic requirement-quality rules (research R4): the IQ/SQ subset that needs no model.

Semantic quality (necessary, correct, feasible, consistent ...) stays with the independent inspector. These rules
only catch what a machine can decide: identity, the single mandatory verb, listed ambiguous terms, a heuristic for
several obligations in one item, the verification method, sources, units on numbers, and rationale for derived items.

Heuristic rules (marked WAIVABLE) may be waived per item through
``attributes.quality_waivers: [{"rule": <code>, "rationale": <text>}]``. The waiver stays visible to the inspector.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from . import gate_result
from .config import REFS, load_project, effective_rigor, stages
from .io import read_json

ID_PREFIX = {"sys-req": ("SYS",), "sw-req": ("SWR", "DRV")}
ID_RE = re.compile(r"^(STK|SYS|SWR|DRV)-[A-Z0-9_]+-[0-9]{3}$")
METHODS = ("test", "analysis", "inspection", "demonstration")
WAIVABLE = {"IQ-03.ambiguous-term", "IQ-05.multiple-obligations", "IQ-11.value-without-unit"}
STOPWORDS = {
    "and", "or", "of", "to", "the", "a", "an", "after", "before", "then", "than", "when", "if", "while", "in", "on",
    "at", "for", "with", "from", "by", "is", "are", "be", "shall",
}
SHALL = re.compile(r"\bshall\b", re.I)
NUMBER = re.compile(r"(?<![\w\-./#])(\d+(?:\.\d+)?)(?:\s*([A-Za-zµ°%/]+))?")


@lru_cache(maxsize=None)
def _lists() -> tuple[tuple[str, ...], frozenset[str], frozenset[str], tuple[str, ...]]:
    doc = read_json(REFS / "ambiguous-terms.json")
    units = frozenset(doc["units"])
    return (
        tuple(sorted(doc["terms"], key=len, reverse=True)),
        units,
        frozenset(u.lower() for u in units),
        tuple(doc["obligation_verbs"]),
    )


def _term_re(term: str) -> re.Pattern:
    body = re.escape(term)
    return re.compile(rf"(?<![\w/-]){body}(?![\w/-])", re.I)


def ambiguous_terms(text: str) -> list[str]:
    terms, *_ = _lists()
    found = []
    for t in terms:
        if _term_re(t).search(text) and not any(t.lower() in f.lower() for f in found):
            found.append(t)
    return found


# Words after which a number is an identifier, not a quantity ("fault code 1", "codes 1 to 7 or 9", "step 3").
ID_CONTEXT = {
    "code", "codes", "id", "ids", "number", "numbers", "no", "item", "items", "step", "steps", "case", "cases",
    "channel", "channels", "pin", "pins", "bit", "version", "rev", "revision", "section", "sections", "table",
    "figure", "class", "classes", "level", "levels", "index", "entry", "slot", "phase", "mode", "modes", "type",
    "option", "priority", "rank", "group", "port", "line", "event", "events", "state", "states",
}
LIST_GLUE = {"to", "and", "or", ","}


def _identifier_number(text: str, start: int) -> bool:
    """True when the number at `start` follows an identifier word, possibly through a list ("codes 1, 4 to 7 or 9")."""
    words = re.findall(r"[A-Za-z]+|\d+(?:\.\d+)?|,", text[:start])[-8:]
    for w in reversed(words):
        lw = w.lower()
        if lw in ID_CONTEXT:
            return True
        if not (lw in LIST_GLUE or w[0].isdigit()):
            return False
    return False


def bare_numbers(text: str) -> list[str]:
    _, units, units_lower, _ = _lists()
    bare = []
    for m in NUMBER.finditer(text):
        unit = m.group(2)
        if _identifier_number(text, m.start()):
            continue
        if unit is None:
            bare.append(m.group(1))
        elif unit in units or unit.lower() in units_lower:
            continue
        elif unit.lower() in STOPWORDS:
            bare.append(m.group(1))
    return bare


def multiple_obligations(text: str) -> bool:
    *_, verbs = _lists()
    m = SHALL.search(text)
    if not m:
        return False
    tail = text[m.end():]
    if re.search(r"\band/or\b", tail, re.I):
        return True
    alt = "|".join(re.escape(v) for v in verbs)
    return bool(re.search(rf"\b(?:and|or)\s+(?:then\s+|also\s+)?(?:shall\s+)?(?:{alt})(?:s|es)?\b", tail, re.I))


def _waived(item: dict) -> set[str]:
    out = set()
    for w in (item.get("attributes") or {}).get("quality_waivers") or []:
        if isinstance(w, dict) and w.get("rule") in WAIVABLE and len(str(w.get("rationale", "")).strip()) >= 15:
            out.add(w["rule"])
    return out


def check_items(
    items: list[dict],
    *,
    stage: str,
    allowed_methods: tuple[str, ...] | list[str] = METHODS,
    other_ids: set[str] | None = None,
) -> list[dict]:
    """All deterministic item and set rules for one requirement set. Returns gate issues."""
    issues: list[dict] = []
    seen: dict[str, int] = {}
    prefixes = ID_PREFIX.get(stage)
    for item in items:
        iid = str(item.get("id", ""))
        seen[iid] = seen.get(iid, 0) + 1
    for iid, n in sorted(seen.items()):
        if n > 1:
            issues.append(gate_result.issue("IQ-12.duplicate-id", f"{iid} is used by {n} items", iid))
        elif other_ids and iid in other_ids:
            issues.append(gate_result.issue("IQ-12.duplicate-id", f"{iid} is already used in another stage", iid))
    for item in items:
        iid = str(item.get("id", ""))
        tid = iid or None
        text = str(item.get("text", ""))
        waived = _waived(item)

        def add(code: str, msg: str) -> None:
            if code not in waived:
                issues.append(gate_result.issue(code, f"{iid or '<no id>'}: {msg}", tid))

        if not ID_RE.match(iid):
            add("IQ-12.id-format", "ID does not match PREFIX-AREA-NNN")
        elif prefixes and iid.split("-", 1)[0] not in prefixes:
            add("IQ-12.id-prefix", f"{stage} IDs start with {' or '.join(prefixes)}")
        n_shall = len(SHALL.findall(text))
        if n_shall == 0:
            add("IQ-11.shall-missing", 'no mandatory "shall"')
        elif n_shall > 1:
            add("IQ-11.shall-multiple", f'{n_shall} "shall" in one requirement; split it')
        terms = ambiguous_terms(text)
        if terms:
            add("IQ-03.ambiguous-term", "ambiguous term(s): " + ", ".join(terms[:6]))
        if n_shall == 1 and multiple_obligations(text):
            add("IQ-05.multiple-obligations", "more than one obligation joined by and/or (heuristic)")
        method = item.get("verification_method")
        if not method:
            add("IQ-06.verification-method-missing", "no verification method")
        elif method not in allowed_methods:
            add("IQ-06.verification-method-not-allowed", f"{method} is not allowed at this level ({list(allowed_methods)})")
        if not item.get("sources"):
            add("IQ-12.source-missing", "no source or upstream reference")
        bare = bare_numbers(text)
        if bare:
            add("IQ-11.value-without-unit", "number(s) without a unit: " + ", ".join(bare[:6]))
        if item.get("derived") is True and not str(item.get("rationale", "")).strip():
            add("IQ-12.rationale-missing", "derived requirement without rationale")
    return issues


def requirement_file(root: Path, stage: str) -> Path:
    return Path(root) / stages()[stage]["outputs"][0]


def run(root: Path, stage: str, *, write: bool = True) -> dict:
    """The `quality` gate for a requirement stage (sys-req, sw-req)."""
    root = Path(root)
    project = load_project(root)
    rigor = effective_rigor(project)
    common = {"profile": rigor["profile"], "integrity_level": rigor["level"], "root": root}
    if stage not in ID_PREFIX:
        doc = gate_result.result("quality", [], not_run_reason=f"no deterministic quality rules for stage {stage}", **common)
    else:
        path = requirement_file(root, stage)
        if not path.is_file():
            doc = gate_result.result("quality", [], not_run_reason=f"{path.relative_to(root)} does not exist", **common)
        else:
            wp = read_json(path)
            other = set()
            for s in ID_PREFIX:
                if s != stage and requirement_file(root, s).is_file():
                    other |= {i.get("id") for i in read_json(requirement_file(root, s)).get("items", [])}
            issues = check_items(
                wp.get("items", []), stage=stage, allowed_methods=rigor.get("verification_methods") or METHODS,
                other_ids=other,
            )
            doc = gate_result.result("quality", issues, evidence=[path], **common)
    if write:
        gate_result.write(root, stage, doc)
    return doc
