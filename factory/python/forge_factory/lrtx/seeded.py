"""LRTX-T021 (LRTX-FR-019, spec acceptance 6): seeded semantic defects on independent frozen holdouts.

    python -m forge_factory.lrtx.seeded --holdout <READY workspace> --model qwen3-coder:30b --out <report.json>

The holdouts are complete work-order workspaces of the Codex/Claude line, for example the rc1 work orders. They are
independent of the local model and of this feature, and they are copied, never modified in place. For each case of
the frozen catalogue:
1. one defect of a named class is seeded into the phase's work products;
2. the phase is re-frozen through the UNCHANGED author gate (a gate rejection is a deterministic detection);
3. otherwise the structured local inspection judges the frozen baseline (an inspection FAIL whose findings name the
   seeded element is a semantic detection; a FAIL on other grounds is recorded as off-target).

The unmutated holdout runs through the same path, so a FAIL there is a false rejection. Deterministic detection,
semantic detection and false rejections are reported separately. The catalogue is versioned and hashed in the report
and is never adjusted to a model's results.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from ..common import pretty_json, sha256_bytes, utc_now

CATALOGUE_VERSION = "lrtx-seeded-3"  # -2 (F011-T045): the paired SWE.1 defects of the inspection lessons; -3 (owner
# 2026-11-02): the paired SWE.1 defects of the detection lessons
LESSON_SET: dict = {"value": None}  # F011-T044: the inspection lesson set of this run (--lessons), in every report
OPTIONS: dict = {"value": None}  # F011-T048/T049: the semantic inspector's sampling and coverage switch, in every report
TRIAL: dict = {"value": None}  # a detection lesson's paired trial arm (knowledge/detection_trial.py), in every report


def _req_md(ws: Path) -> Path:
    return ws / "workproducts/SWE.1/software_requirements.md"


def omit_requirement(ws: Path) -> str:
    """Remove the first requirement that writes a field (statement, source and verification) and its effects."""
    md = _req_md(ws).read_text()
    eff = json.loads((ws / "workproducts/SWE.1/register_effects.json").read_text())
    target = next(e["swr"] for e in eff["effects"] if e.get("op") in ("write", "set", "clear"))
    md = re.sub(rf"^- \*\*{target}\*\*.*\n(?:  - .*\n)*", "", md, count=1, flags=re.M)
    _req_md(ws).write_text(md)
    eff["effects"] = [e for e in eff["effects"] if e["swr"] != target]
    (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps(eff, indent=2))
    return target


def safety_scope_qm(ws: Path) -> str:
    (ws / "safety/software_safety_requirements.md").write_text(
        "# Software safety requirements\n\nQM development scope: no software safety requirements are allocated "
        "(work-order owner decision).\n"
    )
    return "safety/software_safety_requirements.md"


def _effects(ws: Path) -> tuple[Path, dict]:
    p = ws / "workproducts/SWE.1/register_effects.json"
    return p, json.loads(p.read_text())


def contradict_effect(ws: Path) -> str:
    """F011-T045 (paired with the register-effects lesson): the first set/clear entry of the effects contract gets the
    opposite op, or the first written value changes; the requirement text is unchanged, so the two contradict."""
    p, eff = _effects(ws)
    for e in eff["effects"]:
        if e.get("op") in ("set", "clear"):
            e["op"] = "clear" if e["op"] == "set" else "set"
        elif e.get("op") == "write" and isinstance(e.get("value"), int):
            e["value"] ^= 1
        elif e.get("op") == "write" and isinstance(e.get("value"), str) and e["value"].startswith("0x"):
            e["value"] = hex(int(e["value"], 16) ^ 1)
        else:
            continue
        p.write_text(json.dumps(eff, indent=2))
        return e["swr"]
    raise ValueError("NO_MUTATION_SITE:contradict_effect")


def _drop_requirement(ws: Path, swr: str) -> None:
    md = _req_md(ws).read_text()
    _req_md(ws).write_text(re.sub(rf"^- \*\*{swr}\*\*.*\n(?:  - .*\n)*", "", md, count=1, flags=re.M))


def omit_startup(ws: Path) -> str:
    """F011-T045 (paired with the LL failure-handling lesson): the reset/startup requirement is removed."""
    from .review_semantic import STARTUP

    m = STARTUP.search(_req_md(ws).read_text())
    if not m:
        raise ValueError("NO_MUTATION_SITE:omit_startup")
    _drop_requirement(ws, m.group(1))
    return m.group(1)


def unrecord_allocation_gap(ws: Path) -> str:
    """F011-T045 (paired with the recorded-allocation lesson): the Safety allocation row of the upstream gaps goes."""
    p = ws / "traceability/upstream_gaps.md"
    lines = p.read_text().splitlines(keepends=True)
    kept = [x for x in lines if not x.startswith("| Safety allocation |")]
    if len(kept) == len(lines):
        raise ValueError("NO_MUTATION_SITE:unrecord_allocation_gap")
    p.write_text("".join(kept))
    return "Safety allocation"


def omit_budget(ws: Path) -> str:
    """F011-T045 (paired with the budget lesson): the stack budget requirement is removed."""
    from .review_semantic import BYTES, REQ_LINE

    for line in _req_md(ws).read_text().splitlines():
        m = REQ_LINE.match(line)
        if m and re.search(r"\bstack\b", m.group(2), re.I) and BYTES.search(m.group(2)):
            _drop_requirement(ws, m.group(1))
            return m.group(1)
    raise ValueError("NO_MUTATION_SITE:omit_budget")


def _header(ws: Path) -> Path:
    from ..layer import ll_header

    return ws / ll_header(ws)


def invert_behaviour(ws: Path) -> str:
    """The first key/flag write of the driver writes a different documented key (start <-> refresh) or the first set
    becomes a clear: the code still compiles and every trace tag stays in place."""
    h = _header(ws)
    t = h.read_text()
    for a, b in (("0x0000CCCCU", "0x0000AAAAU"), ("0xCCCCU", "0xAAAAU"), ("|=", "&= ~")):
        if a in t:
            h.write_text(t.replace(a, b, 1))
            fn = re.findall(r"\b(LL_\w+)\s*\(", t[: t.index(a)])
            return fn[-1] if fn else a
    raise ValueError("NO_MUTATION_SITE:invert_behaviour")


def comment_out_write(ws: Path) -> str:
    """The first register-array assignment of a function body is commented out (the function becomes a no-op)."""
    from ..layer import register_block

    h = _header(ws)
    t = h.read_text()
    m = re.search(rf"^(\s+)({re.escape(register_block(ws))}\[[^\]]+\]\s*=[^;]+;)", t, re.M)
    if not m:
        raise ValueError("NO_MUTATION_SITE:comment_out_write")
    h.write_text(t[: m.start()] + f"{m.group(1)}/* {m.group(2)} */" + t[m.end() :])
    fn = re.findall(r"\b(LL_\w+)\s*\(", t[: m.start()])
    return fn[-1] if fn else m.group(2)


def vacuous_test(ws: Path) -> str:
    """The first unit-test CHECK condition becomes always true (the id, trace tags and test still exist)."""
    from ..workflow.scaffold import unit_test

    p = ws / unit_test(ws)
    t = p.read_text()
    if p.suffix == ".cpp":  # owner 2026-11-03: every check of the first GoogleTest TEST becomes always true
        h = re.search(r"\bTEST\s*\(\s*\w+\s*,\s*(UT_\d{3})\s*\)\s*\{", t)
        if not h:
            raise ValueError("NO_MUTATION_SITE:vacuous_test")
        end = re.search(r"\n\}", t[h.end():])
        stop = h.end() + (end.start() if end else len(t) - h.end())
        body = re.sub(r"\b(?:EXPECT|ASSERT)_[A-Z_]+\s*\((?:[^;]|\n)*?\)\s*;", "EXPECT_TRUE(1U == 1U);", t[h.end():stop])
        p.write_text(t[: h.end()] + body + t[stop:])
        return h.group(1).replace("_", "-")
    m = re.search(r'CHECK\("(UT-\d+)",\s*(.+?)\);', t, re.S)
    if not m:
        raise ValueError("NO_MUTATION_SITE:vacuous_test")
    p.write_text(t[: m.start()] + f'CHECK("{m.group(1)}", 1U == 1U);' + t[m.end() :])
    return m.group(1)


# lrtx-seeded-3 (owner 2026-11-02, cloud cross-inspection): the SWE.1 defect classes the local inspector missed, paired
# with the PROPOSED detection lessons. Generic synthetic mutations of one requirement each; a holdout without a site for
# a class is NOT_APPLICABLE for it (never forced).
def _req_blocks(md: str) -> list[tuple[str, int, int]]:
    """(SWR id, start, end) of each requirement block (its line and its indented sub-lines)."""
    return [(m.group(1), m.start(), m.end()) for m in
            re.finditer(r"^- \*\*(SWR-\d{3})\*\*.*\n(?:  - .*\n?)*", md, re.M)]


def _statement(block: str) -> str:
    return block.split("\n", 1)[0]


def _write_swrs(ws: Path) -> list[str]:
    _p, eff = _effects(ws)
    return list(dict.fromkeys(e["swr"] for e in eff.get("effects") or [] if e.get("op") in ("write", "set", "clear")))


def _open_point(md: str, swr: str, text: str) -> str:
    op = f"- **OP-{sha256_bytes(f'seeded:{swr}:{text}'.encode())[:16]}** (input scope: {swr}): {text}"
    if re.search(r"^## Open points\s*$", md, re.M):
        return re.sub(r"(^## Open points\s*\n(?:\s*\n)?)", lambda m: m.group(1) + op + "\n", md, count=1, flags=re.M)
    return md.rstrip("\n") + "\n\n## Open points\n\n" + op + "\n"


DOMAIN_CLAUSES = (  # the clause of a value-taking requirement that decides its input domain
    re.compile(r"\s+(?:in|within) (?:the|its) [\w -]*?range(?: (?:of )?[\w.]+ (?:through|to|-) [\w.]+)?", re.I),
    re.compile(r",?\s+(?:masking|masked|confined|truncated|saturated|clamped|limited) (?:it |the value )?to [^.]*", re.I),
    re.compile(r"\s+and discards? (?:all )?(?:requested )?bits above [^.,;]*", re.I),
)
VALUE_TAKING = re.compile(r"\b(?:requested|supplied|caller-supplied|given|argument|parameter)\b", re.I)


def undecided_domain(ws: Path) -> str:
    """S1-DOMAIN: the input-domain clause of the first value-taking write requirement is removed and an open point
    says the handling of out-of-range values (and a minimum value) is undecided."""
    md = _req_md(ws).read_text()
    writes = set(_write_swrs(ws))
    for swr, a, b in _req_blocks(md):
        st = _statement(md[a:b])
        if swr not in writes or not VALUE_TAKING.search(st):
            continue
        new = st
        for rx in DOMAIN_CLAUSES:
            new = rx.sub("", new)
        new = re.sub(r"\bbits [\d:]+ of (the requested value)", r"\1", new)
        if new != st:
            md = md[:a] + md[a:b].replace(st, new, 1) + md[b:]
            _req_md(ws).write_text(_open_point(md, swr, (
                "It is undecided whether a requested value outside the field range is rejected, masked or excluded "
                "by a caller precondition, and which minimum value the driver supports.")))
            return swr
    raise ValueError("NO_MUTATION_SITE:undecided_domain")


def _obligations(ws: Path) -> tuple[dict, dict[str, list[str]]]:
    from ..assurance.owner_obligations import declared, parse

    doc = declared(ws)
    if doc is None:
        raise ValueError("NO_MUTATION_SITE:no owner obligations declared")
    return doc, parse(_req_md(ws).read_text())[0]


def decline_obligation(ws: Path) -> str:
    """S1-OBLDECLINE: an implemented owner obligation (non-critical first) is filed as an obligation gap 'because the
    rules forbid an invented contract'; a requirement that implemented only it is removed with its effects."""
    doc, mapping = _obligations(ws)
    cited = [o for o in sorted(doc["obligations"], key=lambda o: bool(o.get("critical")))
             if any(o["id"] in ids for ids in mapping.values())]
    if not cited:
        raise ValueError("NO_MUTATION_SITE:decline_obligation")
    obl = cited[0]["id"]
    md = _req_md(ws).read_text()
    for swr, ids in mapping.items():
        if obl not in ids:
            continue
        rest = [i for i in ids if i != obl]
        if rest:
            md = re.sub(rf"(^- \*\*{swr}\*\*.*\n(?:  - .*\n)*?)  - Obligations:.*\n",
                        lambda m: m.group(1) + f"  - Obligations: {', '.join(rest)}\n", md, count=1, flags=re.M)
        else:
            md = re.sub(rf"^- \*\*{swr}\*\*.*\n(?:  - .*\n)*", "", md, count=1, flags=re.M)
            p, eff = _effects(ws)
            eff["effects"] = [e for e in eff.get("effects") or [] if e.get("swr") != swr]
            p.write_text(json.dumps(eff, indent=2))
    reason = ("It asserts a behavioural contract the inputs do not establish, and the rules forbid inventing a "
              "contract, so no requirement is written for it.")
    bullet = f"- **{obl}**: {reason}"
    if re.search(r"^## Obligation gaps\s*$", md, re.M):
        md = re.sub(r"(^## Obligation gaps\s*\n(?:\s*\n)?)", lambda m: m.group(1) + bullet + "\n", md, count=1,
                    flags=re.M)
    else:
        md = md.rstrip("\n") + "\n\n## Obligation gaps\n\n" + bullet + "\n"
    _req_md(ws).write_text(md)
    csv_p = ws / "traceability/obligations_to_requirements.csv"
    if csv_p.is_file():
        import csv

        rows = list(csv.reader(io.StringIO(csv_p.read_text())))
        rows = [rows[0]] + [r for r in rows[1:] if r and r[0] != obl] + [[obl, "", reason]]
        out = io.StringIO()
        csv.writer(out, lineterminator="\n").writerows(rows)
        csv_p.write_text(out.getvalue())
    return obl


