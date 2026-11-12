"""Feature 020 T011 (research R3 part 1, FR-002/FR-003/FR-009..FR-012): the deterministic governance inventory.

Written by `prepare` (model-free) for a functional-level SWE.1 order as the listed, fingerprinted input
`inputs/governance-inventory.json` (the pattern of `inputs/delivered-interface.json`):

- the input register: every declared order input as `requirement_source` (conversion provenance is metadata, not a
  source; the delivered-interface vocabulary is derived from the code and therefore `implementation_under_analysis`),
  then every delivered code file as `implementation_under_analysis` - never a requirement source. RM inputs carry their
  section ids, titles and start pages from the existing section split; the revision comes from the input name
  (`-revN`) or the conversion manifest. Delivered build dependencies (vendor framework headers) are build context and
  are not listed.
- the delivered public API: per module component, the delivery-scope functions defined in its files (as resolved by
  the delivery intake) and, for an LL component, every inline function its delivered headers define (the existing
  C index of brownfield/scope.py). Only names, components and files are recorded - never a body.
- the scope classification of every API function by the order's scope rule (exact names and `*` patterns; an exact
  name wins over a pattern, the most specific pattern over a shorter one; a tie between groups is ambiguous), the
  in/out RM features and the not-delivered list.

Every gap is refused before launch as INPUT_GAP naming the item: an unclassified or ambiguous function, a scope entry
that matches no delivered function, a delivered file no component owns, a component file that is not delivered, an RM
feature the inputs do not have. Module facts come only from the work order: a second module needs no code change."""
from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA = "forge-c/governance-inventory/1"
OUT = "inputs/governance-inventory.json"
ROLE = "governance_inventory"
SOURCE, UNDER_ANALYSIS = "requirement_source", "implementation_under_analysis"
NOT_A_SOURCE = ("conversion_provenance",)
DERIVED_FROM_CODE = ("delivered_interface",)


class InputGap(ValueError):
    """The order cannot be prepared for functional-level SWE.1; the message lists INPUT_GAP:<code>:<item> entries."""


def _rx(entry: str) -> re.Pattern:
    return re.compile("^" + ".*".join(re.escape(p) for p in entry.split("*")) + "$")


def classify(functions: list[str], rule: dict) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """{function: (scope_class, group)} and the gap codes, for delivered function names and a scope rule."""
    entries = [(cls, g["group"], e) for cls in ("in", "out") for g in rule.get(cls) or [] for e in g["functions"]]
    used: set[tuple[str, str, str]] = set()
    out: dict[str, tuple[str, str]] = {}
    gaps: list[str] = []
    for fn in functions:
        hits = [h for h in entries if (h[2] == fn if "*" not in h[2] else _rx(h[2]).match(fn))]
        used.update(hits)
        if not hits:
            gaps.append(f"GOVERNANCE_FUNCTION_UNCLASSIFIED:{fn}")
            continue
        best = [h for h in hits if "*" not in h[2]]
        if not best:
            top = max(len(h[2].replace("*", "")) for h in hits)
            best = [h for h in hits if len(h[2].replace("*", "")) == top]
        groups = sorted({(c, g) for c, g, _e in best})
        if len(groups) > 1:
            gaps.append(f"GOVERNANCE_FUNCTION_AMBIGUOUS:{fn}:{'|'.join(f'{c}/{g}' for c, g in groups)}")
            continue
        out[fn] = groups[0]
    gaps += [f"GOVERNANCE_SCOPE_ENTRY_MATCHES_NOTHING:{e}" for e in dict.fromkeys(h[2] for h in entries
                                                                                  if h not in used)]
    return out, gaps


def sections(md_text: str, doc_stem: str) -> list[dict]:
    """Section id, title and start page of an RM input, from the existing section split (workorder.split_sections)."""
    from ..workorder import split_sections

    out, seen = [], set()
    for line in split_sections(md_text, doc_stem)[1]:
        num, title, page = (x.strip() for x in line.split(" | ")[:3])
        if num in seen:
            continue
        seen.add(num)
        title = re.sub(r" \(part \d+/\d+\)$", "", title)
        out.append({"section": num, "title": title,
                    **({"page": int(page[2:])} if page.startswith("p.") and page[2:].isdigit() else {})})
    return out


def _revision(name: str, provenance: dict[str, dict]) -> dict:
    rec = provenance.get(name) or {}
    if rec.get("revision"):
        return {"revision": str(rec["revision"])}
    m = re.search(r"-rev(\d+)(?=[-_.])", name, re.I)
    return {"revision": f"Rev {m.group(1)}"} if m else {}


