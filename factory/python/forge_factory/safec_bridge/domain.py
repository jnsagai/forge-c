"""F011-T013: the register-io domain document (contracts/register-io-domain.schema.json, version 2) from the work
order's RM sections.

Deterministic extraction only, with the same parser the SWE.1 inventory uses (`assurance.hardware.parse_section`).
Per register it records:
- offset and reset value, plus the reset bits the manual leaves undefined ("(0xFFFF FEFF)" in IWDG_SR);
- the section, the pages, and the SHA-256 of the exact section file;
- per field: bit span and the access tokens of the register diagram;
- the values the field description lists as bullets ("- 0xAAAA: ...");
- for a register with a single write-only field (a key register), the values the functional-description
  sections document as written to it ("Write 0x0000 0000 into IWDG key register (IWDG_KR) ..."), each with
  its own section and pages.

Unknown stays visible: a field whose access the diagram does not give has the token `unknown`; a missing reset value
is reset 0 with defined mask 0; a missing errata sheet is `errata.status = NOT_PROVIDED`. Nothing is guessed. SafeC
re-validates every invariant. The file is bound to a bridge request by the SHA-256 of its exact bytes
(`binding.source_manifest_sha256`).
"""
from __future__ import annotations

import re
from pathlib import Path

from ..common import sha256_bytes, sha256_file
from . import contracts as C

SCHEMA = "forge-c/register-io-domain/2"
VALUE_BULLET = re.compile(r"^\s*-\s*(0x[0-9A-Fa-f]+)\s*:\s*(.+)$")
FIELD_LINE = re.compile(r"^\s*Bits?\s+(\d+)(?::(\d+))?\s+([A-Z][A-Z0-9_]*)(?:\[[^\]]*\])?\s*:\s*(.*)$")
WRITES = (  # sentence forms of the manual's functional description that state a value written to a register
    r"[Ww]rit(?:e|es|ing)\s+(?:the\s+(?:key\s+)?value\s+)?(?P<v>0x[0-9A-Fa-f]{{4}}(?:\s[0-9A-Fa-f]{{4}})?)\s+(?:in|into|to)\s+"
    r"(?:the\s+)?[A-Za-z ]{{0,40}}?\((?P<r>{p}_[A-Z0-9_]+)\)",
    r"[Vv]alue\s+(?P<v>0x[0-9A-Fa-f]{{4}}(?:\s[0-9A-Fa-f]{{4}})?)\s+is\s+written\s+(?:in|into|to)\s+(?:the\s+)?[A-Za-z ]{{0,40}}?"
    r"\((?P<r>{p}_[A-Z0-9_]+)\)",
    r"[Ww]rit(?:e|es|ing)\s+(?P<r>{p}_[A-Z0-9_]+)\s+to\s+(?P<v>0x[0-9A-Fa-f]{{4}}(?:\s[0-9A-Fa-f]{{4}})?)",
)
RESET = re.compile(r"Reset value:\s*(0x[0-9a-fA-F]{4}\s?[0-9a-fA-F]{4})(?:\s*\((0x[0-9a-fA-F]{4}\s?[0-9a-fA-F]{4})\))?")


def hexs(v: int) -> str:
    return hex(v)  # canonical: lowercase, no leading zeros ("0x0", "0x20")


def _extractor_sha() -> str:
    from ..assurance import hardware

    return sha256_bytes(Path(hardware.__file__).read_bytes() + Path(__file__).read_bytes())


def _field_blocks(text: str) -> dict[str, list[str]]:
    """Field name -> its description lines (from its 'Bits' line up to the next one)."""
    blocks: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        m = FIELD_LINE.match(line)
        if m:
            current = m.group(3)
            blocks.setdefault(current, []).append(m.group(4))
        elif current is not None:
            if line.startswith(("#", "```")):
                current = None
            else:
                blocks[current].append(line)
    return blocks


def register_entry(text: str, prefix: str, source_id: str, section: str, pages: list[int]) -> dict | None:
    from ..assurance.hardware import parse_section

    r = parse_section(text, prefix)
    if r is None:
        return None
    m = RESET.search(text)
    reset = int(m.group(1).replace(" ", ""), 16) if m else 0
    defined = 0xFFFFFFFF if m else 0  # no reset value in the section: every bit's reset is unknown
    if m and m.group(2):  # the manual gives the mask of the defined bits in parentheses
        defined = int(m.group(2).replace(" ", ""), 16)
    blocks = _field_blocks(text)
    fields = []
    for name, f in sorted(r["fields"].items(), key=lambda kv: -kv[1]["msb"]):
        lines = blocks.get(name, [])
        label = " ".join(" ".join(lines[:1]).split())[:120]
        values = []
        for line in lines:
            v = VALUE_BULLET.match(line)
            if v:
                n = int(v.group(1), 16)
                values.append({"value": hexs(n), "fact_id": f"F-{r['name']}-{name}-V-{n:X}",
                               "label": " ".join(v.group(2).split())[:120], "source_id": source_id, "pages": pages})
        fields.append({"field_id": name, "lsb": f["lsb"], "msb": f["msb"],
                       "access_tokens": sorted(f["access"]) or ["unknown"], "fact_id": f"F-{r['name']}-{name}",
                       "label": label, "values": values})
    return {"register_id": r["name"], "offset": hexs(r["offset"]), "reset_value": hexs(reset),
            "reset_defined_mask": hexs(defined), "source_id": source_id, "section": section, "pages": pages,
            "fact_id": f"F-{r['name']}", "fields": fields}


