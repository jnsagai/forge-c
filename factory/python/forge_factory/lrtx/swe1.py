"""LRTX-T013/T015 (LRTX-FR-008/010/012/013): SWE.1 as coherent structured tasks for the local profile (LL layer).

1. Inventory (deterministic): every register field of the work order's key RM sections, with its section, page and bit
   range. Nothing may disappear silently: each field ends up named by a requirement or explicitly NOT covered with the
   scope reason the model gives.
2. Requirement groups (model, one packet per register, at most MAX_FIELDS fields): EARS requirements with source page,
   verification, verification level and register effects. Each answer is validated deterministically and repaired
   locally (only the named elements) within the visit's call budget.
3. Cross-cutting group (model): reset/startup behaviour and rules for all functions; resource requirements are
   rendered from the owner's work-order budgets (not invented).
4. Assembly (deterministic): SWR numbering, software_requirements.md, register_effects.json, requirements_to_tests.csv,
   upstream_gaps.md and the safety statement - the exact files the unchanged SWE.1 gates and inspector judge.
Validated packets are checkpointed by input hash and reused while their inputs are unchanged.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import structured as S
from . import visit as V

MAX_FIELDS = 5
EFFECTS = "workproducts/SWE.1/register_effects.json"
REQS = "workproducts/SWE.1/software_requirements.md"
CSV = "traceability/requirements_to_tests.csv"
GAPS = "traceability/upstream_gaps.md"
SAFETY = "safety/software_safety_requirements.md"
STARTUP = re.compile(r"^\s*While no .*after reset", re.I)

EFFECT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["case", "register", "field", "op", "value"],
                 "properties": {"case": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]{1,47}$"},
                                "register": {"type": "string"}, "field": {"type": "string"},
                                "op": {"type": "string", "enum": ["set", "clear", "write", "no_write"]},
                                "value": {"type": "string"}}}
REQ_SCHEMA = {"type": "object", "additionalProperties": False,
              "required": ["key", "statement", "source_page", "verification", "verified_by", "effects"],
              "properties": {"key": {"type": "string", "pattern": "^[a-z][a-z0-9_]{2,40}$"},
                             "statement": {"type": "string", "minLength": 20},
                             "source_page": {"type": "integer"},
                             "verification": {"type": "string", "minLength": 10},
                             "verified_by": {"type": "string", "enum": ["host_unit_test", "target_robot_test"]},
                             "effects": {"type": "array", "items": EFFECT_SCHEMA}}}
GROUP_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["requirements", "not_covered", "open_points"],
                "properties": {"requirements": {"type": "array", "items": REQ_SCHEMA},
                               "not_covered": {"type": "array", "items": {
                                   "type": "object", "additionalProperties": False, "required": ["field", "reason"],
                                   "properties": {"field": {"type": "string"}, "reason": {"type": "string", "minLength": 5}}}},
                               "open_points": {"type": "array", "items": {"type": "string"}}}}


# ---- inventory --------------------------------------------------------------------------------------------------------
def _manifest(ws: Path) -> dict:
    return json.loads((Path(ws) / ".forge-run/manifest.json").read_text())


def _section_files(ws: Path) -> dict[str, dict]:
    """section number -> {file, title, page} from inputs/index.md (first occurrence wins, like the builder)."""
    out: dict[str, dict] = {}
    for line in (Path(ws) / "inputs/index.md").read_text().splitlines():
        parts = [x.strip() for x in line.split(" | ")]
        if len(parts) == 4 and parts[0][:1].isdigit() and parts[0] not in out:
            page = int(parts[2][2:]) if parts[2].startswith("p.") and parts[2][2:].isdigit() else None
            out[parts[0]] = {"file": parts[3], "title": parts[1], "page": page}
    return out


def system_name(ws: Path) -> str:
    from ..layer import layer_of, profile

    names = json.loads((Path(ws) / "configuration/system_names.json").read_text())
    want = profile(ws).get("system_name") or "RCC LL driver"
    if layer_of(ws) != "LL":
        want = want.replace(" LL", "")
    return want if want in names else names[0]


def inventory(ws: Path) -> dict:
    from ..assurance.hardware import parse_section
    from ..layer import profile, register_prefix

    ws = Path(ws)
    prof, pfx, secs = profile(ws), register_prefix(ws), _section_files(ws)
    regs, missing = [], []
    for num in prof["rm"]["key_sections"]:
        s = secs.get(num)
        if s is None:
            missing.append(num)
            continue
        text = (ws / s["file"]).read_text(errors="replace")
        r = parse_section(text, pfx)
        if r is None:
            missing.append(num)
            continue
        pages = sorted({int(p) for p in re.findall(r"p\.(\d+)", text.split("\n", 1)[0])} |
                       {int(p) for p in re.findall(r'id="p-(\d+)"', text)} | ({s["page"]} if s["page"] else set()))
        regs.append({"section": num, "file": s["file"], "register": r["name"], "offset": r["offset"],
                     "pages": pages, "fields": {k: {"msb": v["msb"], "lsb": v["lsb"], "access": v.get("access", [])}
                                                for k, v in r["fields"].items()}})
    items = [f"{r['register']}.{f}" for r in regs for f in r["fields"]]
    return {"schema": "forge-c/lrtx-swe1-inventory/1", "registers": regs, "items": items, "missing_sections": missing,
            "generated_at": utc_now()}


def groups(inv: dict) -> list[dict]:
    """One packet per register, split at MAX_FIELDS fields (field order of the RM section kept)."""
    out = []
    for r in inv["registers"]:
        names = list(r["fields"])
        n = -(-len(names) // MAX_FIELDS) or 1  # balanced parts, none larger than MAX_FIELDS
        size = -(-len(names) // n) if names else 0
        for i in range(0, len(names), size or 1):
            part = names[i:i + size]
            gid = f"{r['register']}" + (f"_{i // size + 1}" if n > 1 else "")
            out.append({"id": gid, "register": r["register"], "section": r["section"], "file": r["file"],
                        "pages": r["pages"], "fields": {f: r["fields"][f] for f in part}})
    return out


# ---- packet texts -----------------------------------------------------------------------------------------------------
def coverage_guidance(ws: Path) -> str:
    """The work order's coverage rules, from the same texts the agent prompts use (no new requirements policy)."""
    from ..layer import layer_of, profile
    from ..workflow import prompts

    prof = profile(ws)
    cover = ((prof.get("prompt") or {}).get("swe1_cover"))
    if cover:
        return " ".join(cover.split())
    step = (prompts.LL_AUTHOR_STEPS if layer_of(ws) == "LL" else prompts.AUTHOR_STEPS)["SWE.1"][1]
    m = re.search(r"(Cover:.*?)(?:Add three measurable|$)", step, re.S)
    return " ".join((m.group(1) if m else step).split())