def input_register(listed: list[dict], inputs: dict[str, bytes], delivered: list[dict]) -> list[dict]:
    provenance: dict[str, dict] = {}
    for item in listed:
        if item["role"] in NOT_A_SOURCE and item["path"].endswith(".json"):
            try:
                docs = json.loads(inputs[item["path"]]).get("documents") or []
            except (ValueError, AttributeError):
                docs = []
            provenance.update({d["markdown"]: d for d in docs if isinstance(d, dict) and d.get("markdown")})
    rows = []
    for item in listed:
        if item["role"] in NOT_A_SOURCE or item["path"] == OUT:
            continue
        name = Path(item["path"]).name
        row = {"name": name, **_revision(name, provenance), "sha256": item["sha256"], "bytes": item["bytes"],
               "role": UNDER_ANALYSIS if item["role"] in DERIVED_FROM_CODE else SOURCE}
        if item["path"].startswith("inputs/RM") and item["path"].endswith(".md"):
            row["sections"] = sections(inputs[item["path"]].decode("utf-8"), Path(item["path"]).stem.split("-")[0])
        rows.append(row)
    rows += [{"name": d["path"], "sha256": d["sha256"], "bytes": d["bytes"], "role": UNDER_ANALYSIS}
             for d in delivered if d.get("role") == "delivered_code"]
    return [{"input_id": f"IN-{n:02d}", **r} for n, r in enumerate(rows, 1)]


def delivered_api(module: dict, delivered: list[dict], files: dict[str, bytes],
                  scope_functions: list[dict]) -> tuple[list[dict], list[str]]:
    """[(function, component, file)] of the module's components and the component/file gaps."""
    from ..brownfield import scope as S

    code = [d["path"] for d in delivered if d.get("role") == "delivered_code"]
    owner: dict[str, dict] = {}
    gaps = []
    for c in module["components"]:
        for f in c["files"]:
            if f not in code:
                gaps.append(f"GOVERNANCE_COMPONENT_FILE_NOT_DELIVERED:{f}")
            elif f in owner:
                gaps.append(f"GOVERNANCE_FILE_IN_TWO_COMPONENTS:{f}")
            else:
                owner[f] = c
    gaps += [f"GOVERNANCE_FILE_WITHOUT_COMPONENT:{p}" for p in code if p not in owner]
    api: dict[str, dict] = {}
    for s in scope_functions:
        if s.get("file") in owner:
            api.setdefault(s["name"], {"function": s["name"], "component": owner[s["file"]]["id"], "file": s["file"]})
    for f, c in owner.items():
        if c["layer"] == "LL" and f.endswith(".h"):
            for d in S.index(files[f].decode("utf-8", errors="replace"), f):
                if d.kind == "static_inline":
                    api.setdefault(d.name, {"function": d.name, "component": c["id"], "file": f})
    return list(api.values()), gaps


def build(spec: dict, listed: list[dict], inputs: dict[str, bytes], intake: dict | None, wo: str) -> dict:
    """The inventory of a functional-level order (InputGap when it cannot be classified)."""
    if not intake:
        raise InputGap("INPUT_GAP:GOVERNANCE_NO_DELIVERY:a functional-level module order needs its delivered code")
    from ..brownfield import delivery as BD

    store = BD.store_dir(wo)
    scope_functions = json.loads((store / "scope.json").read_text())["functions"]
    module, rule = spec["module"], spec["scope_rule"]
    api, gaps = delivered_api(module, intake["files"], BD.stored(wo), scope_functions)
    classes, cgaps = classify([a["function"] for a in api], rule)
    gaps += cgaps
    register = input_register(listed, inputs, intake["files"])
    known = {s["section"] for r in register for s in r.get("sections") or []}
    features: dict[str, str] = {}
    for cls in ("in", "out"):
        for g in rule.get(cls) or []:
            for f in g.get("rm_features") or []:
                if f not in known:
                    gaps.append(f"GOVERNANCE_RM_FEATURE_UNKNOWN:{f}")
                elif features.get(f) != "in":
                    features[f] = cls
    if gaps:
        raise InputGap(";".join(f"INPUT_GAP:{g}" for g in dict.fromkeys(gaps)))
    return {"schema": SCHEMA, "module": module["name"], "inputs": register,
            "api": [{**a, "scope_class": classes[a["function"]][0], "scope_group": classes[a["function"]][1]}
                    for a in api],
            "rm_features": [{"feature": f, "scope_class": c} for f, c in features.items()],
            "not_delivered": list(rule.get("not_delivered") or [])}


def render(doc: dict) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


def load(ws: Path) -> dict:
    return json.loads((Path(ws) / OUT).read_text())