NARROW = re.compile(r"\b(not|no|never|without)\s+(read or write|read and write|reads or writes|reading or writing|"
                    r"access(?:es|ing)?)\b(?!\s+(?:setup|rights?|control|protection))", re.I)
NARROWED = {"read or write": "write", "read and write": "write", "reads or writes": "writes",
            "reading or writing": "writing", "access": "write", "accesses": "writes", "accessing": "writing"}


def narrow_obligation(ws: Path) -> str:
    """S1-OBLNARROW: a requirement that implements an owner obligation prohibiting accesses is narrowed to prohibit
    writes only; the obligation mapping stays and no gap reason is given."""
    _doc, mapping = _obligations(ws)
    md = _req_md(ws).read_text()
    for swr, a, b in _req_blocks(md):
        st = _statement(md[a:b])
        if mapping.get(swr) and NARROW.search(st):
            new = NARROW.sub(lambda m: f"{m.group(1)} {NARROWED[m.group(2).lower()]}", st, count=1)
            _req_md(ws).write_text(md[:a] + md[a:b].replace(st, new, 1) + md[b:])
            return swr
    raise ValueError("NO_MUTATION_SITE:narrow_obligation")


PRECONDITIONS = (  # a caller precondition that establishes the hardware enabling condition of a write
    re.compile(r"^(- \*\*SWR-\d{3}\*\* )While (?!no )[^,]+, (\w)", re.I),
    re.compile(r",? provided (?:that )?[^,.;]+", re.I),
    re.compile(r",? only (?:when|if|after|once) [^,.;]+", re.I),
    re.compile(r"\s+(?:after|once) the caller has [^,.;]+", re.I),
)