def effect_rule(ws: Path) -> str:
    from ..layer import profile

    rule = (profile(ws).get("prompt") or {}).get("swe1_effect_rule")
    base = ("effects: one entry per bit and per function the requirement sets or clears (op set|clear), writes a value "
            "to (op write, value \"0x...\") or only reads (op no_write with register and field); value is \"\" unless "
            "op is write. register/field are the RM names the statement itself uses (write them as REGISTER.FIELD in "
            "the statement). case ids are unique UPPER_CASE names.")
    return base + (" " + " ".join(rule.split()) if rule else "")


def group_packet(ws: Path, g: dict, model: str, findings: list[str] | None = None, previous: dict | None = None) -> dict:
    m = _manifest(ws)
    sysname = system_name(ws)
    fields = ", ".join(f"{g['register']}.{f} (bits {v['msb']}:{v['lsb']}, access {'/'.join(v['access']) or '?'})"
                       for f, v in g["fields"].items())
    instr = (f"Write the software requirements of the {sysname} for register {g['register']} (RM0486 section "
             f"{g['section']}). Fields of this task: {fields}. Work-order scope: " + " | ".join(m["scope"]) +
             f". Coverage rules of this work order: {coverage_guidance(ws)} Apply them ONLY to the fields of this task; "
             "other registers are separate tasks. For every field of this task either write the requirements the scope "
             "demands for it or list it in not_covered with the scope reason. Each statement uses EARS "
             f"(The/When/While/Where/If..then), exactly one 'shall', the subject 'the {sysname}', and ends with a period; "
             "name the field as REGISTER.FIELD. verification states the test and its pass criterion ('... passes "
             "when ...'), checking register bits and return values on the register array - never a count of register "
             "accesses. verified_by is host_unit_test, except startup/reset behaviour ('While no ... after reset') which "
             f"is target_robot_test. source_page is the RM0486 page of the cited fact ({', '.join(map(str, g['pages']))}). "
             + effect_rule(ws) + " key is a short snake_case name of the requirement. open_points lists ambiguities of "
             "the source (or nothing).")
    crit = [f"every requirement's subject is exactly 'the {sysname}'", "every field of the task is covered or listed "
            "in not_covered", "every effect names a field of this task that its statement names",
            "a statement that sets, clears or writes a field has an effect for it"]
    return S.packet(phase="SWE.1", task=f"requirements:{g['id']}", role="swe1-author", instructions=instr,
                    sources=[S.source(ws, g["file"])], criteria=crit, output_schema=GROUP_SCHEMA, model=model,
                    findings=findings, previous=previous)


