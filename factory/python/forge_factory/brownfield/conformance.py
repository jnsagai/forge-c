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
from . import DELIVERY_DIR, manifest_of, reference_paths
from . import scope as S

EFFECTS = "workproducts/SWE.1/register_effects.json"
INVARIANT_RX = re.compile(r"^While no\b.{0,80}\bhas been (called|requested)\b", re.I)  # initial-state requirement
CALLS = "workproducts/SWE.2/api_calls.json"
ARCH = "workproducts/SWE.2/software_architecture.md"


def _field_mask(register: str, field: str, macros: dict[str, str], prefix: str = "RCC") -> int | None:
    """Bit mask of RM field `register.field` from the delivered macros (forge: LL_<P>_<REG>_<FIELD>_MSK; CMSIS:
    <P>_<REG>_<FIELD>_Msk or <P>_<REG>_<FIELD>), P the work order's register prefix (feature 015: RCC was
    hard-coded, so every CRC field read 'has no definition in the delivered code')."""
    reg = register.removeprefix(f"{prefix}_")
    for name in (f"LL_{prefix}_{reg}_{field}_MSK", f"{prefix}_{reg}_{field}_Msk", f"{prefix}_{reg}_{field}"):
        if name in macros:
            v = S.evaluate(name, macros)
            if v:
                return v
    return None


def _rm_fields(ws: Path) -> dict[tuple[str, str], int]:
    """(register, field) -> bit mask from the work order's RM register sections (feature 015: a field the RM names
    differently from the vendor macros, e.g. RM CRC_INIT.CRC_INIT vs CMSIS CRC_INIT_INIT, is still checkable; the
    requirements are RM-derived)."""
    from ..inspection.regmap import rm_registers

    try:
        regs = rm_registers(ws)
    except (OSError, ValueError, KeyError):
        return {}
    return {(r, f): ((1 << (msb - lsb + 1)) - 1) << lsb for r, v in regs.items() for f, (msb, lsb) in v["fields"].items()}


def _clears_by_zero(exps: list[dict], register: str) -> bool:
    on = [x for x in exps if x.get("register") == register and x.get("op") != "no_write"]
    return bool(on) and all(x.get("op") == "write" and str(x.get("value")) in ("0", "0x0", "0x00") for x in on)


def _allocated_functions(ws: Path, names: set[str]) -> set[str]:
    """Delivered functions named in any requirement row of the SWE.2 architecture tables (any column: b005 put the
    function in the third column, and query requirements have no register-effect case to link them)."""
    from ..assurance.oracle_gen import allocation

    p = Path(ws) / ARCH
    if not p.is_file():
        return set()
    from ..layer import profile

    pr = profile(ws)
    pfx = (pr["hal"]["function_prefix"], pr["ll"]["function_prefix"])
    return {f for fns in allocation(p.read_text(errors="replace"), names, pfx).values() for f in fns}


