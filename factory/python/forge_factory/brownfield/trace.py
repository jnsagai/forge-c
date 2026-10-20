"""Code trace for delivered code (research R5): frozen code cannot carry @unit/@spec tags, so the SWE.3 author maps
each delivered scope function to its unit and unit specification items in `workproducts/SWE.3/code_trace_map.json`.

`seed()` writes the deterministic starting point (scope functions, files, fingerprints); `check_code()` replaces
swtrace's tag-based code check for brownfield work orders and returns the same shape (verdict, findings, rows)."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import pretty_json, sha256_bytes
from . import DELIVERY_DIR, manifest_of, reference_paths
from . import scope as S

MAP = "workproducts/SWE.3/code_trace_map.json"
SEED = "workproducts/SWE.3/code_trace_map.seed.json"
FACTS = "workproducts/SWE.3/delivered_code_facts.json"
SCHEMA = "forge-c/code-trace-map/0.1"


def scope_functions(ws: Path) -> list[dict]:
    p = Path(ws) / DELIVERY_DIR / "scope.json"
    return json.loads(p.read_text()).get("functions", []) if p.is_file() else []


def seed(ws: Path) -> dict:
    """Write the trace-map seed and the delivered-code facts (functions, kinds, lines, register effects)."""
    ws = Path(ws)
    m = manifest_of(ws)
    style = (m.get("delivery") or {}).get("build", {}).get("style", "forge")
    texts = {rel: (ws / rel).read_text(errors="replace") for rel in reference_paths(m) if (ws / rel).is_file()}
    macros = S.constant_macros(list(texts.values()))
    defs = {d.name: d for rel in reversed(list(texts)) for d in S.index(texts[rel], rel)}  # delivered wins
    rows, facts = [], []
    for f in scope_functions(ws):
        sha = sha256_bytes((ws / f["file"]).read_bytes()) if (ws / f["file"]).is_file() else None
        rows.append({"function": f["name"], "file": f["file"], "sha256": sha, "unit": "SWU-?", "uspecs": []})
        d = defs.get(f["name"])
        eff = [] if d is None else [{"register": e.register, "op": e.op, "bits": S.bits(e.mask), "via": e.via}
                                    for e in S.register_effects(d, macros, style, defs=defs) if d.kind != "macro"
                                    or not d.params]
        facts.append({"function": f["name"], "file": f["file"], "line": f["line"], "kind": f["kind"],
                      "params": d.params if d else [], "register_effects": eff})
    out = ws / SEED
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pretty_json({"schema": SCHEMA, "note": "seed: fill unit and uspecs, save as code_trace_map.json",
                                "rows": rows}))
    (ws / FACTS).write_text(pretty_json({"schema": "forge-c/delivered-code-facts/0.1", "style": style,
                                         "functions": facts}))
    return {"rows": len(rows)}


def load_map(ws: Path) -> dict | None:
    p = Path(ws) / MAP
    try:
        return json.loads(p.read_text()) if p.is_file() else None
    except ValueError:
        return {"schema": None, "rows": None}


def check_code(ws: Path, units: list[dict]) -> dict:
    """Brownfield replacement of swtrace.check_code (CODE:* findings and matrix-3 rows) from the trace map."""
    ws = Path(ws)
    m = manifest_of(ws)
    f, rows = [], []
    tm = load_map(ws)
    by_unit = {u["id"]: u for u in units}
    spec_unit = {s["id"]: u["id"] for u in units for s in u["specs"]}
    scope = {x["name"]: x for x in scope_functions(ws)}
    expected = {d["path"]: d["sha256"] for d in m.get("delivered") or []}
    if tm is None:
        return {"verdict": "FAIL", "major_findings": [f"CODE:TRACE_MAP_MISSING:{MAP} (copy {SEED} and fill unit/uspecs)"],
                "rows": [], "doxygen": {"status": "NOT_RUN", "warnings": []}}
    if tm.get("schema") != SCHEMA or not isinstance(tm.get("rows"), list):
        return {"verdict": "FAIL", "major_findings": [f"CODE:TRACE_MAP_INVALID:{MAP} (schema {SCHEMA}, rows list)"],
                "rows": [], "doxygen": {"status": "NOT_RUN", "warnings": []}}
    seen: dict[str, int] = {}
    texts = {rel: (ws / rel).read_text(errors="replace") for rel in expected if (ws / rel).is_file()}
    defined = {d.name: d.file for rel, t in texts.items() for d in S.index(t, rel)}
    for r in tm["rows"]:
        fn = str(r.get("function", ""))
        seen[fn] = seen.get(fn, 0) + 1
        if r.get("out_of_scope"):
            if fn in scope:
                f.append(f"CODE:SCOPE_FUNCTION_MARKED_OUT_OF_SCOPE:{fn}")
            continue
        rel, sha = str(r.get("file", "")), r.get("sha256")
        if fn not in scope:
            f.append(f"CODE:TRACE_MAP_FUNCTION_NOT_IN_SCOPE:{fn}")
        if defined.get(fn) != rel:
            f.append(f"CODE:TRACE_MAP_FUNCTION_NOT_IN_FILE:{fn}@{rel}")
        current = sha256_bytes((ws / rel).read_bytes()) if rel in texts else None
        if rel in texts and sha != current and not (m.get("code_mode") == "FIX_ALLOWED" and sha == expected.get(rel)):
            # FIX_ALLOWED: the delivered fingerprint stays valid after a fix (verify_delivery governs the change)
            f.append(f"CODE:TRACE_MAP_FINGERPRINT_MISMATCH:{fn}@{rel}")
        u = str(r.get("unit", ""))
        if u not in by_unit:
            f.append(f"CODE:UNKNOWN_UNIT_REF:{fn}:{u}")
        elif fn not in by_unit[u]["functions"]:
            f.append(f"CODE:FUNCTION_UNIT_MISMATCH:{fn}:{u}")
        specs = r.get("uspecs") or []
        if not specs:
            f.append(f"CODE:UNDOCUMENTED_FUNCTION:{fn}@{rel} (no uspecs in the trace map)")
        for s in specs:
            if spec_unit.get(s) is None:
                f.append(f"CODE:UNKNOWN_SPEC_REF:{fn}:{s}")
            elif spec_unit[s] != u:
                f.append(f"CODE:SPEC_OF_OTHER_UNIT:{fn}:{s}")
            rows.append({"function": fn, "file": rel, "unit": u, "uspec": s,
                         "status": "TRACED" if spec_unit.get(s) == u else "INVALID"})
    f += [f"CODE:TRACE_MAP_DUPLICATE_FUNCTION:{fn}" for fn, n in seen.items() if n > 1]
    f += [f"CODE:SCOPE_FUNCTION_NOT_IN_TRACE_MAP:{fn}" for fn in scope if fn not in seen]
    referenced = {r["uspec"] for r in rows if r["status"] == "TRACED"}
    f += [f"CODE:SPEC_NOT_IMPLEMENTED:{s} (map it to the delivered function(s) of {spec_unit[s]} in {MAP})"
          for s in sorted(spec_unit) if s not in referenced]
    for u in units:
        for fn in u["functions"]:
            if fn not in seen:
                f.append(f"CODE:UNIT_FUNCTION_NOT_IN_CODE:{u['id']}:{fn}")
    return {"verdict": "FAIL" if f else "PASS", "major_findings": f, "rows": rows,
            "doxygen": {"status": "NOT_RUN", "warnings": [], "note": "delivered code: trace from the trace map"}}