def crosscut_packet(ws: Path, functional: list[dict], model: str, findings: list[str] | None = None,
                    previous: dict | None = None) -> dict:
    m = _manifest(ws)
    sysname = system_name(ws)
    listing = "\n".join(f"- [{r['key']}] {r['statement']}" for r in functional)
    instr = (f"The register-level requirements of the {sysname} are already written (listed below as CURRENT "
             "ARTIFACT). Write only the requirements that do not belong to one register field: the reset/startup "
             f"behaviour (e.g. 'While no LL function has been called after reset, the {sysname} shall not write any "
             "register.') and any rule the coverage rules state for all functions (e.g. that a write changes only the "
             "named bits). Work-order scope: " + " | ".join(m["scope"]) + f". Coverage rules: {coverage_guidance(ws)} "
             "Do NOT write flash/RAM/stack budget requirements: the factory adds them from the owner's work-order "
             "budgets. Same statement, verification and source_page rules as the register tasks; reset/startup "
             "requirements are target_robot_test. effects stay empty unless a statement sets, clears or writes a named "
             "field. not_covered stays empty.")
    art = {"path": "lrtx:functional_requirements", "text": listing, "sha256": sha256_bytes(listing.encode())}
    secs = _section_files(ws)
    from ..layer import profile

    chapter = str(profile(ws)["rm"]["chapter"])
    func = [n for n, s in secs.items() if n.startswith(chapter + ".") and "functional" in s["title"].lower()]
    srcs = [S.source(ws, secs[n]["file"], max_chars=20_000) for n in func[:1]]
    return S.packet(phase="SWE.1", task="requirements:crosscutting", role="swe1-author", instructions=instr,
                    sources=srcs, artifacts=[art], criteria=[f"subject exactly 'the {sysname}'",
                                                             "no budget requirements"],
                    output_schema=GROUP_SCHEMA, model=model, findings=findings, previous=previous)


# ---- deterministic validation of one answer -------------------------------------------------------------------------
def _value(v: str) -> int | None:
    try:
        return int(v, 0) if isinstance(v, str) else None
    except ValueError:
        return None