def drop_precondition(ws: Path) -> str:
    """S1-PRECOND: the caller-precondition clause of the first write requirement that has one is deleted."""
    md = _req_md(ws).read_text()
    writes = set(_write_swrs(ws))
    for swr, a, b in _req_blocks(md):
        st = _statement(md[a:b])
        if swr not in writes:
            continue
        for i, rx in enumerate(PRECONDITIONS):
            if rx.search(st):
                new = rx.sub(lambda m: m.group(1) + m.group(2).upper(), st, count=1) if i == 0 else rx.sub("", st,
                                                                                                         count=1)
                _req_md(ws).write_text(md[:a] + md[a:b].replace(st, new, 1) + md[b:])
                return swr
    raise ValueError("NO_MUTATION_SITE:drop_precondition")


def _reset_literal(lit: str, text: str) -> str:
    """The field's reset value when the verification states one, else the zero-initialised register-array contents."""
    m = re.search(r"reset value (?:of \S+ )?\(?(0[xX][0-9A-Fa-f]+[uU]?)", text)
    if m:
        return m.group(1)
    h = re.fullmatch(r"(0[xX])([0-9A-Fa-f]+)([uU]?)", lit)
    return f"{h.group(1)}{'0' * len(h.group(2))}{h.group(3)}" if h else "0U"


