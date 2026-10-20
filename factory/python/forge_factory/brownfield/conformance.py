"""Conformance of delivered code to independently derived requirements (US2, FR-008, research R6).

Inputs (all frozen work products, never agent replies):
* `workproducts/SWE.1/register_effects.json` - per requirement case: register, field, op (set | clear | no_write);
* `workproducts/SWE.2/api_calls.json` - per case: the delivered function (and arguments) that implements it, or
  "NONE" when no delivered function does;
* the delivered code and its dependency headers (field masks come from the RM-derived names via the code's macros).

Findings: NO_CODE (a case's function is NONE or not delivered), NO_REQUIREMENT (a scope function no case or
allocation row uses), CONTRADICTION (the function's register effects differ from the requirement: wrong register,
wrong bit, wrong operation, extra writes, or a plain write that overwrites other bits of a shared register)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import pretty_json, utc_now
from . import DELIVERY_DIR, delivered_paths, manifest_of, reference_paths
from . import scope as S

EFFECTS = "workproducts/SWE.1/register_effects.json"
INVARIANT_RX = re.compile(r"^While no\b.{0,80}\bhas been (called|requested)\b", re.I)  # initial-state requirement
CALLS = "workproducts/SWE.2/api_calls.json"
ARCH = "workproducts/SWE.2/software_architecture.md"


def _field_mask(register: str, field: str, macros: dict[str, str]) -> int | None:
    """Bit mask of RM field `register.field` from the delivered macros (forge: LL_RCC_<REG>_<FIELD>_MSK; CMSIS:
    RCC_<REG>_<FIELD>_Msk or RCC_<REG>_<FIELD>)."""
    reg = register.removeprefix("RCC_")
    for name in (f"LL_RCC_{reg}_{field}_MSK", f"RCC_{reg}_{field}_Msk", f"RCC_{reg}_{field}"):
        if name in macros:
            v = S.evaluate(name, macros)
            if v:
                return v
    return None


def _allocated_functions(ws: Path) -> set[str]:
    """Function names in the SWE.2 requirement allocation table (a function allocated to any requirement)."""
    p = Path(ws) / ARCH
    if not p.is_file():
        return set()
    names, on = set(), False
    for ln in p.read_text(errors="replace").splitlines():
        if ln.startswith("## "):
            on = "allocation" in ln.lower()
            continue
        if on and ln.startswith("|") and re.search(r"\bSWR-\d+", ln):
            names |= set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", ln.split("|")[2] if ln.count("|") > 2 else ""))
    return names


def check(ws: Path, phase: str, write: bool = True) -> dict:
    ws = Path(ws)
    m = manifest_of(ws)
    style = (m.get("delivery") or {}).get("build", {}).get("style", "forge")
    texts = {rel: (ws / rel).read_text(errors="replace") for rel in reference_paths(m) if (ws / rel).is_file()}
    macros = S.constant_macros(list(texts.values()))
    defs = {d.name: d for rel in reversed(list(texts)) for d in S.index(texts[rel], rel)}  # delivered wins
    scope_p = ws / DELIVERY_DIR / "scope.json"
    scope = [x["name"] for x in json.loads(scope_p.read_text()).get("functions", [])] if scope_p.is_file() else []
    try:
        effects = json.loads((ws / EFFECTS).read_text()).get("effects", [])
        calls = json.loads((ws / CALLS).read_text()).get("calls", {})
    except (OSError, ValueError) as exc:
        return {"status": "NOT_RUN", "findings": [], "issues": [f"CONFORMANCE_INPUT_MISSING:{exc}"]}
    findings: list[dict] = []

    def add(kind: str, function: str, requirement: str, evidence: str, reference: str = "") -> None:
        key = (kind, function, requirement, evidence)
        if any((f["kind"], f["function"], f["requirement"], f["evidence"]) == key for f in findings):
            return
        findings.append({"id": f"CF-{len(findings) + 1:03d}", "kind": kind, "function": function,
                         "requirement": requirement, "reference": reference, "evidence": evidence, "status": "OPEN"})

    from ..inspection.swtrace import swr_texts

    invariants = {sid for sid, text in swr_texts(ws).items() if INVARIANT_RX.search(text)}
    used: set[str] = set()
    by_case: dict[str, list[dict]] = {}
    for e in effects:
        by_case.setdefault(e.get("case", ""), []).append(e)
    for case, exps in by_case.items():
        swr = exps[0].get("swr", "")
        call = calls.get(case) or {}
        fn = str(call.get("function", ""))
        if fn.upper() == "NONE" and swr in invariants and all(x.get("op") == "no_write" for x in exps):
            continue  # an initial-state invariant ('While no ... has been called ... shall not write'): nothing to
            # call, met by the absence of start-up code and verified by the reset-state tests
        if not fn or fn.upper() == "NONE" or fn not in defs:
            add("NO_CODE", "" if fn.upper() in ("", "NONE") else fn, swr,
                f"case {case}: no delivered function implements it" + (f" ({fn} is not in the delivered code)"
                                                                        if fn and fn.upper() != "NONE" else ""))
            continue
        used.add(fn)
        got = S.register_effects(defs[fn], macros, style, [str(a) for a in call.get("args") or []], defs)
        writes = [g for g in got if g.op != "read"]
        expected_bits: dict[str, int] = {}
        for x in exps:
            reg, field, op = x.get("register"), x.get("field"), x.get("op")
            if op == "no_write" and not reg:
                continue  # 'no register access' for one input (e.g. an invalid parameter): branch-dependent, so
                # it is judged by the requirement-based tests, not by static extraction
            if op == "no_write":
                bad = [g for g in writes if g.register == reg]
                for g in bad:
                    add("CONTRADICTION", fn, swr, f"case {case}: requirement says no write to {reg or 'any register'}; "
                        f"the code does {g.op} on {g.via or g.register} ({g.text.strip()[:80]})", x.get("source", ""))
                continue
            mask = _field_mask(reg or "", field or "", macros)
            if mask is None:
                add("CONTRADICTION", fn, swr, f"case {case}: field {reg}.{field} has no definition in the delivered "
                    "code (cannot be checked)")
                continue
            expected_bits[reg] = expected_bits.get(reg, 0) | mask
            hit = [g for g in writes if g.register == reg and g.op == op and g.mask is not None and g.mask & mask]
            if not hit:
                seen = "; ".join(f"{g.op} {g.via or g.register} mask {g.mask if g.mask is None else hex(g.mask)}"
                                 for g in writes) or "no register write"
                add("CONTRADICTION", fn, swr, f"case {case}: expected {op} {reg}.{field} (mask {hex(mask)}); "
                    f"the code does: {seen}")
        for g in writes:  # extra effects beyond what the requirement cases of this function state
            allowed = expected_bits.get(g.register)
            if allowed is None and any(x.get("op") != "no_write" for x in exps):
                add("CONTRADICTION", fn, swr, f"case {case}: writes {g.via or g.register} which no requirement of "
                    f"this case names ({g.text.strip()[:80]})")
            elif allowed is not None and g.mask is not None and g.mask & ~allowed:
                add("CONTRADICTION", fn, swr, f"case {case}: changes {g.register} bits {hex(g.mask & ~allowed)} that "
                    "the requirement does not name")
            if g.op == "write" and not g.via:
                add("CONTRADICTION", fn, swr, f"case {case}: plain write to shared register {g.register} overwrites "
                    f"its other bits ({g.text.strip()[:80]})")
    allocated = _allocated_functions(ws) | used
    for fn in scope:
        if fn not in allocated:
            add("NO_REQUIREMENT", fn, "", f"delivered scope function {fn} implements no requirement case and is not "
                "in the SWE.2 allocation table")
    rec = {"schema": "forge-c/conformance/0.1", "phase": phase, "checked_at": utc_now(), "findings": findings}
    if write:
        (ws / DELIVERY_DIR).mkdir(parents=True, exist_ok=True)
        (ws / DELIVERY_DIR / "conformance.json").write_text(pretty_json(rec))
    return {"status": "FINDINGS" if findings else "CONFORMANT", "findings": findings, "issues": []}