def validate_group(ws: Path, doc: dict, g: dict | None, sysname: str, idx: dict) -> list[str]:
    from ..assurance.register_contract import _needs_contract
    from ..inspection.ears import Requirement, check_statement
    from ..layer import register_prefix

    pfx = register_prefix(ws)
    out, keys, named = [], set(), set()
    for r in doc["requirements"]:
        k = r["key"]
        if k in keys:
            out.append(f"[{k}] duplicate key")
        keys.add(k)
        st = r["statement"]
        for f in check_statement(Requirement(k, st, 0), {sysname}).findings:
            out.append(f"[{k}] {f.split(':', 1)[1] if ':' in f else f}")
        if "pass" not in r["verification"].lower():
            out.append(f"[{k}] verification has no pass criterion ('passes when ...')")
        if STARTUP.match(st) and r["verified_by"] != "target_robot_test":
            out.append(f"[{k}] a startup/reset invariant is verified by target_robot_test, not a host unit test")
        if g is not None and g["pages"] and not (min(g["pages"]) <= r["source_page"] <= max(g["pages"]) + 2):
            out.append(f"[{k}] source_page {r['source_page']} is outside the section pages {g['pages']}")
        for f in re.findall(rf"\b({pfx}_[A-Z0-9]+)\.([A-Z0-9_]+)", st):
            named.add(f"{f[0]}.{f[1]}")
            if f[0] not in idx or f[1] not in idx[f[0]]["fields"]:
                out.append(f"[{k}] {f[0]}.{f[1]} is not a field of the RM0486 register index")
        for e in r["effects"]:
            reg, fld, op = e["register"], e["field"], e["op"]
            if g is not None and (reg != g["register"] or fld not in g["fields"]):
                out.append(f"[{k}] effect {e['case']} names {reg}.{fld}, not a field of this task")
                continue
            if reg not in idx or fld not in idx[reg]["fields"]:
                out.append(f"[{k}] effect {e['case']} names {reg}.{fld}, not in the RM0486 register index")
                continue
            if f"{reg}.{fld}" not in st and not (reg in st and fld in st):
                out.append(f"[{k}] effect {e['case']}: the statement must name {reg}.{fld}")
            if op == "write":
                width = idx[reg]["fields"][fld]["msb"] - idx[reg]["fields"][fld]["lsb"] + 1
                v = _value(e["value"])
                if v is None or not 0 <= v < (1 << width):
                    out.append(f"[{k}] effect {e['case']}: value {e['value']!r} must be a number that fits "
                               f"{reg}.{fld} ({width} bits)")
            elif e["value"] not in ("", None):
                out.append(f"[{k}] effect {e['case']}: value must be \"\" for op {op}")
        if _needs_contract(st, pfx) and not r["effects"]:  # the gate's rule (CONTRACT_SWR_NOT_COVERED)
            out.append(f"[{k}] the statement names a field it sets or clears but has no effect entry")
    if g is not None:
        covered = named | {f"{e['register']}.{e['field']}" for r in doc["requirements"] for e in r["effects"]}
        excluded = {x["field"] if "." in x["field"] else f"{g['register']}.{x['field']}" for x in doc["not_covered"]}
        for f in g["fields"]:
            full = f"{g['register']}.{f}"
            if full not in covered and full not in excluded:
                out.append(f"field {full} is neither named by a requirement nor listed in not_covered")
            if full in covered and full in excluded:
                out.append(f"field {full} is both covered and listed in not_covered")
        out += [f"not_covered {x['field']} is not a field of this task" for x in doc["not_covered"]
                if (x["field"].split(".")[-1]) not in g["fields"]]
    elif doc["not_covered"]:
        out.append("not_covered must be empty for the cross-cutting task")
    return out