def reset_value_verification(ws: Path) -> str:
    """S1-VERIFRESET: the verification of the first caller-value write requirement only checks the field's reset (or
    zero-initialised) value, so an implementation that never writes passes; its effects case is made consistent."""
    md = _req_md(ws).read_text()
    p, eff = _effects(ws)
    cases = {e["swr"]: e for e in eff.get("effects") or [] if e.get("op") == "write" and e.get("value") is not None}
    for swr, a, b in _req_blocks(md):
        block = md[a:b]
        st = _statement(block)
        e = cases.get(swr)
        ver = re.search(r"^  - Verification:.*$", block, re.M)
        if e is None or ver is None or str(e["value"]) in st or not VALUE_TAKING.search(st) or \
                not re.search(r"\bshall write\b", st) or f"{e.get('register')}.{e.get('field')}" not in st:
            continue
        reset = _reset_literal(str(e["value"]), ver.group(0))
        new = (f"  - Verification: Host unit test calls the function of this requirement once with the value {reset} "
               f"on the register array and passes when the written field holds {reset}.")
        md = md[:a] + block.replace(ver.group(0), new, 1) + md[b:]
        _req_md(ws).write_text(md)
        e["value"] = reset if isinstance(e["value"], str) else int(reset.rstrip("uU"), 0)
        for c in e.get("api_calls") or []:
            c["args"] = [int(reset.rstrip("uU"), 0) if isinstance(x, int) else x for x in c.get("args") or []]
        p.write_text(json.dumps(eff, indent=2))
        return swr
    raise ValueError("NO_MUTATION_SITE:reset_value_verification")


PRESERVATION = re.compile(r"\b(?:change|modify|alter)s? only the (?:named|addressed|specified)\b|"
                          r"\bleave (?:the )?(?:remaining|other) bits\b|"
                          r"\bleave every (?:other )?(?:register )?(?:field|bit)s?\b[^.]*\bunchanged\b", re.I)
FIELD_REF = re.compile(r"\b([A-Z][A-Z0-9]*_[A-Z0-9]+)\.([A-Z][A-Z0-9_]*)\b")


def exactly_one_field(ws: Path) -> str:
    """S1-XCUT: the cross-cutting preservation requirement is rewritten as 'exactly one named field changes per call'
    while another requirement of the baseline changes two fields of one register."""
    from .review_semantic import STARTUP

    md = _req_md(ws).read_text()
    _p, eff = _effects(ws)
    per: dict[str, set] = {}
    for e in eff.get("effects") or []:
        if e.get("op") in ("write", "set", "clear"):
            per.setdefault((e["swr"], e.get("register")), set()).add(e.get("field"))
    multi = any(len(f) > 1 for f in per.values())
    for swr, a, b in _req_blocks(md):
        st = _statement(md[a:b])
        regs: dict[str, set] = {}
        for r, f in FIELD_REF.findall(st):
            regs.setdefault(r, set()).add(f)
        multi = multi or (swr in _write_swrs(ws) and any(len(f) > 1 for f in regs.values()))
    if not multi:
        raise ValueError("NO_MUTATION_SITE:exactly_one_field (no requirement changes two fields)")
    for swr, a, b in _req_blocks(md):
        st = _statement(md[a:b])
        if STARTUP.search(st) or not PRESERVATION.search(st) or FIELD_REF.search(st):
            continue  # the rule stated for all functions, not one function's own preservation clause
        subj = re.search(r"\bthe ([^,]+?) shall\b", st)
        if not subj:
            continue
        new = (f"- **{swr}** When writing to a register, the {subj.group(1)} shall change exactly one named field of "
               "that register per call and leave every other bit of that register unchanged.")
        _req_md(ws).write_text(md[:a] + md[a:b].replace(st, new, 1) + md[b:])
        return swr
    raise ValueError("NO_MUTATION_SITE:exactly_one_field (no cross-cutting preservation requirement)")