def documented_writes(text: str, prefix: str) -> list[tuple[str, int, str]]:
    """(register, value, sentence) for every value a functional-description text states as written to a register."""
    flat = " ".join(text.split())
    out = []
    for sentence in re.split(r"(?<=\.)\s+", flat):
        for form in WRITES:
            for m in re.finditer(form.format(p=prefix), sentence):
                out.append((m.group("r"), int(m.group("v").replace(" ", ""), 16), sentence[:120]))
    return out


def _source(document: str, s: dict, ext: str) -> dict:
    return {"source_id": f"{document.split()[0]}-{s['section']}", "kind": "reference_manual", "document": document,
            "file": s["file"], "file_sha256": sha256_file(Path(s["path"])),
            "authority": "STMicroelectronics (owner input)", "extractor": "forge_factory.safec_bridge.domain",
            "extractor_sha256": ext}


def from_sections(sections: list[dict], *, prefix: str, peripheral: str, document: str,
                  out_of_scope: list[str] | None = None, errata: list[dict] | None = None,
                  functional: list[dict] | None = None) -> dict:
    """sections: [{"section", "file" (relative), "path" (readable), "pages": [int]}] in manual order; functional:
    the functional-description sections (same shape) searched for values written to key registers."""
    ext = _extractor_sha()
    sources, registers = [], []
    for s in sections:
        text = Path(s["path"]).read_text(errors="replace")
        src = _source(document, s, ext)
        entry = register_entry(text, prefix, src["source_id"], s["section"], sorted(set(s["pages"])))
        if entry is None:
            continue
        sources.append(src)
        registers.append(entry)
    keyed = {r["register_id"]: r["fields"][0] for r in registers
             if len(r["fields"]) == 1 and r["fields"][0]["access_tokens"] == ["w"]}
    for s in functional or []:
        src, used = _source(document, s, ext), False
        for reg, value, sentence in documented_writes(Path(s["path"]).read_text(errors="replace"), prefix):
            f = keyed.get(reg)
            if f is None or value >= 1 << (f["msb"] - f["lsb"] + 1) or any(
                    int(v["value"], 16) == value for v in f["values"]):
                continue
            f["values"].append({"value": hexs(value), "fact_id": f"F-{reg}-{f['field_id']}-V-{value:X}",
                                "label": sentence, "source_id": src["source_id"],
                                "pages": sorted(set(s["pages"]))})
            used = True
        if used:
            sources.append(src)
    errata = errata or []
    return {"schema": SCHEMA, "profile": "register-io-0.1", "peripheral": peripheral, "register_width": 32,
            "sources": sources + errata,
            "errata": {"status": "PROVIDED" if errata else "NOT_PROVIDED",
                       "source_ids": [e["source_id"] for e in errata]},
            "registers": registers, "out_of_scope_registers": sorted(set(out_of_scope or []))}


def build(ws: Path) -> tuple[dict, bytes]:
    """The domain of a prepared work order: its key RM sections and the registers its scope names out of scope."""
    from ..layer import profile, register_prefix
    from ..lrtx.swe1 import _manifest, _section_files

    ws = Path(ws)
    prof, pfx, secs = profile(ws), register_prefix(ws), _section_files(ws)
    sections = []
    for num in prof["rm"]["key_sections"]:
        s = secs.get(num)
        if s is None:
            continue
        text = (ws / s["file"]).read_text(errors="replace")
        pages = {int(p) for p in re.findall(r"p\.(\d+)", text.split("\n", 1)[0])} | \
            {int(p) for p in re.findall(r'id="p-(\d+)"', text)} | ({s["page"]} if s["page"] else set())
        sections.append({"section": num, "file": s["file"], "path": ws / s["file"], "pages": sorted(pages) or [1]})
    chapter = str(prof["rm"]["chapter"])
    func_roots = [n for n, s in secs.items() if n.startswith(chapter + ".") and "functional" in s["title"].lower()]
    functional = []
    for num, s in secs.items():
        if any(num == r or num.startswith(r + ".") for r in func_roots):
            text = (ws / s["file"]).read_text(errors="replace")
            pages = {int(p) for p in re.findall(r'id="p-(\d+)"', text)} | ({s["page"]} if s["page"] else set())
            functional.append({"section": num, "file": s["file"], "path": ws / s["file"], "pages": sorted(pages) or [1]})
    scope = _manifest(ws).get("scope") or []
    oos = sorted({r for line in scope if line.lower().startswith("out of scope")
                  for r in re.findall(rf"\b{pfx}_[A-Z0-9_]+\b", line)})
    doc = from_sections(sections, prefix=pfx, peripheral=pfx, document="RM0486 Rev 4", out_of_scope=oos,
                        functional=functional)
    return doc, C.canonical_bytes(doc)