# ---- assembly (deterministic rendering of the existing SWE.1 work products) -------------------------------------------
def _page_section(ws: Path, page: int | None, fallback: str) -> str:
    """The RM0486 section whose page range holds `page` (key sections first), else the task's own section."""
    if page is None:
        return fallback
    secs = _section_files(ws)
    starts = sorted(((s["page"], n) for n, s in secs.items() if s["page"]), key=lambda x: (x[0], -len(x[1])))
    best = None
    for start, n in starts:
        if start <= page:
            best = n if best is None or start >= secs[best]["page"] else best
    return best or fallback


def budget_requirements(ws: Path, sysname: str) -> list[dict]:
    b = _manifest(ws)["budgets"]
    src = "work-order budget (owner development target)"
    robot = "SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; "
    return [{"key": "budget_flash", "statement": f"The {sysname} shall occupy at most {b['flash_bytes']} bytes of flash.",
             "source": src, "verification": robot + f"passes when the driver flash usage is at most {b['flash_bytes']} "
             "bytes.", "verified_by": "target_robot_test", "effects": [], "upstream": "WO-BUDGET"},
            {"key": "budget_static_ram", "statement": f"The {sysname} shall use at most {b['static_ram_bytes']} bytes "
             "of static RAM.", "source": src, "verification": robot + "passes when the driver-owned data and BSS total "
             f"at most {b['static_ram_bytes']} bytes, excluding the externally provided register array.",
             "verified_by": "target_robot_test", "effects": [], "upstream": "WO-BUDGET"},
            {"key": "budget_stack", "statement": f"The {sysname} shall use at most {b['stack_bytes']} bytes of stack "
             "for any public API call.", "source": src, "verification": robot + "passes when the worst-case stack usage "
             f"of every public API call chain is at most {b['stack_bytes']} bytes.", "verified_by": "target_robot_test",
             "effects": [], "upstream": "WO-BUDGET"}]


def _scope_ids(alloc: str) -> tuple[str, str]:
    asil = re.search(r"\b(ASIL [A-D]|QM)\b", alloc)
    sid = re.search(r"\((SC-[^,)\s]+)", alloc)
    return (asil.group(1) if asil else "UNSPECIFIED"), (sid.group(1) if sid else "no scope id")


def safety_text(ws: Path) -> str | None:
    """The SWE.1 safety statement exactly as the SWE.1 author instructions prescribe it; None when an allocation exists
    (then the safety-relevant SWRs must come from an upstream SSR task - not implemented here: the visit fails)."""
    alloc = _manifest(ws)["target"].get("safety_allocation", "")
    if "OUT_OF_SCOPE" in alloc:
        return ("# Software safety requirements\n\nQM development scope: no software safety requirements are allocated "
                "(work-order owner decision).\n")
    if "PENDING owner allocation review" in alloc:
        asil, sid = _scope_ids(alloc)
        return (f"# Software safety requirements\n\nTarget {asil} ({sid}): software safety allocation PENDING owner "
                "allocation review - no software safety requirement is allocated yet; this is an open gap, not a QM "
                f"claim.\n\nSafety context recorded in the work-order manifest: {alloc}. No safety items are listed "
                "until the owner's allocation review allocates software safety requirements.\n")
    return None