def neighbour_trace_section(ws: Path) -> str:
    """S1-TRACESEC (optional, paired with the optional trace-section lesson): one requirement's trace row (both trace
    tables, kept consistent) names another source section of the baseline than the one its text and page cite."""
    p = ws / "traceability/upstream_gaps.md"
    if not p.is_file():
        raise ValueError("NO_MUTATION_SITE:neighbour_trace_section")
    t = p.read_text()
    rows = re.findall(r"^\| (SWR-\d{3}) \| ([^|\s]+) \|$", t, re.M)
    ups = list(dict.fromkeys(u for _s, u in rows if not u.upper().startswith("WO-")))
    for swr, up in rows:
        if up not in ups or len(ups) < 2:
            continue
        other = ups[(ups.index(up) + 1) % len(ups)]
        t = re.sub(rf"^\| {swr} \| {re.escape(up)} \|$", f"| {swr} | {other} |", t, count=1, flags=re.M)

        def move(m, swr=swr, up=up, other=other):
            ids = [x.strip() for x in m.group(2).split(",") if x.strip()]
            if m.group(1) == up:
                ids = [x for x in ids if x != swr]
            elif m.group(1) == other and swr not in ids:
                ids = sorted(ids + [swr])
            return f"| {m.group(1)} | {', '.join(ids)} |"
        t = re.sub(r"^\| ([^|\s]+) \| ((?:SWR-\d{3}(?:, )?)+) \|$", move, t, flags=re.M)
        p.write_text(t)
        return swr
    raise ValueError("NO_MUTATION_SITE:neighbour_trace_section")


CATALOGUE = [
    {"id": "S1-OMIT", "phase": "SWE.1", "class": "omitted requirement", "apply": omit_requirement},
    {"id": "S1-QM", "phase": "SWE.1", "class": "safety-scope contradiction", "apply": safety_scope_qm},
    {"id": "S1-EFFECT", "phase": "SWE.1", "class": "effects contract contradicts a requirement", "apply": contradict_effect},
    {
        "id": "S1-NOSTART",
        "phase": "SWE.1",
        "class": "missing reset/startup requirement",
        "apply": omit_startup,
        "alt": "reset_startup_missing",
    },
    {"id": "S1-GAPROW", "phase": "SWE.1", "class": "upstream gap not recorded", "apply": unrecord_allocation_gap},
    {"id": "S1-NOBUDGET", "phase": "SWE.1", "class": "missing resource budget", "apply": omit_budget, "alt": "budget_missing"},
    {"id": "S1-DOMAIN", "phase": "SWE.1", "class": "undecided input domain", "apply": undecided_domain},
    {"id": "S1-OBLDECLINE", "phase": "SWE.1", "class": "owner obligation filed as a gap", "apply": decline_obligation},
    {"id": "S1-OBLNARROW", "phase": "SWE.1", "class": "requirement narrower than its obligation",
     "apply": narrow_obligation},
    {"id": "S1-PRECOND", "phase": "SWE.1", "class": "hardware enabling condition unassigned", "apply": drop_precondition},
    {"id": "S1-VERIFRESET", "phase": "SWE.1", "class": "verification cannot fail", "apply": reset_value_verification},
    {"id": "S1-XCUT", "phase": "SWE.1", "class": "cross-cutting rule contradicts a requirement",
     "apply": exactly_one_field},
    {"id": "S1-TRACESEC", "phase": "SWE.1", "class": "trace row names another section", "apply": neighbour_trace_section},
    {"id": "S3-INVERT", "phase": "SWE.3", "class": "inverted behaviour", "apply": invert_behaviour},
    {"id": "S3-COMMENT", "phase": "SWE.3", "class": "commented-out code", "apply": comment_out_write},
    {"id": "S4-VACUOUS", "phase": "SWE.4", "class": "wrong test property", "apply": vacuous_test},
]


def catalogue_hash() -> str:
    import inspect

    return sha256_bytes(
        "\n".join(
            f"{c['id']}|{c['phase']}|{c['class']}|{c.get('alt', '')}|{inspect.getsource(c['apply'])}" for c in CATALOGUE
        ).encode()
    )


