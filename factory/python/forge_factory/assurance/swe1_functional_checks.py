"""Feature 020 T021 (FR-020, FR-021): the deterministic SWE.1 author-gate checks of a functional-level order.

Called by `inspection/gate.py` `step_author` for SWE.1 only when the manifest says `swe1_level: functional`; a
register-level order never reaches it (its register contract checks are unchanged). Reads
`workproducts/SWE.1/requirement_attributes.json` and `software_requirements.md` and checks, per requirement: the
template attributes (contracts/functional-requirement.schema.json via the template config) and the lane's fixed values,
the origin group and its link consistency, the input register (requirement_source inputs only, known locators, derive
rationale), no delivered code as a source, the level rule, EARS, design constraints by inspection and known use cases
(the validators of `lrtx/swe1_functional.py`); then that the markdown states every requirement as recorded. Every
finding is `SWE1_FUNCTIONAL:<SWR id> [<key>] <RULE>: <detail>`."""
from __future__ import annotations

import json
import re
from pathlib import Path

PREFIX = "SWE1_FUNCTIONAL:"


def findings(ws: Path) -> list[str]:
    from ..lrtx import swe1_functional as F

    ws = Path(ws)
    p = ws / F.ATTRS
    if not p.is_file():
        return [f"{PREFIX}ATTRIBUTES_MISSING:{F.ATTRS}"]
    try:
        doc = json.loads(p.read_text())
    except ValueError as exc:
        return [f"{PREFIX}ATTRIBUTES_NOT_JSON:{str(exc)[:120]}"]
    ctx = F.context(ws)
    tpl = ctx["template"]
    out = []
    if doc.get("schema") != F.ATTR_SCHEMA or doc.get("template") != tpl["template_id"]:
        out.append(f"{PREFIX}ATTRIBUTES_SCHEMA: expected schema {F.ATTR_SCHEMA} and template {tpl['template_id']}")
    try:
        origins = {t["id"]: t["origins"] for t in F.plan(ws)}
    except ValueError as exc:
        return out + [f"{PREFIX}{exc}"]
    fixed = dict(tpl["fixed"])
    md = (ws / F.REQS).read_text() if (ws / F.REQS).is_file() else ""
    stated = {m.group(1): m.group(2).strip() for m in re.finditer(r"^\s*-\s*\*\*(SWR-\d{3,})\*\*\s*(.+)$", md, re.M)}
    ids = []
    for r in doc.get("requirements") or []:
        swr, key = r.get("id", "?"), r.get("key", "?")
        ids.append(swr)
        own = {k: v for k, v in r.items() if k not in ("id", "task", *fixed)}
        found = F.requirement_findings(own, origins.get(r.get("task")), ctx)
        found += [("FIXED_ATTRIBUTE", f"{k} is '{r.get(k)}', the lane fixes '{v}'") for k, v in fixed.items()
                  if str(r.get(k)) != str(v)]
        if r.get("task") not in origins:
            found.append(("TASK_UNKNOWN", f"{r.get('task')} is no task of the functional author"))
        if stated.get(swr) != str(r.get("statement", "")).strip():
            found.append(("MARKDOWN_MISMATCH", f"{F.REQS} does not state {swr} as recorded in {F.ATTRS}"))
        out += [f"{PREFIX}{swr} [{key}] {rule}: {detail}" for rule, detail in found]
    if not ids:
        out.append(f"{PREFIX}NO_REQUIREMENTS")
    if ids != [f"SWR-{n:03d}" for n in range(1, len(ids) + 1)]:
        out.append(f"{PREFIX}SWR_NUMBERING: identifiers are SWR-001.. in order")
    out += [f"{PREFIX}{s} MARKDOWN_EXTRA: {s} is not in {F.ATTRS}" for s in stated if s not in ids]
    return out