def assemble(ws: Path, inv: dict, results: list[tuple[dict, dict]], cross: dict) -> dict:
    """results: [(group, VALID task record)]. Writes the SWE.1 work products; returns the SWR map."""
    from ..layer import profile

    ws = Path(ws)
    m = _manifest(ws)
    sysname, pid = system_name(ws), profile(ws)["id"]
    rows: list[dict] = []
    for g, rec in results:
        for r in rec["doc"]["requirements"]:
            rows.append({**r, "task": rec["task"], "source": f"RM0486 p.{r['source_page']}",
                         "upstream": f"RM0486-{_page_section(ws, r['source_page'], g['section'])}"})
    first = inv["registers"][0]["section"] if inv["registers"] else "?"
    for r in cross["doc"]["requirements"]:
        rows.append({**r, "task": cross["task"], "source": f"RM0486 p.{r['source_page']}",
                     "upstream": f"RM0486-{_page_section(ws, r['source_page'], first)}"})
    rows += [{**r, "task": "budgets"} for r in budget_requirements(ws, sysname)]
    for n, r in enumerate(rows, 1):
        r["swr"] = f"SWR-{n:03d}"
    opens = []
    for _g, rec in results + [(None, cross)]:
        opens += [o.strip() for o in rec["doc"]["open_points"] if o.strip() and o.strip() not in opens]
    up = m.get("upstream", {}).get("status", "NOT_PROVIDED")
    opens += [f"Upstream inputs (HSI contract, safety allocation, budgets): {up}.",
              f"Safety allocation as stated in the manifest: {m['target'].get('safety_allocation', 'UNSPECIFIED')}.",
              f"Target silicon revision: {m['target'].get('silicon_revision', 'UNSPECIFIED')}.",
              f"Flash, static RAM and stack limits: {m['budgets'].get('status', 'work-order budgets')}."]
    md = ["# Software requirements", "",
          f"Software requirements of the {sysname} for this work order. Scope: " + " ".join(m["scope"]), ""]
    for r in rows:
        md += [f"- **{r['swr']}** {r['statement'].strip()}", f"  - Source: {r['source']}",
               f"  - Verification: {r['verification'].strip()}"]
    md += ["", "## Open points", ""] + [f"- {o}" for o in opens] + [""]
    effects, seen = [], set()
    for r in rows:
        for e in r["effects"]:
            case = e["case"]
            k = 2
            while case in seen:
                case = f"{e['case']}_{k}"
                k += 1
            seen.add(case)
            item = {"case": case, "swr": r["swr"], "register": e["register"], "field": e["field"], "op": e["op"]}
            if e["op"] == "write":
                item["value"] = e["value"]
            effects.append(item)
    csv, ut = ["requirement_id,test_id,test_file"], 0
    for r in rows:
        if r["verified_by"] == "host_unit_test":
            ut += 1
            csv.append(f"{r['swr']},UT-{ut:03d},software/tests/unit/test_{pid}.c")
        else:
            csv.append(f"{r['swr']},{r['swr']},software/tests/software/test_{pid}_requirements.robot")
    by_up: dict[str, list[str]] = {}
    for r in rows:
        by_up.setdefault(r["upstream"], []).append(r["swr"])
    t = m["target"]
    reg_swr = [r["swr"] for r in rows if r["upstream"] != "WO-BUDGET"]
    bud_swr = [r["swr"] for r in rows if r["upstream"] == "WO-BUDGET"]
    gaps = ["# Upstream coverage", "", "| Input | Status as stated in the manifest | Affected SWR IDs |",
            "| --- | --- | --- |",
            f"| HSI contract | {t.get('hsi_contract', 'NOT_PROVIDED')}; upstream.status: {up} | {', '.join(reg_swr)} |",
            f"| Safety allocation | {t.get('safety_allocation', 'NOT_PROVIDED')} | "
            f"{rows[0]['swr']} through {rows[-1]['swr']}: no software safety requirement is allocated |",
            f"| Budgets | {m['budgets'].get('status', '')}; flash_bytes: {m['budgets']['flash_bytes']}; static_ram_bytes: "
            f"{m['budgets']['static_ram_bytes']}; stack_bytes: {m['budgets']['stack_bytes']}; upstream.status: {up} | "
            f"{', '.join(bud_swr)} |", "",
            "No allocation is invented: missing approved upstream inputs remain open gaps.", "",
            "## Upstream to software requirements", "", "| Upstream ID | SWR IDs |", "| --- | --- |"]
    gaps += [f"| {u} | {', '.join(s)} |" for u, s in by_up.items()]
    gaps += ["", "## Software requirements to upstream", "", "| SWR ID | Upstream ID |", "| --- | --- |"]
    gaps += [f"| {r['swr']} | {r['upstream']} |" for r in rows] + [""]
    files = {REQS: "\n".join(md), EFFECTS: json.dumps({"schema": "forge-c/register-effects/1", "effects": effects},
                                                      indent=2) + "\n",
             CSV: "\n".join(csv) + "\n", GAPS: "\n".join(gaps)}
    st = safety_text(ws)
    if st is not None:
        files[SAFETY] = st
    write_scoped(ws, files)
    amap = {"schema": "forge-c/lrtx-swe1-assembly/1", "at": utc_now(),
            "swr": {r["swr"]: {"task": r["task"], "key": r["key"]} for r in rows},
            "case": {e["case"]: e["swr"] for e in effects}, "files": sorted(files)}
    S.record(ws, "SWE.1/assembly.json", amap)
    return amap