def _refreeze(ws: Path, phase: str) -> dict:
    """Freeze the phase through the unchanged author gate; record its decision (rejection = deterministic catch)."""
    from ..inspection import gate
    from . import tools as T

    if phase == "SWE.4":  # the SWE.4 presence gate needs a run_unit PASS recorded after the code baseline
        T.call(ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", phase)
    old = sys.stdin
    sys.stdin = io.StringIO('{"status":"PASS","artifacts":[],"issues":[],"next_action":"next"}')
    out = io.StringIO()
    try:
        import contextlib

        with contextlib.redirect_stdout(out):
            rc = gate.main(["--workspace", str(ws), "--phase", phase, "--step", "author"])
    finally:
        sys.stdin = old
    log = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    last = [d for d in log if d.get("step") == "author" and d.get("phase") == phase][-1]
    return {"rc": rc, "result": last.get("result"), "issues": (last.get("issues") or [])[:10]}


def _omitted_field(ws: Path) -> str | None:
    """REG.FIELD of the effect omit_requirement removes (read before the mutation; the catalogue is unchanged)."""
    eff = json.loads((ws / "workproducts/SWE.1/register_effects.json").read_text())
    e = next((e for e in eff["effects"] if e.get("op") in ("write", "set", "clear")), None)
    return f"{e['register']}.{e['field']}" if e else None


def evaluate(holdout: Path, case: dict | None, model: str, scratch: Path, inspector: str = "structured") -> dict:
    from importlib import import_module

    review = import_module("forge_factory.lrtx." + {"structured": "review", "semantic": "review_semantic"}[inspector])
    name = case["id"] if case else "BASELINE"
    ws = scratch / name / "workspace"
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(holdout, ws, symlinks=True, ignore=shutil.ignore_patterns("build"))
    for p in (ws / ".forge-run/lrtx").glob("*"):  # no checkpoints from any earlier evaluation
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    manifest_path = ws / ".forge-run/manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        manifest["evaluation_holdout"] = True
        manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    phase = case["phase"] if case else "SWE.1"
    # F011 (2026-10-22): an inspector restricted to existing requirement ids names the uncovered FIELD of an omitted
    # requirement, not its removed id; both count as on target (same rule for every inspector)
    alt = _omitted_field(ws) if case and case["id"] == "S1-OMIT" else (case or {}).get("alt")
    target = case["apply"](ws) if case else None
    rec = {
        "case": name,
        "phase": phase,
        "class": case["class"] if case else "none",
        "target": target,
        "target_field": alt,
        "inspector": inspector,
        "gate": _refreeze(ws, phase),
    }
    if rec["gate"]["result"] not in ("FROZEN", "FROZEN_BY_EVIDENCE", "FROZEN_BY_TOOL_EVIDENCE"):
        rec["detected_by"] = "deterministic gate" if case else "FALSE_REJECTION_BY_GATE"
        return rec
    # F011 (2026-10-22): only an inspection recorded by THIS visit counts. The holdout carries the inspection records
    # of its original run; reading one of those when the local inspector records nothing reported a stale PASS.
    earlier = {q.name for q in (ws / "inspection" / phase).glob("INS-*.json")}
    rep = review.visit(ws, phase, model)
    ins = sorted(q for q in (ws / "inspection" / phase).glob("INS-*.json") if q.name not in earlier)
    rec_ins = json.loads(ins[-1].read_text()) if ins else None
    rec["inspection"] = {
        "reply": rep["status"],
        "verdict": (rec_ins or {}).get("verdict"),
        # run 2 (2026-10-26): the record's top-level findings list is a capped display list (1 entry while SWE1-02 held
        # the on-target claim); every item's findings are authoritative, so on-target is judged on all of them
        "findings": [f"{f.get('id')}: {f.get('detail', '')[:240]}" for f in (rec_ins or {}).get("findings") or []]
        + [f"{iid}: {str(x)[:240]}" for iid, item in sorted(((rec_ins or {}).get("items") or {}).items())
           for x in item.get("findings") or []],
    }
    # detection-lesson promotion (d): what the refuters contested and what the inspector withdrew after them
    lrec = ws / ".forge-run/lrtx" / phase / "inspection-record.json"
    lrec = json.loads(lrec.read_text()) if lrec.is_file() else {}
    rec["inspection"]["contested"] = [f"{i}: {str(x)[:240]}" for i, xs in sorted((lrec.get("contested_findings") or
                                                                                 {}).items()) for x in xs]
    rec["inspection"]["withdrawn"] = [f"{i}: {str(x)[:240]}" for i, xs in sorted((lrec.get("withdrawn_in_repair") or
                                                                                 {}).items()) for x in xs]
    if rep["status"] not in ("PASS", "REWORK"):  # F011-T045 m9: why an inspection recorded nothing
        rec["inspection"]["issues"] = [str(i)[:200] for i in rep.get("issues") or []][:5]
    text = " ".join(rec["inspection"]["findings"])
    on_target = bool(target) and (
        target in text or (target.startswith("SWR-") and re.search(rf"\b{target}\b", text)) or bool(alt and alt in text)
    )
    if rec_ins is None:
        rec["detected_by"] = f"NO_INSPECTION ({rep['status']})"
    elif case is None:
        rec["detected_by"] = "FALSE_REJECTION_BY_INSPECTION" if rec["inspection"]["verdict"] == "FAIL" else "none"
    elif rec["inspection"]["verdict"] == "FAIL":
        rec["detected_by"] = "inspection (on target)" if on_target else "inspection (off target)"
    else:
        rec["detected_by"] = "MISSED"
    return rec


def run(holdouts: list[Path], model: str, out: Path, cases: list[str] | None = None, inspector: str = "structured",
        max_no_inspection: int | None = None) -> dict:
    """max_no_inspection: stop early (summary `aborted`) once more inspections record nothing; repeated invalid answers
    point at the harness, and a run should not spend hours of inference measuring that."""
    rows = []
    with tempfile.TemporaryDirectory(prefix="lrtx-seeded-", dir=out.parent) as td:
        for h in holdouts:
            for case in [None] + [c for c in CATALOGUE if not cases or c["id"] in cases]:
                try:
                    r = evaluate(h, case, model, Path(td) / h.parent.name, inspector)
                except ValueError as exc:  # a holdout without a site for this defect class
                    r = {"case": case["id"] if case else "BASELINE", "detected_by": f"NOT_APPLICABLE ({exc})"}
                rows.append({"holdout": h.parent.name, **r})
                summary = _summary(rows, model)
                if max_no_inspection is not None and summary["no_inspection"] > max_no_inspection:
                    summary["aborted"] = f"NO_INSPECTION_LIMIT: {summary['no_inspection']} > {max_no_inspection}"
                    out.write_text(pretty_json(summary))
                    return summary
                out.write_text(pretty_json(summary))
    return _summary(rows, model)


# F014 (owner 2026-10-26: "place in the run script a deterministic check that, in the fail, returns an error"): before
# any inference, every holdout's clean baseline is inspected with scripted truthful answers. Each question's schema must
# accept its true answer and the adjudication must pass the baseline; otherwise the run is a harness defect.
PREFLIGHT: dict = {"ws": None}


def _truth(ws: Path, p: dict) -> dict:
    """The true answer to one inspector question on a clean baseline, read from its frozen work products."""
    from . import review_semantic as RS

    item = p["task"].split(":")[-1]
    schema = p["output_schema"]
    if item.startswith("step-check-"):  # a judgement check keeps the claim (conservative: never a withdrawal)
        return {"quote": "", "answer": "TRUE"}
    if item.startswith("step-") and not item.startswith("step-behaviour-"):
        facts = RS.baseline_facts(ws)
        q = next(x for x in RS.step_questions(ws, facts) if "step-" + x["id"] == item)
        if q["id"] == "startup":
            return {"quote": "", "answer": facts["startup"][0] if facts["startup"] else "NONE"}
        if q["id"].startswith("startup-"):
            return {"quote": "", "answer": RS.startup_hit(facts, q["field"]) or "NONE"}
        if q["id"].startswith("input-"):
            return {"quote": "", "answer": RS.input_label(q["answers"], q["input"]) or "NONE"}
        if q["id"] == "safety-scope":
            from ..assurance.scope import QM_CLAIM

            doc = ws / RS.SAFETY_DOC
            return {"quote": "", "answer": "QM_CLAIMED" if doc.is_file() and QM_CLAIM.search(doc.read_text())
                    else "ASIL_TARGET_KEPT"}
        if q["id"].startswith("budget-"):
            b = q["row"]
            hit = next((x for x, r in sorted(facts["reqs"].items()) if re.search(rf"\b{b['resource']}\b", r["statement"],
                        re.I) and b["bytes"] in RS._numbers(r["statement"])), "NONE")
            return {"quote": "", "answer": hit}
        e = q["row"]
        return {"quote": "", "answer": e["op"], "value": str(e["value"]) if e["op"] == "write" else ""}
    if item.startswith("step-behaviour-"):  # truthful: the requirement the behaviour rule finds, else NONE
        return {"quote": "", "answer": RS.behaviour_hit(RS.baseline_facts(ws), RS.BEHAVIOURS[item[5:]]) or "NONE"}
    if item == "behaviours":  # truthful scope behaviours of a clean baseline: its own effects entries
        facts = RS.baseline_facts(ws)
        act = {"set": "set", "clear": "clear", "write": "write"}
        enum = schema["properties"]["behaviours"]["items"]["properties"]["register_field"]["enum"]
        # phrases carry the effect's case so the purpose-word path is exercised (run 4 hole: bare phrases never were)
        rows = [{"phrase": f"{e['case'].lower().replace('_', ' ')}: {e['op']} {e['field']}"[:80],
                 "action": act[e["op"]], "register_field": e["field"],
                 "value": str(e["value"]) if e["op"] == "write" and e["value"] is not None else ""}
                for e in RS.effect_entries(ws, facts) if e["field"] in enum]
        # run 5 hole: flag queries ('no_write' entries naming a field) are read behaviours and were never exercised
        raw = json.loads((ws / "workproducts/SWE.1/register_effects.json").read_text()).get("effects") or []
        rows += [{"phrase": f"{e.get('case', '').lower().replace('_', ' ')}: read {e['register']}.{e['field']}"[:80],
                  "action": "read", "register_field": f"{e['register']}.{e['field']}", "value": ""}
                 for e in raw if e.get("op") == "no_write" and e.get("register") and e.get("field")
                 and f"{e['register']}.{e['field']}" in enum]
        return {"behaviours": rows[:16]}
    if item == "coverage":
        return {"behaviours": []}
    if item in ("effects", "budgets"):
        row = schema["properties"]["entries"]["items"]["properties"]
        return {"entries": [{"entry": i, "reason": "stated by the requirement",
                             **({"agrees": True} if item == "effects" else
                                {"covered_by": row["covered_by"]["items"]["enum"][:1]})}
                            for i in row["entry"]["enum"]]}
    offered = schema["properties"]["evidence_checked"]["items"].get("enum") or [x["path"] for x in p["sources"]]
    return {"verdict": "PASS", "claims": [], "evidence_checked": offered[:1]}


def _truthful_call(p: dict, **_k) -> dict:
    from . import structured as S

    doc = _truth(PREFLIGHT["ws"], p)
    return {"doc": doc, "errors": S.validate(doc, p["output_schema"]), "usage": {"prompt_tokens": 0,
            "completion_tokens": 0}, "wall_ms": 0.0, "finish_reason": "stop"}


def preflight(holdouts: list[Path], model: str, scratch: Path, inspector: str) -> dict:
    """Zero model calls: each clean baseline must pass through the unchanged gate and the inspection's adjudication."""
    from . import structured as S

    rows, real = [], S.call
    S.call = _truthful_call
    try:
        for h in holdouts:
            PREFLIGHT["ws"] = scratch / h.parent.name / "BASELINE" / "workspace"
            try:
                r = evaluate(h, None, model, scratch / h.parent.name, inspector)
            except Exception as exc:  # noqa: BLE001 - any crash is the harness defect this check exists to find
                r = {"detected_by": f"HARNESS_ERROR ({type(exc).__name__}: {str(exc)[:200]})"}
            rows.append({"holdout": h.parent.name, "detected_by": r["detected_by"],
                         "issues": (r.get("inspection") or {}).get("issues") or (r.get("inspection") or {}).get("findings")})
    finally:
        S.call, PREFLIGHT["ws"] = real, None
    return {"status": "PASS" if all(r["detected_by"] == "none" for r in rows) else "FAIL", "model_calls": 0,
            "rows": rows}


def _summary(rows: list[dict], model: str) -> dict:
    seeded = [r for r in rows if r["case"] != "BASELINE" and not r["detected_by"].startswith("NOT_APPLICABLE")]
    base = [r for r in rows if r["case"] == "BASELINE"]
    return {
        "schema": "forge-c/lrtx-seeded/1",
        "catalogue": CATALOGUE_VERSION,
        "catalogue_sha256": catalogue_hash(),
        "model": model,
        "inspector": rows[0].get("inspector", "structured") if rows else None,
        "generated_at": utc_now(),
        "deterministic_detection": sum(r["detected_by"] == "deterministic gate" for r in seeded),
        "semantic_detection_on_target": sum(r["detected_by"] == "inspection (on target)" for r in seeded),
        "inspection_fail_off_target": sum(r["detected_by"] == "inspection (off target)" for r in seeded),
        "missed": sum(r["detected_by"] == "MISSED" for r in seeded),
        "seeded": len(seeded),
        "false_rejections": sum(r["detected_by"].startswith("FALSE_REJECTION") for r in base),
        "baselines": len(base),
        "no_inspection": sum(r["detected_by"].startswith("NO_INSPECTION") for r in seeded + base),
        "inspection_lessons": LESSON_SET["value"],
        "inspector_options": OPTIONS["value"],
        **({"trial": TRIAL["value"]} if TRIAL["value"] else {}),
        "rows": rows,
        "note": "Pilot evidence on a small frozen catalogue; not a reliability or safety qualification.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout", type=Path, action="append", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", action="append", default=None)
    ap.add_argument(
        "--inspector",
        choices=("structured", "semantic"),
        default="structured",
        help="semantic: F011 typed claims with deterministic adjudication (SWE.1; other phases structured)",
    )
    ap.add_argument(
        "--lessons",
        type=Path,
        default=None,
        help="F011-T044: inspection lesson directory for the inspector, structured or semantic (recorded in the report)",
    )
    ap.add_argument(
        "--lessons-trial",
        action="store_true",
        help="F011-T045 promotion trial: PROPOSED lessons that pass every check are retrieved too",
    )
    ap.add_argument("--seed", type=int, default=None, help="F011-T048: sampling seed of this run (recorded)")
    ap.add_argument("--no-lessons", action="store_true", help="inspect without any inspection lesson (trial control)")
    ap.add_argument(
        "--coverage",
        choices=("on", "off"),
        default=None,
        help="F011-T049: decomposed coverage questions (default: the profile's structured.inspector_coverage)",
    )
    ap.add_argument(
        "--entries",
        choices=("on", "off"),
        default=None,
        help="F011-T054: per-entry effects and budget questions (default: structured.inspector_entries)",
    )
    ap.add_argument(
        "--stepwise",
        choices=("on", "off"),
        default=None,
        help="F014: one closed temperature-0 question per baseline fact (default: structured.inspector_stepwise)",
    )
    ap.add_argument(
        "--preflight",
        action="store_true",
        help="F014: inspect every clean baseline with scripted truthful answers first (no model call); exit 2 on failure",
    )
    ap.add_argument(
        "--max-no-inspection",
        type=int,
        default=None,
        help="F014: stop (exit 3) once more than this many inspections record nothing",
    )
    a = ap.parse_args(argv)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.inspector == "semantic":
        from . import review_semantic as RS

        RS.INSPECTOR["seed"] = a.seed
        RS.INSPECTOR["coverage"] = None if a.coverage is None else a.coverage == "on"
        RS.INSPECTOR["entries"] = None if a.entries is None else a.entries == "on"
        RS.INSPECTOR["stepwise"] = None if a.stepwise is None else a.stepwise == "on"
        OPTIONS["value"] = RS.inspector_options(a.holdout[0].resolve(), a.model)
    elif a.seed is not None:  # the structured inspector's sampling seed (otherwise the gateway default)
        from . import review as R

        R.INSPECTOR["sampling"] = {"seed": a.seed}
        OPTIONS["value"] = {"sampling": R.INSPECTOR["sampling"]}
    if a.no_lessons:
        from . import review as R

        R.LESSONS["off"] = True
        LESSON_SET["value"] = {"dir": None, "trial": False, "lessons": []}
    elif a.lessons:
        from ..knowledge import inspection as IL
        from . import review as R
        from . import review_semantic as RS

        RS.LESSONS["dir"] = R.LESSONS["dir"] = a.lessons.resolve()
        RS.LESSONS["include_proposed"] = R.LESSONS["include_proposed"] = a.lessons_trial
        LESSON_SET["value"] = {
            "dir": str(a.lessons),
            "trial": a.lessons_trial,
            "lessons": [
                {"id": x.get("id"), "version": x.get("version"), "state": x["_state"], "sha256": x["_hash"]}
                for x in IL.load(a.lessons)
            ],
        }
    holdouts = [h.resolve() for h in a.holdout]
    if a.preflight:
        with tempfile.TemporaryDirectory(prefix="lrtx-preflight-", dir=a.out.parent) as td:
            pf = preflight(holdouts, a.model, Path(td), a.inspector)
        (a.out.parent / (a.out.stem + "-preflight.json")).write_text(pretty_json(pf))
        print(json.dumps({"preflight": pf["status"], "failed": [r for r in pf["rows"] if r["detected_by"] != "none"]}))
        if pf["status"] != "PASS":
            return 2
    s = run(holdouts, a.model, a.out, a.case, a.inspector, a.max_no_inspection)
    print(json.dumps({k: v for k, v in s.items() if k != "rows"}))
    return 3 if s.get("aborted") else 0


if __name__ == "__main__":
    raise SystemExit(main())
