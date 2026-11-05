"""CAPA-028/029 (r110) — deterministic SWE.3 unit scaffold for work orders with the owner trace profile.

r110: the SWE.3 design author ran out of tool calls (46 > 45) re-writing unit specifications, per-unit PlantUML
designs and the MISRA statement by hand, and the inspector failed SWE3-04 because no explicit deviation record
existed. Runs between the SWE.3 code authors and the SWE.3 design author and writes, from FACTS only:
  * workproducts/SWE.3/unit_specifications.md skeleton: units/SWC/functions/spec ids taken from the Doxygen @unit/@spec
    tags in the code; existing spec texts and traces are kept; new items carry TODO markers the author must replace
    (the trace gate rejects any TODO);
  * workproducts/SWE.3/detailed_design/<unit>.puml: as-built activity per function derived from the code statements,
    with a 'USPEC: TODO' note the author replaces by the unit's spec ids (checked);
  * workproducts/SWE.3/misra_deviations.md: cppcheck MISRA-subset result, code suppressions and approved deviation
    records (none -> 'no deviations'); MISRA compliance is NOT claimed.
Idempotent: a rerun never overwrites author-written text. CAPA-118: a design the scaffold generated and nobody changed
since (recorded by hash in .forge-run/gates/as-built-designs.json) is re-rendered from the current code on every run, so
a design never stays stale after code rework; a design an author changed is kept.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .swtrace import DESIGN_DIR, UNITS_MD, code_files, developed_swcs, functions_with_docs, parse_units

DEVIATIONS_MD = "workproducts/SWE.3/misra_deviations.md"
AS_BUILT_LOG = ".forge-run/gates/as-built-designs.json"
_CITE_LEGEND = re.compile(r"legend top left\n  Unit specification \(generated from [^\n]*\nendlegend\n")
TODO_TEXT = "TODO: behaviour the unit shall implement"


def _bodies(text: str) -> dict[str, str]:
    """The body text of each function defined in the code (CAPA-119: parsed with its control structure)."""
    return {m.group(1): m.group(2) for m in re.finditer(r"^[A-Za-z_][\w\s\*]*?\b(\w+)\s*\([^;{)]*\)\s*\{(.*?)^\}", text,
                                                         re.S | re.M)}


# CAPA-119 (run WO-F014-CMP-SWE3-IWDG-20261102-08): the as-built design drew 'if' as an ordinary action followed by the
# unconditional branch body (SWU-LL-07..09: 'result = 1U' without the path keeping 0U), and SWE3-06 failed on it.
# Control statements are PlantUML branches/loops with their condition text whole.
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


class _Body:
    """CAPA-119: the statements of a C function body with their control structure (if/else if/else, switch, while,
    for, do-while); conditions and statements are kept whole, whitespace collapsed."""

    def __init__(self, text: str):
        self.s, self.i = _COMMENT.sub(" ", text), 0

    def _ws(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def _kw(self, kw: str) -> bool:
        self._ws()
        if re.match(kw + r"\b", self.s[self.i:]):
            self.i += len(kw)
            return True
        return False

    def _expect(self, ch: str):
        self._ws()
        if not self.s.startswith(ch, self.i):
            raise ValueError(f"expected {ch!r} at {self.i}")
        self.i += 1

    def _scan(self, stop: str) -> str:
        """Text up to `stop` at bracket depth 0 (strings and character literals skipped), `stop` consumed."""
        start, depth = self.i, 0
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in "\"'":
                q, self.i = c, self.i + 1
                while self.i < len(self.s) and self.s[self.i] != q:
                    self.i += 2 if self.s[self.i] == "\\" else 1
            elif c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    if c == stop:
                        break
                    raise ValueError(f"unbalanced {c!r} at {self.i}")
                depth -= 1
            elif c == stop and depth == 0:
                break
            self.i += 1
        if self.i >= len(self.s):
            raise ValueError(f"missing {stop!r}")
        text = " ".join(self.s[start:self.i].split())
        self.i += 1
        return text

    def _cond(self) -> str:
        self._expect("(")
        return self._scan(")")

    def block(self, closing: bool) -> list:
        out = []
        while True:
            self._ws()
            if self.i >= len(self.s):
                if closing:
                    raise ValueError("missing '}'")
                return out
            if self.s[self.i] == "}":
                if not closing:
                    raise ValueError("unbalanced '}'")
                self.i += 1
                return out
            out += self.stmt()

    def stmt(self) -> list:
        self._ws()
        if self.s.startswith("{", self.i):
            self.i += 1
            return self.block(True)
        if self.s.startswith(";", self.i):
            self.i += 1
            return []
        if self._kw("if"):
            arms, other = [(self._cond(), self.stmt())], None
            while self._kw("else"):
                if self._kw("if"):
                    arms.append((self._cond(), self.stmt()))
                else:
                    other = self.stmt()
                    break
            return [("if", arms, other)]
        if self._kw("switch"):
            expr = self._cond()
            self._expect("{")
            cases = []
            while True:
                self._ws()
                if self.s.startswith("}", self.i):
                    self.i += 1
                    break
                if self._kw("case"):
                    cases.append([self._scan(":"), []])
                elif self._kw("default"):
                    self._expect(":")
                    cases.append(["default", []])
                elif not cases:
                    raise ValueError("statement before the first case")
                else:
                    cases[-1][1] += [n for n in self.stmt() if n != ("act", "break")]
            return [("switch", expr, cases)]
        if self._kw("while"):
            return [("while", self._cond(), self.stmt())]
        if self._kw("for"):
            return [("for", self._cond(), self.stmt())]
        if self._kw("do"):
            body = self.stmt()
            if not self._kw("while"):
                raise ValueError("do without while")
            cond = self._cond()
            self._expect(";")
            return [("do", body, cond)]
        text = self._scan(";")
        return [("ret" if re.match(r"return\b", text) else "act", text)]


def _label(text: str) -> str:
    return text.replace('"', "'")


def _emit(nodes: list, out: list, depth: int) -> None:
    for n in nodes:
        kind = n[0]
        if kind in ("act", "ret"):
            out.append(f":{_label(n[1])};")
            if kind == "ret" and depth:
                out.append("stop")
        elif kind == "if":
            for k, (cond, body) in enumerate(n[1]):
                out.append(f"{'if' if k == 0 else 'elseif'} ({_label(cond)}) then (yes)")
                _emit(body, out, depth + 1)
            if n[2] is not None:
                out.append("else (no)")
                _emit(n[2], out, depth + 1)
            out.append("endif")
        elif kind == "switch":
            out.append(f"switch ({_label(n[1])})")
            for label, body in n[2]:
                out.append(f"case ({_label(label)})")
                _emit(body, out, depth + 1)
            out.append("endswitch")
        elif kind == "while":
            out.append(f"while ({_label(n[1])}) is (yes)")
            _emit(n[2], out, depth + 1)
            out.append("endwhile (no)")
        elif kind == "for":
            out.append(f"while (for ({_label(n[1])})) is (next)")
            _emit(n[2], out, depth + 1)
            out.append("endwhile (done)")
        elif kind == "do":
            out.append("repeat")
            _emit(n[1], out, depth + 1)
            out.append(f"repeat while ({_label(n[2])}) is (yes) not (no)")


def _activity(unit_id: str, name: str, fns: list[str], bodies: dict[str, str]) -> str:
    lines = ["@startuml", f"title {unit_id} {name} - as-built activity (generated from the code; refine as needed)",
             "note right", "  USPEC: TODO", "end note"]
    for fn in fns:
        lines += [f"partition {fn} {{", "start"]
        # CAPA-117 (run WO-F014-CMP-SWE3-IWDG-20261102-08): a 110-character cut ended a label mid-identifier
        # ('... & (uint32_t)LL_IWDG_KR_K') and a 20-statement cap dropped the tail of longer functions, so the as-built
        # diagram no longer matched the code (SWE3-06). Every statement is rendered whole.
        body = bodies.get(fn, "")
        try:
            _emit(_Body(body).block(False), lines, 0)
        except ValueError as exc:  # never a partial diagram: the statements as written, marked as not parsed
            lines.append(f"note right: control flow not parsed ({exc}); statements as written")
            lines += [f":{_label(x.rstrip(';'))};" for x in (" ".join(ln.split()) for ln in _COMMENT.sub(" ", body).splitlines())
                      if x and x not in ("{", "}")]
        lines += ["stop", "}"]
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def _generated_form(text: str) -> str:
    """CAPA-118: a design as the scaffold wrote it, without the USPEC citation the gate adds (cite_specs)."""
    return re.sub(r"(?m)^  USPEC: .*$", "  USPEC: TODO", _CITE_LEGEND.sub("", text))


def _render_design(ws: Path, rel: str, text: str) -> bool:
    """CAPA-118 (run WO-F014-CMP-SWE3-IWDG-20261102-08): the as-built design was written only when missing, so the
    baselines frozen after code rework carried the round-1 diagrams and SWE3-06 failed on them. A missing design and
    one still exactly as the scaffold last generated it are (re-)rendered from the current code; an author-changed
    design is kept. Returns whether it was written."""
    from ..common import sha256_bytes

    log_p = ws / AS_BUILT_LOG
    log = json.loads(log_p.read_text()) if log_p.is_file() else {}
    p = ws / rel
    if p.is_file() and log.get(rel) != sha256_bytes(_generated_form(p.read_text(errors="replace")).encode()):
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    log[rel] = sha256_bytes(_generated_form(text).encode())
    log_p.parent.mkdir(parents=True, exist_ok=True)
    log_p.write_text(json.dumps(log, indent=1, sort_keys=True) + "\n")
    return True


def _swc(ws: Path) -> str:
    return developed_swcs(ws)[0]


def scaffold(ws: Path) -> dict:
    ws = Path(ws)
    tags: dict[str, dict] = {}
    bodies: dict[str, str] = {}
    for p in code_files(ws):
        text = p.read_text(errors="replace")
        bodies.update(_bodies(text))
        for fn in functions_with_docs(text):
            for u in fn["units"][:1]:
                t = tags.setdefault(u, {"functions": [], "specs": []})
                if fn["function"] not in t["functions"]:
                    t["functions"].append(fn["function"])
                t["specs"] += [s for s in fn["specs"] if s not in t["specs"]]
    md_p = ws / UNITS_MD
    existing = {u["id"]: u for u in parse_units(md_p.read_text())} if md_p.is_file() else {}
    swc = _swc(ws)
    out = ["# Software unit specifications", "",
           "Skeleton generated by forge_factory.inspection.unit_scaffold from the @unit/@spec tags of the code; the "
           "SWE.3 author replaces every placeholder marker (the trace gate rejects unreplaced markers).", ""]
    for uid in sorted(set(tags) | set(existing)):
        old = existing.get(uid, {})
        t = tags.get(uid, {"functions": [], "specs": []})
        fns = list(dict.fromkeys((old.get("functions") or []) + t["functions"]))
        out += [f"## {uid}: {old.get('name') or ', '.join(fns) or 'TODO: name'}", f"- SWC: {old.get('swc') or swc}",
                f"- Functions: {', '.join(fns)}", f"- Design: {old.get('design') or f'{DESIGN_DIR}/{uid}.puml'}"]
        old_specs = {s["id"]: s for s in old.get("specs") or []}
        for sid in sorted(set(old_specs) | set(t["specs"])):
            s = old_specs.get(sid)
            text = s["text"] if s and s["text"] else TODO_TEXT
            tr = ", ".join(s["swrs"]) if s and s["swrs"] else "TODO"
            out.append(f"- **{sid}** {text} Traces: {tr}")
        out.append("")
        _render_design(ws, old.get("design") or f"{DESIGN_DIR}/{uid}.puml",
                       _activity(uid, old.get("name") or "", fns, bodies))
    md_p.parent.mkdir(parents=True, exist_ok=True)
    md_p.write_text("\n".join(out))
    dev = misra_statement(ws)
    return {"units": sorted(set(tags) | set(existing)), "deviations": dev}


def _justified_lines(ws: Path) -> list[str]:
    """Owner 2026-11-01: findings the SWE.3 author justified instead of fixing (never approved deviations)."""
    p = ws / "workproducts/SWE.3/coding_rule_justifications.json"
    try:
        just = json.loads(p.read_text()).get("justified") or [] if p.is_file() else []
    except ValueError:
        just = []
    return [f"- Findings justified by the author (judged at inspection, NOT approved deviations): {len(just)}" +
            ("" if just else " (none)")] + [f"  - {j.get('rule')} in {j.get('function')}: {j.get('rationale')}"
                                            for j in just]


def misra_statement(ws: Path) -> dict:
    from ..assurance.swe3 import deviation_findings

    res = ws / "evidence/tool-results.jsonl"
    cpp = None
    for line in (res.read_text().splitlines() if res.is_file() else []):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("op") == "cppcheck":
            cpp = r.get("result")
    rec_p = ws / "workproducts/SWE.3/misra_deviations.json"
    records = json.loads(rec_p.read_text()) if rec_p.is_file() else []
    code = {str(p): p.read_text(errors="replace") for p in code_files(ws)}
    unapproved = deviation_findings(code, records)
    m = (cpp or {}).get("metrics") or {}
    lines = ["# MISRA C:2012 deviations (generated from recorded facts)", "",
             f"- cppcheck MISRA addon (subset) result: {(cpp or {}).get('status', 'NOT_RUN')} - "
             f"{m.get('misra_rules_violated', 'n/a')} rules violated, {m.get('general_findings', 'n/a')} general findings",
             f"- Approved deviation records: {len(records)}" + ("" if records else " (none)"),
             f"- Suppressions in code without an approved record: {len(unapproved)}" +
             ("" if unapproved else " (none)"),
             "- Deviations: " + ("; ".join(f"{d.get('rule')} in {d.get('file')} approved by {d.get('approved_by')}"
                                          for d in records) or "none"),
             *_justified_lines(ws),
             "- MISRA C:2012 compliance: NOT CLAIMED (addon subset only; undecidable and unsupported rules need manual "
             "review)", ""]
    p = ws / DEVIATIONS_MD
    p.write_text("\n".join(lines))
    return {"records": len(records), "unapproved": unapproved, "cppcheck": (cpp or {}).get("status", "NOT_RUN")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.inspection.unit_scaffold")
    ap.add_argument("--workspace", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    r = scaffold(a.workspace.resolve())
    print(json.dumps({"units": len(r["units"]), "misra_unapproved": len(r["deviations"]["unapproved"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())


def cite_specs(ws: Path) -> list[str]:
    """CAPA-030 (r111): the design author wrote complete designs but did not cite the unit's USPEC ids, and SWE.3 was
    rejected three times for that alone. The citation is a FACT of unit_specifications.md, so the gate adds it as a
    generated PlantUML legend (or fills the scaffold's 'USPEC: TODO' note) and never changes the design itself."""
    ws = Path(ws)
    md = ws / UNITS_MD
    if not md.is_file():
        return []
    changed = []
    for u in parse_units(md.read_text(errors="replace")):
        ids = [s["id"] for s in u["specs"]]
        p = ws / (u["design"] or f"{DESIGN_DIR}/{u['id']}.puml")
        if not ids or not p.is_file():
            continue
        t = p.read_text(errors="replace")
        if all(i in t for i in ids):
            continue
        cite = ", ".join(ids)
        if "USPEC: TODO" in t:
            t = t.replace("USPEC: TODO", f"USPEC: {cite}")
        else:
            legend = f"legend top left\n  Unit specification (generated from {UNITS_MD}): {cite}\nendlegend\n"
            head = re.search(r"@startuml[^\n]*\n", t)
            t = t[:head.end()] + legend + t[head.end():] if head else legend + t
        p.write_text(t)
        changed.append(u["id"])
    return changed


SYNC_LOG = ".forge-run/gates/trace-sync.jsonl"


def sync_trace(ws: Path) -> dict:
    """CAPA-042 (r129): after code changes in SWE.3 rework, a unit's 'Functions:' list kept functions the code no
    longer has (CODE:UNIT_FUNCTION_NOT_IN_CODE) and missed new ones, costing rework cycles on bookkeeping. The list is
    a FACT of the code: it is set to the functions the code tags '@unit <id>' (only for units the code tags at all).
    Spec items, behaviour text, designs and code are never changed (a spec item rarely names its function, so @spec
    tags stay the author's). Every change is logged in .forge-run/gates/trace-sync.jsonl."""
    from ..common import utc_now

    ws = Path(ws)
    md = ws / UNITS_MD
    if not md.is_file():
        return {"functions": []}
    tagged: dict[str, list[str]] = {}
    for p in code_files(ws):
        for fn in functions_with_docs(p.read_text(errors="replace")):
            for u in fn["units"][:1]:
                tagged.setdefault(u, [])
                if fn["function"] not in tagged[u]:
                    tagged[u].append(fn["function"])
    text = md.read_text(errors="replace")
    units = parse_units(text)
    fn_changes = []
    lines, cur = text.splitlines(keepends=True), None
    for i, line in enumerate(lines):
        h = re.match(r"^##\s+(SWU-(?:LL|HAL)-\d{2,})\b", line)
        if h:
            cur = h.group(1)
            continue
        m = re.match(r"^(\s*[-*]\s*Functions\s*:\s*)(.+?)(\s*)$", line, re.I)
        if cur in tagged and m:
            old = next(u["functions"] for u in units if u["id"] == cur)
            new = [f for f in old if f in tagged[cur]] + [f for f in tagged[cur] if f not in old]
            if new != old:
                lines[i] = m.group(1) + ", ".join(new) + "\n"
                fn_changes.append({"unit": cur, "removed": [f for f in old if f not in new],
                                   "added": [f for f in new if f not in old]})
    if fn_changes:
        md.write_text("".join(lines))
        log = ws / SYNC_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": utc_now(),
                                "functions": fn_changes}) + "\n")
    return {"functions": fn_changes}