# ---- consistency and self-checks ------------------------------------------------------------------------------------
def consistency(results: list[tuple[dict, dict]], cross: dict) -> list[str]:
    """LRTX-FR-010 global check across tasks: duplicate statements, contradictory effects on one field."""
    out, seen, ops = [], {}, {}
    for _g, rec in results + [(None, cross)]:
        for r in rec["doc"]["requirements"]:
            norm = re.sub(r"\W+", " ", r["statement"].lower()).strip()
            if norm in seen:
                out.append(f"[{r['key']}] duplicates [{seen[norm]}] ({rec['task']})")
            seen[norm] = r["key"]
            for e in r["effects"]:
                ops.setdefault((e["case"], e["register"], e["field"]), set()).add(e["op"])
    out += [f"case {c} has contradictory ops {sorted(o)} on {r}.{f}" for (c, r, f), o in ops.items()
            if {"set", "clear"} <= o]
    return out


def self_check(ws: Path) -> list[str]:
    """The deterministic SWE.1 checks the author gate will apply, run before replying (no new criteria)."""
    from ..assurance import register_contract as RC
    from ..assurance.scope import workspace_scope_findings
    from ..inspection.ears import check_document
    from ..inspection.test_mapping import startup_on_host

    ws = Path(ws)
    names = set(json.loads((ws / "configuration/system_names.json").read_text()))
    ears = check_document((ws / REQS).read_text(), names)
    out = [f for f in ears.get("findings", []) if not f.split(":", 1)[-1].startswith("EARS_SYSTEM_NAME_HINT")]
    out += RC.check_effects(ws, "LL")
    out += startup_on_host(ws)
    out += workspace_scope_findings(ws, "SWE.1")
    return out


# ---- rework inputs -----------------------------------------------------------------------------------------------------


# ---- phase bindings of the shared visit machinery --------------------------------------------------------------------
def _ckpt(ws: Path, task: str) -> Path:
    return V._ckpt(ws, "SWE.1", task)


def run_task(ws: Path, task: str, build, check, budget: dict, findings: list[str] | None = None,
             max_repairs: int = 2) -> dict:
    return V.run_task(ws, "SWE.1", task, build, check, budget, findings, max_repairs)


def write_scoped(ws: Path, files: dict[str, str], node: str = "swe1_author") -> None:
    V.write_scoped(ws, files, node)


def rework_findings(ws: Path, since: str) -> list[str]:
    return V.rework_findings(ws, "SWE.1", since)


def route_findings(findings: list[str], amap: dict | None) -> dict[str, list[str]]:
    return V.route_findings(findings, amap, "requirements:crosscutting")


def reply(ws: Path, status: str, issues: list[str], budget: dict | None = None, artifacts: list[str] | None = None) -> dict:
    return V.reply(ws, "SWE.1", status, issues, budget, artifacts)