def check(ws: Path, phase: str, write: bool = True) -> dict:
    ws = Path(ws)
    m = manifest_of(ws)
    style = (m.get("delivery") or {}).get("build", {}).get("style", "forge")
    from ..layer import register_prefix

    pfx = register_prefix(ws)
    rm_fields = _rm_fields(ws) if pfx != "RCC" else {}
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

    def add(kind: str, function: str, requirement: str, evidence: str, reference: str = "", status: str = "OPEN") -> None:
        key = (kind, function, requirement, evidence)
        if any((f["kind"], f["function"], f["requirement"], f["evidence"]) == key for f in findings):
            return
        findings.append({"id": f"CF-{len(findings) + 1:03d}", "kind": kind, "function": function,
                         "requirement": requirement, "reference": reference, "evidence": evidence, "status": status})

    from ..inspection.swtrace import swr_texts

    invariants = {sid for sid, text in swr_texts(ws).items() if INVARIANT_RX.search(text)}
    used: set[str] = set()
    by_case: dict[str, list[dict]] = {}
    for e in effects:
        by_case.setdefault(e.get("case", ""), []).append(e)
    # feature 015: one requirement may set coupled fields in one call (ST: a reversal mode writes REV_IN with RTYPE_IN,
    # a prescaler MBR with BPASS), stated as one effect case per field; outside RCC the bits a function may change
    # are those its requirement names across all its cases
    swr_bits: dict[tuple[str, str], dict[str, int]] = {}
    if pfx != "RCC":
        for case, exps in by_case.items():
            fn_ = str((calls.get(case) or {}).get("function", ""))
            for x in exps:
                if x.get("op") != "no_write" and x.get("register"):
                    mk = _field_mask(x["register"], x.get("field") or "", macros, pfx) or \
                        rm_fields.get((x["register"], x.get("field") or ""))
                    if mk:
                        b = swr_bits.setdefault((fn_, x.get("swr", "")), {})
                        b[x["register"]] = b.get(x["register"], 0) | mk
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
        got = S.register_effects(defs[fn], macros, style, [str(a) for a in call.get("args") or []], defs, prefix=pfx)
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
            mask = _field_mask(reg or "", field or "", macros, pfx) or rm_fields.get((reg or "", field or ""))
            if mask is None:
                add("CONTRADICTION", fn, swr, f"case {case}: field {reg}.{field} has no definition in the delivered "
                    "code (cannot be checked)")
                continue
            expected_bits[reg] = expected_bits.get(reg, 0) | mask
            if op == "write":  # feature 009: the field must hold the value (a whole-register write is expected)
                lsb = (mask & -mask).bit_length() - 1
                want = (int(str(x.get("value")), 0) << lsb) & mask if x.get("value") is not None else None
                ops = ("write",) if pfx == "RCC" else ("write", "modify")  # CMSIS MODIFY_REG(reg, field, value)
                computed = [g for g in writes if g.register == reg and g.op in ops]
                if pfx != "RCC" and want is not None and computed and all(g.mask is None for g in computed):
                    # feature 015: the delivered code computes the value (ST LL_USART_SetBaudRate: BRR from the clock,
                    # prescaler table and oversampling); not decidable statically, so stated and left to the
                    # requirement-based tests (SWE.4/SWE.6) instead of a false contradiction; never a pass claim
                    add("DEFERRED_TO_TESTS", fn, swr, f"case {case}: {reg}.{field} = {x.get('value')} is computed by "
                        "the delivered code (" + "; ".join(g.text.strip()[:60] for g in computed) + ")",
                        x.get("source", ""), status="DEFERRED")
                    continue
                if not any(g.register == reg and g.op in ops and g.mask is not None and want is not None
                           and g.mask & mask == want for g in writes):
                    add("CONTRADICTION", fn, swr, f"case {case}: expected {reg}.{field} = {x.get('value')}; the code "
                        "does: " + ("; ".join(f"{g.op} {g.register} {g.mask if g.mask is None else hex(g.mask)}"
                                              for g in writes) or "no register write"))
                continue
            hit = [g for g in writes if g.register == reg and g.op == op and g.mask is not None and g.mask & mask]
            if not hit and pfx != "RCC" and op in ("set", "clear"):  # ST: MODIFY_REG(reg, FIELD, value) with the
                # value bound: sets the field when the value holds it, clears it when the value leaves it 0
                hit = [g for g in writes if g.register == reg and g.op == "modify" and g.mask is not None
                       and g.clear is not None and g.clear & mask == mask
                       and g.mask & mask == (mask if op == "set" else 0)]
            if not hit:
                seen = "; ".join(f"{g.op} {g.via or g.register} mask {g.mask if g.mask is None else hex(g.mask)}"
                                 for g in writes) or "no register write"
                add("CONTRADICTION", fn, swr, f"case {case}: expected {op} {reg}.{field} (mask {hex(mask)}); "
                    f"the code does: {seen}")
        for g in writes:  # extra effects beyond what the requirement cases of this function state
            allowed = expected_bits.get(g.register)
            if pfx != "RCC":
                allowed = swr_bits.get((fn, swr), {}).get(g.register, allowed)
            if allowed is None and any(x.get("op") != "no_write" for x in exps):
                add("CONTRADICTION", fn, swr, f"case {case}: writes {g.via or g.register} which no requirement of "
                    f"this case names ({g.text.strip()[:80]})")
            elif allowed is not None and g.mask is not None and g.mask & ~allowed and not (
                    pfx != "RCC" and g.op == "write" and not g.via and g.mask == (~allowed & 0xFFFFFFFF)
                    and _clears_by_zero(exps, g.register)):
                # feature 015: an rc_w0 flag clear (ST TIM: WRITE_REG(TIMx->SR, ~TIM_SR_UIF)) writes 1, i.e. no
                # change, to every other flag; accepted only when the requirement writes 0 to exactly those fields
                add("CONTRADICTION", fn, swr, f"case {case}: changes {g.register} bits {hex(g.mask & ~allowed)} that "
                    "the requirement does not name")
            if g.op == "write" and not g.via and not any(x.get("op") == "write" for x in exps):
                add("CONTRADICTION", fn, swr, f"case {case}: plain write to shared register {g.register} overwrites "
                    f"its other bits ({g.text.strip()[:80]})")
    allocated = _allocated_functions(ws, set(scope)) | used
    for fn in scope:
        if fn not in allocated:
            add("NO_REQUIREMENT", fn, "", f"delivered scope function {fn} implements no requirement case and is not "
                "in the SWE.2 allocation table")
    rec = {"schema": "forge-c/conformance/0.1", "phase": phase, "checked_at": utc_now(), "findings": findings}
    if write:
        (ws / DELIVERY_DIR).mkdir(parents=True, exist_ok=True)
        (ws / DELIVERY_DIR / "conformance.json").write_text(pretty_json(rec))
    return {"status": "FINDINGS" if any(f["status"] == "OPEN" for f in findings) else "CONFORMANT",
            "findings": findings, "issues": []}
