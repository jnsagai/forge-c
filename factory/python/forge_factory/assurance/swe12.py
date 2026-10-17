"""EASA-T024..T031 — stronger SWE.1 and SWE.2 validation (deterministic; AI review findings stay hypotheses).

SWE.1
  * source anchoring: every SWR cites an approved source page; registers/fields it names exist in the RM and are
    mentioned on the cited page (REQ_SOURCE_MISMATCH, REQ_UNKNOWN_REGISTER - "invented register")
  * quality: EARS (existing checker), testable observable, numeric time bounds, no silent assumptions
  * contradictions: two requirements binding the same quantity to different numbers, or setting and clearing the
    same field on the same trigger
  * two-way trace HSI page -> SWR -> test and back
  * owner freeze record (human) bound to the requirements digest
SWE.2
  * architecture graph invariants: no cycles, declared endpoints, layer bypass (HAL writing registers)
  * shared-resource / interrupt ownership must be stated when two functions read-modify-write one register
  * PlantUML semantic consistency: dynamic participants are static components, messages are allocated functions
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from ..common import canonical_json, sha256_bytes, utc_now
from ..inspection.ears import check_document
from ..inspection.swtrace import parse_architecture
from . import hardware
from .policy import _human

REQS = "workproducts/SWE.1/software_requirements.md"
TRACE = "traceability/requirements_to_tests.csv"
ARCH_MD = "workproducts/SWE.2/software_architecture.md"
STATIC = "workproducts/SWE.2/architecture_static.puml"
DYNAMIC = "workproducts/SWE.2/architecture_dynamic.puml"
SECTIONS = "inputs/sections/RM0486"
FIELD_REF = re.compile(r"\b(RCC_[A-Z0-9]+)\.([A-Z][A-Z0-9_]*)\b")
REG_REF = re.compile(r"\b(RCC_[A-Z0-9]+)\b")
ASSUME = re.compile(r"\b(TBD|TBC|to be (defined|confirmed)|assum\w*|if possible|unless otherwise|as needed|etc\.?)\b", re.I)
TIME_WORDS = re.compile(r"\b(wait|timeout|within|bounded|poll\w*|delay|until)\b", re.I)
OBSERVABLE = re.compile(r"\b(RCC_[A-Z0-9]+(\.[A-Z0-9_]+)?|HAL_[A-Z_]+|return\w*|\d+\s*(bytes?|iterations?|ms|us|cycles?))\b",
                        re.I)


def requirements(text: str) -> list[dict]:
    out, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^\s*[-*]?\s*\*\*(SWR-\d{3})\*\*\s*(.+)$", line)
        if m:
            cur = {"id": m.group(1), "text": m.group(2).strip(), "sources": []}
            out.append(cur)
            continue
        s = re.match(r"^\s+[-*]\s*Source:\s*(.+)$", line)
        if s and cur:
            cur["sources"].append(s.group(1).strip())
    return out


def _pages(sections_dir: Path) -> dict[int, str]:
    """RM page number -> text of the sections that start on or span it (source anchors in the section files)."""
    out: dict[int, str] = {}
    for p in sorted(sections_dir.glob("*.md")):
        t = p.read_text(errors="replace")
        for m in re.finditer(r"p\.(\d+)", t[:200]):
            out[int(m.group(1))] = out.get(int(m.group(1)), "") + t
        for m in re.finditer(r"<!-- source: RM0486 p\.(\d+) -->", t):
            out[int(m.group(1))] = out.get(int(m.group(1)), "") + t
    return out


def check_requirements(ws: Path) -> dict:
    ws = Path(ws)
    text = (ws / REQS).read_text(errors="replace") if (ws / REQS).is_file() else ""
    if not text:
        return {"verdict": "FAIL", "major_findings": ["REQ:MISSING"]}
    reqs = requirements(text)
    idx = hardware.index(ws / SECTIONS) if (ws / SECTIONS).is_dir() else {}
    pages = _pages(ws / SECTIONS) if (ws / SECTIONS).is_dir() else {}
    f = [x for x in check_document(text)["major_findings"]]
    for r in reqs:
        rid, t = r["id"], r["text"]
        if not r["sources"]:
            f.append(f"REQ_NO_SOURCE:{rid}")
        if ASSUME.search(t):
            f.append(f"REQ_SILENT_ASSUMPTION:{rid}:{ASSUME.search(t).group(0)}")
        if not OBSERVABLE.search(t):
            f.append(f"REQ_NOT_TESTABLE:{rid}")
        if TIME_WORDS.search(t) and not re.search(r"\d", t) and not re.search(r"\bTIMEOUT_VALUE\b", t):
            f.append(f"REQ_UNBOUNDED_TIME:{rid}")
        if idx:
            for reg, fld in FIELD_REF.findall(t):
                if reg not in idx:
                    f.append(f"REQ_UNKNOWN_REGISTER:{rid}:{reg}")
                elif fld not in idx[reg]["fields"]:
                    f.append(f"REQ_UNKNOWN_FIELD:{rid}:{reg}.{fld}")
            for reg in set(REG_REF.findall(t)) - {x for x, _ in FIELD_REF.findall(t)}:
                if reg not in idx and not reg.endswith("_TIMEOUT_VALUE"):
                    f.append(f"REQ_UNKNOWN_REGISTER:{rid}:{reg}")
        if pages:
            for src in r["sources"]:
                m = re.search(r"RM0486\s+p\.(\d+)", src)
                if m and FIELD_REF.search(t):
                    pg = pages.get(int(m.group(1)), "")
                    if not pg:
                        f.append(f"REQ_SOURCE_PAGE_NOT_IN_INPUTS:{rid}:p.{m.group(1)}")
                    else:
                        for _reg, fld in FIELD_REF.findall(t):
                            if fld not in pg:
                                f.append(f"REQ_SOURCE_MISMATCH:{rid}:{fld} not on p.{m.group(1)}")
    f += contradictions(reqs)
    return {"verdict": "FAIL" if f else "PASS", "major_findings": f, "requirements": len(reqs)}


def contradictions(reqs: list[dict]) -> list[str]:
    out = []
    bound: dict[str, tuple[str, str]] = {}
    for r in reqs:
        for name, val in re.findall(r"\b([A-Z][A-Z0-9_]{3,})\s*=\s*(\d+)", r["text"]):
            if name in bound and bound[name][1] != val:
                out.append(f"REQ_CONTRADICTION:{bound[name][0]},{r['id']}:{name}={bound[name][1]}!={val}")
            bound.setdefault(name, (r["id"], val))
        for unit in ("bytes of flash", "bytes of static RAM", "bytes of stack"):
            m = re.search(rf"(\d+)\s*{unit}", r["text"])
            if m:
                key = unit
                if key in bound and bound[key][1] != m.group(1):
                    out.append(f"REQ_CONTRADICTION:{bound[key][0]},{r['id']}:{unit} {bound[key][1]}!={m.group(1)}")
                bound.setdefault(key, (r["id"], m.group(1)))
    trig: dict[tuple[str, str], tuple[str, str]] = {}
    for r in reqs:
        m = re.match(r"When (.+?), the .+? shall (set|clear) (RCC_[A-Z0-9]+\.[A-Z0-9_]+)", r["text"])
        if m:
            key = (m.group(1).lower(), m.group(3))
            if key in trig and trig[key][1] != m.group(2):
                out.append(f"REQ_CONTRADICTION:{trig[key][0]},{r['id']}:{m.group(3)} set and cleared on the same trigger")
            trig.setdefault(key, (r["id"], m.group(2)))
    return out


def trace_round_trip(ws: Path) -> dict:
    ws = Path(ws)
    reqs = {r["id"]: r for r in requirements((ws / REQS).read_text(errors="replace"))} if (ws / REQS).is_file() else {}
    rows = list(csv.DictReader(io.StringIO((ws / TRACE).read_text()))) if (ws / TRACE).is_file() else []
    f = []
    tested = {r.get("requirement_id", "").strip() for r in rows}
    f += [f"TRACE_REQ_WITHOUT_SOURCE:{k}" for k, r in sorted(reqs.items()) if not r["sources"]]
    f += [f"TRACE_REQ_WITHOUT_TEST:{k}" for k in sorted(reqs) if k not in tested]
    f += [f"TRACE_TEST_FOR_UNKNOWN_REQ:{r.get('test_id')}->{r.get('requirement_id')}" for r in rows
          if r.get("requirement_id", "").strip() not in reqs]
    edges = [("source:" + s, k) for k, r in reqs.items() for s in r["sources"]] + \
            [(r["requirement_id"].strip(), "test:" + r["test_id"].strip()) for r in rows if r.get("test_id")]
    return {"verdict": "FAIL" if f else "PASS", "major_findings": f, "edges": len(edges)}


def requirements_digest(ws: Path) -> str:
    return sha256_bytes((Path(ws) / REQS).read_bytes())


def owner_freeze(store, ws: Path, approver: str, citations_checked: bool) -> str:
    """EASA-T027: a human owner freezes the requirement baseline (digest-bound). Agents cannot."""
    if not _human(approver):
        raise PermissionError("requirements owner freeze needs a human approver")
    rep = check_requirements(ws)
    if rep["verdict"] != "PASS" or not citations_checked:
        raise ValueError(f"cannot freeze: {rep['major_findings'][:3] or ['citations not checked']}")
    return store.append("finding", f"requirements-freeze:{Path(ws).parent.name}",
                        {"code": "OWNER_FROZEN", "digest": requirements_digest(ws), "approved_by": approver,
                         "at": utc_now()}, actor=approver)


def owner_freeze_status(store, ws: Path) -> str:
    cur = store.current("finding", f"requirements-freeze:{Path(ws).parent.name}")
    if not cur:
        return "NOT_FROZEN"
    return "FROZEN" if cur["record"]["digest"] == requirements_digest(ws) else "STALE_FREEZE"


# ---- SWE.2 --------------------------------------------------------------------------------------------------------
def _cycles(edges: list[tuple[str, str]]) -> list[list[str]]:
    g: dict[str, list[str]] = {}
    for a, b in edges:
        g.setdefault(a, []).append(b)
    out, state = [], {}

    def dfs(n: str, path: list[str]) -> None:
        state[n] = 1
        for m in g.get(n, []):
            if state.get(m) == 1:
                out.append(path[path.index(m):] + [m] if m in path else [n, m])
            elif not state.get(m):
                dfs(m, path + [m])
        state[n] = 2
    for n in list(g):
        if not state.get(n):
            dfs(n, [n])
    return out


def check_architecture(ws: Path) -> dict:
    ws = Path(ws)
    st = (ws / STATIC).read_text(errors="replace") if (ws / STATIC).is_file() else ""
    dy = (ws / DYNAMIC).read_text(errors="replace") if (ws / DYNAMIC).is_file() else ""
    md = (ws / ARCH_MD).read_text(errors="replace") if (ws / ARCH_MD).is_file() else ""
    model = parse_architecture(st)
    f = []
    declared = set(re.findall(r"\bas\s+(\w+)", st)) | set(model["swcs"])
    for c in model["interfaces"]:
        for end in (c["from"], c["to"]):
            if end not in declared:
                f.append(f"ARCH_UNDECLARED_ENDPOINT:{end}")
    for cyc in _cycles([(c["from"], c["to"]) for c in model["interfaces"]]):
        f.append("ARCH_CYCLE:" + "->".join(cyc))
    # shared resources / interrupts (AT-029)
    shared = shared_registers(ws)
    if shared and not re.search(r"(shared[- ]resource|interrupt|IRQ|concurren|reentran)", md, re.I):
        f += [f"ARCH_SHARED_RESOURCE_UNOWNED:{r} written by {', '.join(fn)}" for r, fn in sorted(shared.items())]
    if re.search(r"\bIRQ|interrupt handler|_IRQHandler\b", md) and not re.search(r"(IRQ|interrupt)[^.\n]{0,60}\bowner\b",
                                                                              md, re.I):
        f.append("ARCH_IRQ_OWNER_MISSING")
    # PlantUML semantics (AT-029 / T030): dynamic participants must be static elements
    parts = set(re.findall(r"^\s*(?:participant|actor|boundary|control|entity)\s+\"?([\w .]+?)\"?(?:\s+as\s+(\w+))?\s*$",
                           dy, re.M))
    names = {(a or b).strip() for b, a in parts}
    static_names = declared | {lbl for v in model["swcs"].values() for lbl in v} | set(re.findall(r'component\s+"([^"\\]+)', st))
    for n in sorted(names):
        if n.lower() in ("caller", "app", "application", "user", "client", "test"):
            continue
        if not any(n == s or n in s or s in n for s in static_names):
            f.append(f"ARCH_VIEW_INCONSISTENT:dynamic participant {n} not in static view")
    hal = list((ws / "software/hal").glob("*.c")) if (ws / "software/hal").is_dir() else []
    for p in hal:
        if "ll_rcc_regs[" in p.read_text(errors="replace"):
            f.append(f"ARCH_LAYER_BYPASS:{p.name} accesses registers directly")
    return {"verdict": "FAIL" if f else "PASS", "major_findings": f, "shared_registers": {k: v for k, v in shared.items()}}


def shared_registers(ws: Path) -> dict[str, list[str]]:
    """Registers written with read-modify-write by two or more functions (interrupt/concurrency exposure)."""
    ws = Path(ws)
    hdr = ws / "software/ll/stm32n6xx_ll_rcc.h"
    if not hdr.is_file():
        return {}
    text = hdr.read_text(errors="replace")
    defs = {m.group(1): int(m.group(2), 0) for m in hardware.DEFINE.finditer(text)}
    by_word: dict[int, set[str]] = {}
    for fm in re.finditer(r"static\s+inline\s+[\w\s\*]+?\b(LL_RCC_\w+)\s*\([^)]*\)\s*\{(.*?)\n\}", text, re.S):
        for w in hardware.WRITE.finditer(fm.group(2)):
            if w.group(2) in ("|=", "&="):
                word = hardware._eval_index(w.group(1), defs)
                if word is not None:
                    by_word.setdefault(word, set()).add(fm.group(1))
    sections = ws / SECTIONS
    idx = {r["offset"] // 4: n for n, r in hardware.index(sections).items()} if sections.is_dir() else {}
    return {idx.get(w, f"word{w}"): sorted(fns) for w, fns in by_word.items() if len(fns) > 1}


def digest(obj) -> str:
    return sha256_bytes(canonical_json(obj))