# ---- the author visit (one Fabro node execution) ----------------------------------------------------------------------
def visit(ws: Path, model: str, max_calls: int | None = None) -> dict:
    from ..assurance.hardware import index
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return reply(ws, "FAILED", ["LRTX_SWE1_LAYER_NOT_SUPPORTED_YET (structured SWE.1 covers LL work orders; HAL "
                                    "uses the agent author)"])
    role = {a.id: a for a in load_agents()[0]}["swe1-author"]
    vlog = ws / ".forge-run/lrtx/SWE.1/visits.jsonl"
    since = json.loads(vlog.read_text().splitlines()[-1])["at"] if vlog.is_file() and vlog.read_text().strip() else ""
    amap_p = ws / ".forge-run/lrtx/SWE.1/assembly.json"
    amap = json.loads(amap_p.read_text()) if amap_p.is_file() else None
    routed = route_findings(rework_findings(ws, since), amap) if since else {}
    budget = {"calls": 0, "max_calls": max_calls or role.max_turns, "schema_mode": "json_schema"}
    inv = inventory(ws)
    S.record(ws, "SWE.1/inventory.json", inv)
    if inv["missing_sections"]:
        return reply(ws, "FAILED", [f"LRTX_INVENTORY_SECTION_MISSING:{x}" for x in inv["missing_sections"]], budget)
    idx = index(ws / "inputs/sections/RM0486")
    sysname = system_name(ws)
    results, issues = [], []
    for g in groups(inv):
        task = f"requirements:{g['id']}"
        rec = run_task(ws, task, lambda fi, pr, g=g: group_packet(ws, g, model, fi, pr),
                       lambda d, g=g: validate_group(ws, d, g, sysname, idx), budget, routed.get(task))
        results.append((g, rec))
        if rec["status"] != "VALID":
            issues += [f"{task}: {e}" for e in rec["errors"][:5]]
    functional = [r for _g, rec in results if rec["doc"] for r in rec["doc"]["requirements"]]
    cross = run_task(ws, "requirements:crosscutting", lambda fi, pr: crosscut_packet(ws, functional, model, fi, pr),
                     lambda d: validate_group(ws, d, None, sysname, idx), budget, routed.get("requirements:crosscutting"))
    if cross["status"] != "VALID":
        issues += [f"requirements:crosscutting: {e}" for e in cross["errors"][:5]]
    if safety_text(ws) is None:
        issues.append("LRTX_SWE1_ALLOCATED_SAFETY_REQUIREMENTS_NOT_SUPPORTED (an approved software safety allocation "
                      "needs the upstream SSR task)")
    if issues:  # missing semantic content stays missing: nothing partial is assembled or frozen
        return reply(ws, "FAILED", issues, budget)
    issues = consistency(results, cross)
    if issues:
        return reply(ws, "FAILED", issues, budget)
    amap = assemble(ws, inv, results, cross)
    checks = self_check(ws)
    if checks and budget["calls"] < budget["max_calls"]:  # one localized repair round on the gate's own findings
        for task, fs in route_findings(checks, amap).items():
            g = next((g for g, _r in results if f"requirements:{g['id']}" == task), None)
            if g is not None:
                rec = run_task(ws, task, lambda fi, pr, g=g: group_packet(ws, g, model, fi, pr),
                               lambda d, g=g: validate_group(ws, d, g, sysname, idx), budget, fs)
                results = [(gg, rec if gg is g else rr) for gg, rr in results]
            else:
                cross = run_task(ws, "requirements:crosscutting",
                                 lambda fi, pr: crosscut_packet(ws, functional, model, fi, pr),
                                 lambda d: validate_group(ws, d, None, sysname, idx), budget, fs)
        bad = [rec for _g, rec in results + [(None, cross)] if rec["status"] != "VALID"]
        if bad:
            return reply(ws, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:5]], budget)
        amap = assemble(ws, inv, results, cross)
        checks = self_check(ws)
    if checks:
        return reply(ws, "FAILED", checks[:20], budget)
    return reply(ws, "PASS", [], budget, artifacts=amap["files"])


