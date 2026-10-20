"""Owner addendum 2026-10-17 (EASA-OR-001..011): SWC structure, unit specifications (ReqIF), Doxygen code trace and
the six traceability matrices — deterministic, no model involvement.

Authored inputs (by the SWE.2-SWE.6 agents):
  SWE.2  workproducts/SWE.2/architecture_static.puml
         * exactly one `<<SWC>>` element per layer component, aliases SWC_LL / SWC_HAL
         * `note ... of SWC_x` containing `Allocated: SWR-001, SWR-002 ...` (allocation stated IN the diagram)
         * every connection labelled with an interface id: `SWC_HAL --> SWC_LL : IF-01 ...`
  SWE.3  workproducts/SWE.3/unit_specifications.md   (`## SWU-HAL-01: <name>`, `- SWC: SWC_HAL`,
         `- Functions: f, g`, `- **USPEC-HAL-01-01** <text> Traces: SWR-001, SWR-003`)
         workproducts/SWE.3/detailed_design/<SWU-id>.puml (one PlantUML design per unit)
         code: a `/** ... @unit SWU-.. @spec USPEC-.. */` Doxygen block before every function definition
  SWE.4  unit tests: `/** @test UT-001 @verifies USPEC-HAL-01-01 */` per test case
  SWE.5  integration tests: `/** @test IT-001 @verifies IF-01 SWC_HAL */` (or `@file ... @verifies` for a whole
         target image)
  SWE.6  Robot tests tagged with their SWR ids
Generated here: unit_specifications/<SWU>.reqif (XSD-validated) and traceability/matrix_<n>_*.csv/.md.
Results come from the executed tool results recorded in the workspace, never from the agents' reports.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

from ..common import data_root
from ..layer import layer_of

ARCH = "workproducts/SWE.2/architecture_static.puml"
ARCH_DOC = "workproducts/SWE.2/software_architecture.md"
UNITS_MD = "workproducts/SWE.3/unit_specifications.md"
UNITS_DIR = "workproducts/SWE.3/unit_specifications"
DESIGN_DIR = "workproducts/SWE.3/detailed_design"
REQS = "workproducts/SWE.1/software_requirements.md"
TRACE_DIR = "traceability"  # SWE.1-owned (requirements_to_tests.csv): matrices are NOT written here
# CAPA-027 (r109): a matrix lives in the folder of the phase that produces it, so it is part of THAT phase's frozen
# baseline; writing into traceability/ changed the SWE.1 baseline and every later freeze failed UPSTREAM_NOT_FROZEN.
MATRIX_DIRS = {1: "workproducts/SWE.2/traceability", 2: "workproducts/SWE.3/traceability",
               3: "workproducts/SWE.3/traceability", 4: "workproducts/SWE.4/traceability",
               5: "workproducts/SWE.5/traceability", 6: "workproducts/SWE.6/traceability"}
DOXY_OUT = "build/doxygen"
SWR_RX = re.compile(r"\bSWR-\d{3}\b")
USPEC_RX = re.compile(r"\bUSPEC-(?:LL|HAL)-\d{2}-\d{2}\b")
SWU_RX = re.compile(r"\bSWU-(?:LL|HAL)-\d{2}\b")
IF_RX = re.compile(r"\bIF-\d{2}\b")
MATRICES = {1: ("swr_to_architecture", ["swr", "swc", "status"]),
            2: ("unitspec_to_swr", ["uspec", "unit", "swc", "swr", "status"]),
            3: ("code_to_unitspec", ["function", "file", "unit", "uspec", "status"]),
            4: ("unittest_to_unitspec", ["test", "file", "uspec", "result", "status"]),
            5: ("integrationtest_to_architecture", ["test", "file", "arch_element", "result", "status"]),
            6: ("validationtest_to_swr", ["test", "swr", "result", "status"])}


def _read(ws: Path, rel: str) -> str:
    p = ws / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def developed_swcs(ws: Path) -> list[str]:
    layer = layer_of(ws)
    return {"LL": ["SWC_LL"], "HAL": ["SWC_HAL"]}.get(layer, ["SWC_LL", "SWC_HAL"])


# CAPA-031 iteration 2 (r120): any limit on a byte quantity is a resource budget, whatever memory it names
# ('4096 bytes of code and constant data', '2 KiB of ROM', 'stack ... at most 128 bytes'), not only flash/RAM/stack
BUDGET_RX = re.compile(r"\b(no more than|at most|not (?:to )?exceed\w*|a maximum of|maximum of)\s+\d+(?:[.,]\d+)?\s*"
                       r"(?:bytes?|KiB|KB|kB|MiB|MB)\b", re.I)


INITIAL_STATE_RX = re.compile(r"^While no\b.{0,80}\bhas been (called|requested)\b.{0,80}\bshall not\b", re.I)


def component_constraints(ws: Path) -> set[str]:
    """CAPA-031 (r113): resource budgets (flash/RAM/stack) constrain the whole SWC; they are verified by measurement
    (SWE.3 tools, SWE.6 'Should Be At Most'), not refined into a software unit.
    CAPA-034 (r116): initial-state invariants ('While no ... has been called ..., shall not write ...') constrain the
    whole SWC too (no start-up code); they are verified by the SWE.4/SWE.6 reset-state tests."""
    return {sid for sid, text in swr_texts(ws).items() if BUDGET_RX.search(text) or INITIAL_STATE_RX.search(text)}


def requirement_ids(ws: Path) -> list[str]:
    md = _read(ws, REQS)
    return sorted(set(re.findall(r"\*\*(SWR-\d{3})\*\*", md)))


# ---- SWE.2 architecture model -------------------------------------------------------------------------------------
def parse_architecture(text: str) -> dict:
    swcs, notes, conns = {}, {}, []
    for m in re.finditer(r'^\s*(?:component\s+"([^"]+)"|\[([^\]]+)\])\s*<<\s*SWC\s*>>\s*as\s+(\w+)', text, re.M):
        swcs.setdefault(m.group(3), []).append((m.group(1) or m.group(2)).replace("\\n", " "))
    for m in re.finditer(r"^\s*note\s+\w+\s+of\s+(\w+)\s*:\s*(.+)$", text, re.M):
        notes.setdefault(m.group(1), []).append(m.group(2))
    for m in re.finditer(r"^\s*note\s+\w+\s+of\s+(\w+)\s*$(.*?)^\s*end\s*note", text, re.M | re.S):
        notes.setdefault(m.group(1), []).append(m.group(2))
    for m in re.finditer(r"^\s*(\w+)\s+([-.]+(?:\([^)]*\))?[-.]*>|<[-.]+)\s+(\w+)\s*(?::\s*(.*))?$", text, re.M):
        conns.append({"from": m.group(1), "to": m.group(3), "label": (m.group(4) or "").strip()})
    alloc = {}
    for swc, ns in notes.items():
        for n in ns:
            # CAPA-026 (r108): an allocation list may wrap over several lines of the note: everything after
            # 'Allocated:' up to the next 'Key:' line (or the end of the note) belongs to it
            for a in re.finditer(r"Allocated\s*:\s*(.*?)(?=^\s*[A-Za-z][\w -]*:\s|\Z)", n, re.I | re.S | re.M):
                alloc.setdefault(swc, set()).update(SWR_RX.findall(a.group(1)))
    return {"swcs": {k: v for k, v in swcs.items()}, "allocation": {k: sorted(v) for k, v in alloc.items()},
            "interfaces": conns}


def check_architecture_model(ws: Path) -> dict:
    text = _read(ws, ARCH)
    if not text:
        return {"verdict": "FAIL", "major_findings": ["ARCH:STATIC_VIEW_MISSING"], "model": {}}
    model = parse_architecture(text)
    f = []
    expected = ["SWC_LL", "SWC_HAL"] if layer_of(ws) in ("HAL", "LL+HAL") else ["SWC_LL"]
    for swc in expected:
        n = len(model["swcs"].get(swc, []))
        if n != 1:
            f.append(f"ARCH:SWC_COUNT:{swc}={n}!=1")
    extra = sorted(set(model["swcs"]) - set(expected))
    if extra:
        f.append("ARCH:LAYER_NOT_SEPARATE:unexpected SWC " + ",".join(extra))
    reqs = requirement_ids(ws)
    dev = developed_swcs(ws)
    allocated = {r for s in dev for r in model["allocation"].get(s, [])}
    f += [f"ARCH:SWR_NOT_ALLOCATED:{r}" for r in reqs if r not in allocated]
    f += [f"ARCH:UNKNOWN_SWR_ALLOCATED:{r}" for s in model["allocation"] for r in model["allocation"][s] if r not in reqs]
    ids = []
    for c in model["interfaces"]:
        m = IF_RX.match(c["label"])
        if not m:
            f.append(f"ARCH:INTERFACE_WITHOUT_ID:{c['from']}->{c['to']}")
        else:
            ids.append(m.group(0))
    f += [f"ARCH:DUPLICATE_INTERFACE_ID:{i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    if not ids:
        f.append("ARCH:NO_INTERFACES")
    return {"verdict": "FAIL" if f else "PASS", "major_findings": f, "model": model}


# ---- SWE.3 unit specifications ------------------------------------------------------------------------------------
def parse_units(text: str) -> list[dict]:
    units, cur = [], None
    for line in text.splitlines():
        h = re.match(r"^##\s+(SWU-(?:LL|HAL)-\d{2})\s*[:\-–]?\s*(.*)$", line)
        if h:
            cur = {"id": h.group(1), "name": h.group(2).strip(), "swc": None, "functions": [], "design": None,
                   "specs": []}
            units.append(cur)
            continue
        if cur is None:
            continue
        kv = re.match(r"^\s*[-*]\s*(SWC|Functions|Design)\s*:\s*(.+)$", line, re.I)
        if kv:
            k, v = kv.group(1).lower(), kv.group(2).strip()
            if k == "swc":
                cur["swc"] = v.split()[0].strip("`")
            elif k == "functions":  # CAPA-031: C identifiers only; prose and parenthesised notes are ignored
                fns = []
                for item in re.sub(r"\([^)]*\)", "", v).split(","):
                    m = re.match(r"\s*`?([A-Za-z_]\w*)`?\s*$", item)
                    if m:
                        fns.append(m.group(1))
                cur["functions"] = fns
            else:
                cur["design"] = v.strip("`")
            continue
        s = re.match(r"^\s*[-*]\s*\*\*(USPEC-[A-Z]+-\d{2}-\d{2})\*\*\s*(.*)$", line)
        if s:
            body = s.group(2)
            tr = re.search(r"Traces?\s*:\s*(.*)$", body, re.I)
            cur["specs"].append({"id": s.group(1), "text": re.sub(r"\s*Traces?\s*:.*$", "", body, flags=re.I).strip(),
                                 "swrs": sorted(set(SWR_RX.findall(tr.group(1)))) if tr else []})
    return units


def _plantuml_jar() -> Path | None:
    jars = sorted((data_root() / "toolchains" / "plantuml").glob("*.jar"))
    return jars[0] if jars else None


def render_ok(puml: Path) -> tuple[bool, str]:
    jar = _plantuml_jar()
    if jar is None or not shutil.which("java"):
        return False, "PLANTUML_NOT_AVAILABLE"
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(jar), "-tsvg", "-failfast2", "-o", td,
                            str(puml)], capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        return True, ""
    # CAPA-033 (r115): 'No diagram found' alone did not tell the author what to fix: add the syntax-check line
    syn = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(jar), "-syntax"], input=puml.read_text(
        errors="replace"), capture_output=True, text=True, timeout=120)
    detail = " ".join(syn.stdout.split())[:120]
    first = puml.read_text(errors="replace").lstrip()[:12]
    hint = "" if first.startswith("@startuml") else " (the file must start with @startuml and end with @enduml)"
    return False, f"{' '.join((r.stderr or r.stdout).split())[:80]}; syntax: {detail}{hint}"


def unit_reqif(unit: dict, swr_text: dict[str, str]) -> str:
    """ReqIF 1.2 for ONE unit: USPEC objects, the SWR objects they refine, 'refines' relations."""
    def _id(*parts: str) -> str:
        return "_" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]

    a, T = quoteattr, "2026-01-01T00:00:00Z"
    dt = _id("DT", "string")
    sot_u, sot_r, srt, st = _id("SOT", "uspec"), _id("SOT", "swr"), _id("SRT", "refines"), _id("ST", unit["id"])
    ad = {k: _id("AD", k) for k in ("ForeignID", "Text", "Unit", "SWC", "rForeignID", "rText")}

    def attr(k: str, name: str) -> str:
        return (f'<ATTRIBUTE-DEFINITION-STRING IDENTIFIER="{ad[k]}" LAST-CHANGE="{T}" LONG-NAME={a(name)}><TYPE>'
                f'<DATATYPE-DEFINITION-STRING-REF>{dt}</DATATYPE-DEFINITION-STRING-REF></TYPE>'
                f'</ATTRIBUTE-DEFINITION-STRING>')

    def val(k: str, v: str) -> str:
        return (f'<ATTRIBUTE-VALUE-STRING THE-VALUE={a(v)}><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>{ad[k]}'
                f'</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>')

    swrs = sorted({r for s in unit["specs"] for r in s["swrs"]})
    objs = [f'<SPEC-OBJECT IDENTIFIER="{_id("SO", s["id"])}" LAST-CHANGE="{T}" LONG-NAME={a(s["id"])}><VALUES>'
            f'{val("ForeignID", s["id"])}{val("Text", s["text"])}{val("Unit", unit["id"])}{val("SWC", unit["swc"] or "")}'
            f'</VALUES><TYPE><SPEC-OBJECT-TYPE-REF>{sot_u}</SPEC-OBJECT-TYPE-REF></TYPE></SPEC-OBJECT>'
            for s in unit["specs"]]
    objs += [f'<SPEC-OBJECT IDENTIFIER="{_id("SWR", r)}" LAST-CHANGE="{T}" LONG-NAME={a(r)}><VALUES>'
             f'{val("rForeignID", r)}{val("rText", swr_text.get(r, ""))}</VALUES><TYPE><SPEC-OBJECT-TYPE-REF>{sot_r}'
             f'</SPEC-OBJECT-TYPE-REF></TYPE></SPEC-OBJECT>' for r in swrs]
    rels = [f'<SPEC-RELATION IDENTIFIER="{_id("SR", s["id"], r)}" LAST-CHANGE="{T}"><SOURCE><SPEC-OBJECT-REF>'
            f'{_id("SO", s["id"])}</SPEC-OBJECT-REF></SOURCE><TARGET><SPEC-OBJECT-REF>{_id("SWR", r)}</SPEC-OBJECT-REF>'
            f'</TARGET><TYPE><SPEC-RELATION-TYPE-REF>{srt}</SPEC-RELATION-TYPE-REF></TYPE></SPEC-RELATION>'
            for s in unit["specs"] for r in s["swrs"]]
    hier = "".join(f'<SPEC-HIERARCHY IDENTIFIER="{_id("SH", s["id"])}" LAST-CHANGE="{T}"><OBJECT><SPEC-OBJECT-REF>'
                   f'{_id("SO", s["id"])}</SPEC-OBJECT-REF></OBJECT></SPEC-HIERARCHY>' for s in unit["specs"])
    title = f"Unit specification {unit['id']} {unit['name']}".strip()
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml"><THE-HEADER>'
            f'<REQ-IF-HEADER IDENTIFIER="{_id("HDR", unit["id"], json.dumps(unit, sort_keys=True))}"><COMMENT>Generated '
            f'deterministically by Forge-C from {UNITS_MD}; the markdown is the source of truth.</COMMENT>'
            f'<CREATION-TIME>{T}</CREATION-TIME><REQ-IF-TOOL-ID>Forge-C swtrace 0.1</REQ-IF-TOOL-ID>'
            '<REQ-IF-VERSION>1.0</REQ-IF-VERSION><SOURCE-TOOL-ID>Forge-C</SOURCE-TOOL-ID>'
            f'<TITLE>{title.replace("&", "&amp;").replace("<", "&lt;")}</TITLE></REQ-IF-HEADER></THE-HEADER>'
            '<CORE-CONTENT><REQ-IF-CONTENT>'
            f'<DATATYPES><DATATYPE-DEFINITION-STRING IDENTIFIER="{dt}" LAST-CHANGE="{T}" LONG-NAME="String" '
            'MAX-LENGTH="4096"/></DATATYPES><SPEC-TYPES>'
            f'<SPEC-OBJECT-TYPE IDENTIFIER="{sot_u}" LAST-CHANGE="{T}" LONG-NAME="Unit Specification Item">'
            f'<SPEC-ATTRIBUTES>{attr("ForeignID", "ReqIF.ForeignID")}{attr("Text", "ReqIF.Text")}{attr("Unit", "Unit")}'
            f'{attr("SWC", "SWC")}</SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE>'
            f'<SPEC-OBJECT-TYPE IDENTIFIER="{sot_r}" LAST-CHANGE="{T}" LONG-NAME="Software Requirement">'
            f'<SPEC-ATTRIBUTES>{attr("rForeignID", "ReqIF.ForeignID")}{attr("rText", "ReqIF.Text")}</SPEC-ATTRIBUTES>'
            f'</SPEC-OBJECT-TYPE>'
            f'<SPEC-RELATION-TYPE IDENTIFIER="{srt}" LAST-CHANGE="{T}" LONG-NAME="refines"/>'
            f'<SPECIFICATION-TYPE IDENTIFIER="{st}" LAST-CHANGE="{T}" LONG-NAME="Unit Specification"/></SPEC-TYPES>'
            f'<SPEC-OBJECTS>{"".join(objs)}</SPEC-OBJECTS>'
            + (f'<SPEC-RELATIONS>{"".join(rels)}</SPEC-RELATIONS>' if rels else "")
            + f'<SPECIFICATIONS><SPECIFICATION IDENTIFIER="{_id("SPEC", unit["id"])}" LAST-CHANGE="{T}" '
            f'LONG-NAME={a(unit["id"])}><TYPE><SPECIFICATION-TYPE-REF>{st}</SPECIFICATION-TYPE-REF></TYPE>'
            f'<CHILDREN>{hier}</CHILDREN></SPECIFICATION></SPECIFICATIONS></REQ-IF-CONTENT></CORE-CONTENT></REQ-IF>\n')


def swr_texts(ws: Path) -> dict[str, str]:
    out = {}
    for m in re.finditer(r"\*\*(SWR-\d{3})\*\*\s*(.+)", _read(ws, REQS)):
        out[m.group(1)] = m.group(2).strip()
    return out


def check_units(ws: Path, arch_model: dict | None = None, render: bool = True, export: bool = True) -> dict:
    text = _read(ws, UNITS_MD)
    if not text:
        return {"verdict": "FAIL", "major_findings": ["UNIT:SPECIFICATION_MISSING"], "units": []}
    units = parse_units(text)
    model = arch_model if arch_model is not None else parse_architecture(_read(ws, ARCH))
    reqs = set(requirement_ids(ws))
    dev = developed_swcs(ws)
    f = []
    if not units:
        f.append("UNIT:NO_UNITS")
    ids = [u["id"] for u in units]
    f += [f"UNIT:DUPLICATE_UNIT:{i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    specs = [s["id"] for u in units for s in u["specs"]]
    f += [f"UNIT:DUPLICATE_SPEC:{i}" for i in sorted({i for i in specs if specs.count(i) > 1})]
    texts = swr_texts(ws)
    # CAPA-028: the scaffold's placeholder markers must all be replaced by the author
    f += [f"UNIT:SPEC_TODO:{s['id']}" for u in units for s in u["specs"] if "TODO" in s["text"]]
    f += [f"UNIT:UNIT_TODO:{u['id']}" for u in units if "TODO" in u["name"]]
    for u in units:
        if u["swc"] not in dev:
            f.append(f"UNIT:SWC_NOT_DEVELOPED_HERE:{u['id']}:{u['swc']}")
        if not u["specs"]:
            f.append(f"UNIT:NO_SPEC_ITEMS:{u['id']}")
        if not u["functions"]:
            f.append(f"UNIT:NO_FUNCTIONS:{u['id']}")
        allocated = set(model.get("allocation", {}).get(u["swc"], []))
        for s in u["specs"]:
            if not s["id"].startswith(u["id"].replace("SWU", "USPEC") + "-"):
                f.append(f"UNIT:SPEC_ID_NOT_OF_UNIT:{s['id']}")
            if not s["swrs"]:
                f.append(f"UNIT:SPEC_WITHOUT_TRACE:{s['id']}")
            for r in s["swrs"]:
                if r not in reqs:
                    f.append(f"UNIT:UNKNOWN_SWR:{s['id']}:{r}")
                elif r not in allocated:
                    f.append(f"UNIT:SPEC_TRACES_UNALLOCATED_SWR:{s['id']}:{r}->{u['swc']}")
        design = ws / (u["design"] or f"{DESIGN_DIR}/{u['id']}.puml")
        if not design.is_file():
            f.append(f"UNIT:DESIGN_MISSING:{u['id']}")
        else:
            dt = design.read_text(errors="replace")
            if "@startuml" not in dt or u["id"] not in dt:
                f.append(f"UNIT:DESIGN_NOT_OF_UNIT:{u['id']}")
            missing_fn = [fn for fn in u["functions"] if fn not in dt]
            if missing_fn:
                f.append(f"UNIT:DESIGN_OMITS_FUNCTION:{u['id']}:{','.join(missing_fn[:3])}")
            if "TODO" in dt:
                f.append(f"UNIT:DESIGN_TODO:{u['id']}")
            missing_spec = [s["id"] for s in u["specs"] if s["id"] not in dt]
            if missing_spec:  # the design is traceable to the unit specification it realises
                f.append(f"UNIT:DESIGN_MISSING_SPEC_REF:{u['id']}:{','.join(missing_spec[:3])}")
            if render:
                ok, why = render_ok(design)
                if not ok:
                    f.append(f"UNIT:DESIGN_RENDER_FAILED:{u['id']}:{why[:80]}")
    refined = {r for u in units for s in u["specs"] for r in s["swrs"]}
    allocated_dev = {r for s in dev for r in model.get("allocation", {}).get(s, [])}
    comp = component_constraints(ws)
    f += [f"UNIT:SWR_NOT_REFINED:{r} (allocated to {', '.join(dev)} but no unit-spec item traces it: add 'Traces: {r}' "
          "to the USPEC item(s) of the unit that implements it)" for r in sorted(allocated_dev & reqs)
          if r not in refined and r not in comp]  # CAPA-034: actionable
    from ..layer import layer_of, ll_tu, ll_tu_text

    tu = ws / ll_tu(ws)
    if layer_of(ws) == "LL" and tu.is_file() and tu.read_text(errors="replace") != ll_tu_text(ws):
        f.append(f"CODE:GENERATED_UNIT_MODIFIED:{ll_tu(ws)}")  # CAPA-031: the generated compile unit is not authored code
    exported = []
    if export and units:
        from .reqif_export import validate as reqif_validate

        d = ws / UNITS_DIR
        d.mkdir(parents=True, exist_ok=True)
        for u in units:
            p = d / f"{u['id']}.reqif"
            p.write_text(unit_reqif(u, texts), encoding="utf-8")
            v = reqif_validate(p)
            exported.append({"unit": u["id"], "file": p.relative_to(ws).as_posix(), "verdict": v["verdict"],
                             "spec_objects": v["spec_objects"]})
            f += [f"UNIT:REQIF_INVALID:{u['id']}:{i}" for i in v["issues"][:2]]
    return {"verdict": "FAIL" if f else "PASS", "major_findings": f, "units": units, "reqif": exported}


# ---- SWE.3 code documentation (Doxygen) ---------------------------------------------------------------------------
FUNC_RX = re.compile(r"^(?:static\s+)?(?:inline\s+)?(?:static\s+)?[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*\(([^;{)]*)\)\s*\{",
                     re.M)


def code_files(ws: Path) -> list[Path]:
    layer = layer_of(ws)
    pats = ["software/ll/*.h"] if layer == "LL" else (["software/hal/*.c", "software/hal/*.h"] if layer == "HAL" else
                                                       ["software/ll/*.h", "software/hal/*.c", "software/hal/*.h"])
    return sorted({p for pat in pats for p in ws.glob(pat) if p.is_file()})


def functions_with_docs(text: str) -> list[dict]:
    out = []
    for m in FUNC_RX.finditer(text):
        name = m.group(1)
        if name in ("if", "while", "for", "switch", "return", "sizeof"):
            continue
        before = text[:m.start()].rstrip()
        doc = None
        if before.endswith("*/"):
            start = before.rfind("/**")
            plain = before.rfind("/*")
            if start != -1 and start >= plain:
                doc = before[start:]
        out.append({"function": name, "line": text.count("\n", 0, m.start()) + 1, "doc": doc,
                    "units": SWU_RX.findall(re.search(r"[@\\]unit\b([^\n]*)", doc).group(1)) if doc and
                    re.search(r"[@\\]unit\b", doc) else [],
                    "specs": sorted(set(USPEC_RX.findall(" ".join(re.findall(r"[@\\]spec\b([^\n]*)", doc))))) if doc
                    else []})
    return out


def run_doxygen(ws: Path, files: list[Path]) -> dict:
    from ..layer import profile

    prof = profile(ws)
    exe = shutil.which("doxygen")
    if exe is None:
        return {"status": "NOT_AVAILABLE", "warnings": [], "version": None}
    out = ws / DOXY_OUT
    out.mkdir(parents=True, exist_ok=True)
    cfg = "\n".join([
        f'PROJECT_NAME = "Forge-C {prof["register_prefix"]} driver"', f"OUTPUT_DIRECTORY = {out}",
        "INPUT = " + " ".join(str(f) for f in files),
        "FILE_PATTERNS = *.c *.h", "EXTRACT_ALL = NO", "EXTRACT_STATIC = YES", "WARN_IF_UNDOCUMENTED = YES",
        "WARN_IF_DOC_ERROR = YES", "WARN_NO_PARAMDOC = NO", "QUIET = YES", "GENERATE_LATEX = NO", "GENERATE_HTML = YES",
        # CAPA-030 (r111): preprocessing ON (documented #defines warned with NO), macros not expanded
        "GENERATE_XML = YES", "OPTIMIZE_OUTPUT_FOR_C = YES", "ENABLE_PREPROCESSING = YES", "MACRO_EXPANSION = NO",
        'ALIASES = "unit=\\xrefitem unit \\"Software unit\\" \\"Software units\\"" '
        '"spec=\\xrefitem spec \\"Unit specification\\" \\"Unit specification items\\"" '
        '"verifies=\\xrefitem verifies \\"Verifies\\" \\"Verification links\\"" '
        '"trace=\\xrefitem trace \\"Traces to\\" \\"Requirement traces\\""', ""])
    (out / "Doxyfile").write_text(cfg, encoding="utf-8")
    r = subprocess.run([exe, str(out / "Doxyfile")], capture_output=True, text=True, timeout=300, cwd=out)
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    d = re.escape(prof["ll"]["function_prefix"])
    gen = re.compile(rf"Member ({d}[A-Z0-9]+_(OFFSET|[A-Z0-9]+_(POS|MSK))|{d}REG_COUNT|{d}BASE) \(macro definition\)")
    # register definitions are GENERATED by inspection/regmap.py from RM0486 (agents may not edit them) and verified
    # against the RM twice; the owner requirement documents functions/units, so only their warnings are dropped
    warns = [ln.replace(str(ws) + "/", "") for ln in (r.stderr or "").splitlines()
             if "warning" in ln.lower() and not gen.search(ln)]
    return {"status": "PASS" if r.returncode == 0 else "FAIL", "warnings": warns, "version": ver}


def check_code(ws: Path, units: list[dict] | None = None, doxygen: bool = True) -> dict:
    units = units if units is not None else parse_units(_read(ws, UNITS_MD))
    from ..brownfield import is_brownfield, manifest_of

    if is_brownfield(manifest_of(ws)):  # feature 008: delivered code carries no tags; the trace map replaces them
        from ..brownfield.trace import check_code as delivered_code_trace

        return delivered_code_trace(ws, units)
    by_unit = {u["id"]: u for u in units}
    spec_unit = {s["id"]: u["id"] for u in units for s in u["specs"]}
    f, rows = [], []
    files = code_files(ws)
    if not files:
        f.append("CODE:NO_SOURCES")
    for p in files:
        for fn in functions_with_docs(p.read_text(errors="replace")):
            rel = p.relative_to(ws).as_posix()
            if not fn["doc"] or not fn["units"] or not fn["specs"]:
                f.append(f"CODE:UNDOCUMENTED_FUNCTION:{fn['function']}@{rel}:{fn['line']}")
                rows.append({"function": fn["function"], "file": rel, "unit": "", "uspec": "", "status": "UNTRACED"})
                continue
            u = fn["units"][0]
            if len(fn["units"]) != 1 or u not in by_unit:
                f.append(f"CODE:UNKNOWN_UNIT_REF:{fn['function']}:{','.join(fn['units'])}")
            elif fn["function"] not in by_unit[u]["functions"]:
                f.append(f"CODE:FUNCTION_UNIT_MISMATCH:{fn['function']}:{u}")
            for s in fn["specs"]:
                if spec_unit.get(s) is None:
                    f.append(f"CODE:UNKNOWN_SPEC_REF:{fn['function']}:{s}")
                elif spec_unit[s] != u:
                    f.append(f"CODE:SPEC_OF_OTHER_UNIT:{fn['function']}:{s}")
                rows.append({"function": fn["function"], "file": rel, "unit": u, "uspec": s,
                             "status": "TRACED" if spec_unit.get(s) == u else "INVALID"})
    referenced = {r["uspec"] for r in rows if r["status"] == "TRACED"}
    fns_of = {u["id"]: u["functions"] for u in units}
    # CAPA-033 (r115): name the unit and the functions whose @spec line should carry the missing item
    f += [f"CODE:SPEC_NOT_IMPLEMENTED:{s} (add {s} to the @spec line of the {spec_unit[s]} function(s) implementing "
          f"it: {', '.join(fns_of.get(spec_unit[s], [])[:6]) or 'none listed'})" for s in sorted(spec_unit)
          if s not in referenced]
    for u in units:
        for fn in u["functions"]:
            if not any(r["function"] == fn for r in rows):
                f.append(f"CODE:UNIT_FUNCTION_NOT_IN_CODE:{u['id']}:{fn}")
    dox = run_doxygen(ws, files) if doxygen and files else {"status": "NOT_RUN", "warnings": []}
    f += [f"CODE:DOXYGEN_WARNING:{w[:120]}" for w in dox["warnings"][:10]]
    if dox["status"] == "FAIL":
        f.append("CODE:DOXYGEN_FAILED")
    return {"verdict": "FAIL" if f else "PASS", "major_findings": f, "rows": rows, "doxygen": dox}


# ---- executed results ---------------------------------------------------------------------------------------------
def _tool_records(ws: Path) -> list[dict]:
    for p in (ws / "evidence" / "tool-results.jsonl", ws / "verification" / "tool-results.jsonl"):
        if p.is_file():
            out = []
            for line in p.read_text(errors="replace").splitlines():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
            return out
    return []


def _raw(ws: Path, ref: str) -> Path | None:
    """The content-addressed raw output; a file whose bytes no longer match its address is not evidence."""
    h = ref.rsplit(":", 1)[-1]
    for d in (ws / "evidence" / "raw", ws / "evidence-raw"):
        c = sorted(d.glob(f"{h}*")) if d.is_dir() else []
        if c:
            return c[0] if hashlib.sha256(c[0].read_bytes()).hexdigest() == h else None
    return None


def latest_run(ws: Path, op: str) -> dict | None:
    recs = [r for r in _tool_records(ws) if r.get("op") == op]
    if not recs:
        return None
    r = recs[-1]["result"]
    raws = [p for p in (_raw(ws, a) for a in r.get("artifact_refs") or []) if p is not None]
    return {"status": r.get("status"), "raw": raws}


def documented_interfaces(ws: Path) -> list[str]:
    """CAPA-036 (r119): interface ids the frozen architecture DOCUMENT defines (first cell of an interface-table row,
    '| IF-01 | LL_RCC_HSI_Enable | ...'). Both frozen SWE.2 views are the architecture design; r119's SWE.5 stopped
    STUCK because tests citing the per-function interfaces IF-01..IF-18 of the document were 'unknown'."""
    p = ws / ARCH_DOC
    text = p.read_text(errors="replace") if p.is_file() else ""
    return sorted(set(re.findall(r"^\s*\|\s*(IF-\d{2})\s*\|", text, re.M)))


def check_results(raws: list[Path]) -> dict[str, str]:
    """'<ID> PASS|FAIL' lines of self-checking host programs: per test id (sub-ids like UT-003b or IT-005-ADC12_EN count
    for their test; any failing sub-check fails the test). CAPA-035 (r117): '_' in a sub-id hid every check of IT-005
    and IT-006, so Matrix 5 reported them NOT_RUN although all 17 checks had passed."""
    res: dict[str, str] = {}
    for p in raws:
        if p.suffix not in (".log", ".txt"):
            continue
        for m in re.finditer(r"^\s*([A-Z]{2,4}-\d{3})([\w-]*)\s+(PASS|FAIL)\b", p.read_text(errors="replace"), re.M):
            tid, ok = m.group(1), m.group(3)
            if res.get(tid) != "FAIL":
                res[tid] = ok
    return res


def robot_results(raws: list[Path]) -> dict[str, dict]:
    out = {}
    for p in raws:
        if p.suffix != ".xml":
            continue
        try:
            root = ET.parse(p).getroot()  # noqa: S314 - output.xml of the local, sandboxed robot run (content-addressed)
        except ET.ParseError:
            continue
        if root.tag != "robot":
            continue
        for t in root.iter("test"):
            st = t.find("status")
            out[t.get("name")] = {"status": st.get("status") if st is not None else "UNKNOWN",
                                  "tags": [x.text for x in t.iter("tag")]}
    return out


def tagged_tests(files: list[Path], ws: Path) -> list[dict]:
    out = []
    for p in files:
        text = p.read_text(errors="replace")
        rel = p.relative_to(ws).as_posix()
        for m in re.finditer(r"/\*\*(.*?)\*/", text, re.S):
            body = m.group(1)
            t = re.search(r"[@\\]test\s+([A-Z]{2,4}-\d{3})", body)
            v = re.search(r"[@\\]verifies\s+([^\n@]*)", body)
            fileblk = re.search(r"[@\\]file\b", body)
            if t or (fileblk and v):
                out.append({"test": t.group(1) if t else f"FILE:{p.name}", "file": rel,
                            "verifies": re.findall(r"[A-Z][A-Z_]*[A-Z]-[A-Z0-9-]+|SWC_[A-Z]+", v.group(1)) if v else [],
                            "file_level": not t})
    return out


# ---- matrices -----------------------------------------------------------------------------------------------------
def write_matrix(ws: Path, n: int, rows: list[dict], uncovered: list[str], write: bool = True) -> dict:
    name, cols = MATRICES[n]
    if not write:
        return {"matrix": n, "file": f"{MATRIX_DIRS[n]}/matrix_{n}_{name}.csv", "rows": len(rows), "uncovered": uncovered,
                "written": False}
    d = ws / MATRIX_DIRS[n]
    d.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: tuple(str(r.get(c, "")) for c in cols))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    (d / f"matrix_{n}_{name}.csv").write_text(buf.getvalue(), encoding="utf-8")
    md = [f"# Traceability matrix {n}: {name.replace('_', ' ')}", "",
          "Generated deterministically by forge_factory.inspection.swtrace from the work products and executed "
          "results; not authored by an agent.", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
    md += ["", f"Uncovered items: {', '.join(uncovered) if uncovered else 'none'}", ""]
    (d / f"matrix_{n}_{name}.md").write_text("\n".join(md), encoding="utf-8")
    return {"matrix": n, "file": f"{MATRIX_DIRS[n]}/matrix_{n}_{name}.csv", "rows": len(rows), "uncovered": uncovered}


PHASE_MATRICES = {"SWE.2": {1}, "SWE.3": {2, 3}, "SWE.4": {4}, "SWE.5": {5}, "SWE.6": {6}}


def build_all(ws: Path, *, render: bool = True, doxygen: bool = True, upto: str = "SWE.6",
              write: set[int] | None = None, export: bool = True) -> dict:
    """Run every relation available up to phase `upto`, write the matrices in `write` (default all), return findings
    per relation. A phase gate writes only its own matrices: earlier ones belong to frozen baselines."""
    ws = Path(ws)

    def w(n: int) -> bool:
        return write is None or n in write

    order = ["SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
    k = order.index(upto)
    reqs = requirement_ids(ws)
    rep: dict = {"matrices": [], "findings": {}}
    arch = check_architecture_model(ws)
    rep["findings"]["SWE.2"] = arch["major_findings"]
    model = arch.get("model") or {"swcs": {}, "allocation": {}, "interfaces": []}
    rows1 = [{"swr": r, "swc": s, "status": "ALLOCATED"} for s, rs in model["allocation"].items() for r in rs]
    allocated = {r["swr"] for r in rows1}
    rows1 += [{"swr": r, "swc": "", "status": "NOT_ALLOCATED"} for r in reqs if r not in allocated]
    rep["matrices"].append(write_matrix(ws, 1, rows1, [r for r in reqs if r not in allocated], write=w(1)))
    if k < 1:
        return rep
    u = check_units(ws, model, render=render, export=export)
    c = check_code(ws, u["units"], doxygen=doxygen)
    rep["findings"]["SWE.3"] = u["major_findings"] + c["major_findings"]
    rows2 = [{"uspec": s["id"], "unit": x["id"], "swc": x["swc"], "swr": r, "status": "TRACED"}
             for x in u["units"] for s in x["specs"] for r in s["swrs"]]
    refined = {r["swr"] for r in rows2}
    dev_alloc = sorted({r for s in developed_swcs(ws) for r in model["allocation"].get(s, [])})
    comp = component_constraints(ws)
    rows2 += [{"uspec": "", "unit": "", "swc": "", "swr": r,
               "status": "COMPONENT_LEVEL" if r in comp else "NOT_REFINED"} for r in dev_alloc if r not in refined]
    rep["matrices"].append(write_matrix(ws, 2, rows2, [r for r in dev_alloc if r not in refined and r not in comp],
                                        write=w(2)))
    rep["matrices"].append(write_matrix(ws, 3, c["rows"], [f.split(":", 2)[2] for f in c["major_findings"]
                                                          if f.startswith("CODE:SPEC_NOT_IMPLEMENTED")], write=w(3)))
    specs = sorted({s["id"] for x in u["units"] for s in x["specs"]})
    if k >= 2:
        run = latest_run(ws, "run_unit")
        res = check_results(run["raw"]) if run else {}
        tests = tagged_tests(sorted(ws.glob("software/tests/unit/*.c")), ws)
        rows4, f4 = [], []
        for t in tests:
            if not t["verifies"]:
                f4.append(f"UT:TEST_WITHOUT_TRACE:{t['test']}")
            if run is not None and t["test"] not in res:  # CAPA-039 (r126): checks printed under other ids
                f4.append(f"UT:TEST_NOT_OBSERVED:{t['test']} (the executed output has no result line for {t['test']}: "
                          f"name the checks inside the function tagged @test {t['test']} '{t['test']}' or "
                          f"'{t['test']}-<suffix>')")
            for v in t["verifies"]:
                if v not in specs:
                    f4.append(f"UT:UNKNOWN_SPEC_REF:{t['test']}:{v}")
                rows4.append({"test": t["test"], "file": t["file"], "uspec": v, "result": res.get(t["test"], "NOT_RUN"),
                              "status": "VERIFIED" if res.get(t["test"]) == "PASS" and v in specs else "UNVERIFIED"})
        ok = {r["uspec"] for r in rows4 if r["status"] == "VERIFIED"}
        f4 += [f"UT:SPEC_NOT_VERIFIED:{s}" for s in specs if s not in ok]
        if run is None:
            f4.append("UT:NO_EXECUTED_RUN")
        rep["findings"]["SWE.4"] = f4
        rep["matrices"].append(write_matrix(ws, 4, rows4, [s for s in specs if s not in ok], write=w(4)))
    if k >= 3:
        ifs = sorted({IF_RX.match(c["label"]).group(0) for c in model["interfaces"] if IF_RX.match(c["label"])})
        elements = set(ifs) | set(documented_interfaces(ws)) | set(model["swcs"])
        known = ", ".join(sorted(elements)) or "none"
        it = latest_run(ws, "run_integration")
        tt = latest_run(ws, "run_renode")
        res = check_results(it["raw"]) if it else {}
        tests = tagged_tests(sorted(ws.glob("software/tests/integration/*.c")) + sorted(ws.glob("software/tests/target/*.c")),
                             ws)
        rows5, f5 = [], []
        for t in tests:
            if not t["verifies"]:
                f5.append(f"IT:TEST_WITHOUT_TRACE:{t['test']}")
            if it is not None and not (t["file_level"] or "/target/" in t["file"]) and t["test"] not in res:  # CAPA-039
                f5.append(f"IT:TEST_NOT_OBSERVED:{t['test']} (the executed output has no result line for {t['test']}: "
                          f"name the checks inside the function tagged @test {t['test']} '{t['test']}' or "
                          f"'{t['test']}-<suffix>')")
            result = (tt or {}).get("status", "NOT_RUN") if t["file_level"] or "/target/" in t["file"] else \
                res.get(t["test"], "NOT_RUN")
            for v in t["verifies"]:
                if v not in elements:
                    f5.append(f"IT:UNKNOWN_ARCH_REF:{t['test']}:{v} (architecture elements: {known})")
                rows5.append({"test": t["test"], "file": t["file"], "arch_element": v, "result": result,
                              "status": "VERIFIED" if result == "PASS" and v in elements else "UNVERIFIED"})
        ok = {r["arch_element"] for r in rows5 if r["status"] == "VERIFIED"}
        f5 += [f"IT:INTERFACE_NOT_VERIFIED:{i}" for i in ifs if i not in ok]
        rep["findings"]["SWE.5"] = f5
        rep["matrices"].append(write_matrix(ws, 5, rows5, [i for i in ifs if i not in ok], write=w(5)))
    if k >= 4:
        rr = latest_run(ws, "run_robot")
        res6 = robot_results(rr["raw"]) if rr else {}
        rows6, f6 = [], []
        for name, t in sorted(res6.items()):
            swrs = sorted(set(SWR_RX.findall(" ".join(t["tags"] or []))))
            if not swrs:
                f6.append(f"VT:TEST_WITHOUT_TRACE:{name}")
            for r in swrs:
                if r not in reqs:
                    f6.append(f"VT:UNKNOWN_SWR:{name}:{r}")
                rows6.append({"test": name, "swr": r, "result": t["status"],
                              "status": "VERIFIED" if t["status"] == "PASS" and r in reqs else "UNVERIFIED"})
        ok = {r["swr"] for r in rows6 if r["status"] == "VERIFIED"}
        f6 += [f"VT:SWR_NOT_VERIFIED:{r}" for r in reqs if r not in ok]
        if rr is None:
            f6.append("VT:NO_EXECUTED_RUN")
        rep["findings"]["SWE.6"] = f6
        rep["matrices"].append(write_matrix(ws, 6, rows6, [r for r in reqs if r not in ok], write=w(6)))
    return rep


PHASE_CHECK = {"SWE.2": "swc_allocation", "SWE.3": "unit_spec_and_code_trace", "SWE.4": "unit_test_trace",
               "SWE.5": "integration_test_trace", "SWE.6": "validation_test_trace"}


def check_phase(ws: Path, phase: str) -> dict:
    """Deterministic checklist entry point: builds matrices up to `phase`, verdict from that phase's relation."""
    own = phase == "SWE.3"  # unit ReqIF, PlantUML rendering and Doxygen belong to the SWE.3 baseline
    if own:
        from .unit_scaffold import cite_specs, sync_trace

        sync_trace(ws)  # CAPA-042: unit function lists and unambiguous @spec tags follow the code facts
        cite_specs(ws)  # CAPA-030: design -> unit-spec citation is generated from facts before the check
    rep = build_all(ws, upto=phase, write=PHASE_MATRICES[phase], render=own, doxygen=own, export=own)
    f = rep["findings"].get(phase, [])
    return {"verdict": "FAIL" if f else "PASS", "major_findings": f,
            "matrices": [m for m in rep["matrices"] if m["matrix"] in PHASE_MATRICES[phase]]}
