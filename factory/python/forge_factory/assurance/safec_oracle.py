"""F011-T034: the SafeC register-image oracle of the frozen SWE.1 contract, as checks of the EASA C oracle.

The semantic SWE.1 (local-rtx-v2) records workproducts/SWE.1/register_oracle.json. Before any of it is used:
- the domain is rebuilt from the work order's RM sections and must be the one the contract was bound to;
- every contract operation is recomputed by `contract.reference_operation` from the domain facts;
- every oracle case is re-derived by `oracle.reference_cases` and the oracle digest and binding are checked.
Any difference blocks (`SAFEC_ORACLE_BLOCKED:`), it is never skipped silently.

Each case then becomes one C check on the real register array: the register starts at the case's initial image, every
other word at a non-zero background, the SWE.2 call of the case's requirement runs, and the whole register word must
equal the expected image, every other register word must be unchanged and a query must return the expected field
value. Only LL work orders are checked this way: an LL call is one register effect, while a
HAL call may poll and sequence (the existing contract cases keep covering HAL).
"""
from __future__ import annotations

import json
from pathlib import Path

FILE = "workproducts/SWE.1/register_oracle.json"


def present(ws: Path) -> bool:
    return (Path(ws) / FILE).is_file()


def _intent_of(op: dict) -> dict:
    return {"intent_id": op["intent_id"], "action": op["action"], "register": op["register"], "field": op["field"],
            "logical_value": op.get("logical_value"), "source_fact_ids": list(op["source_fact_ids"]),
            "precondition_fact_ids": list(op.get("precondition_fact_ids") or [])}


def verified(ws: Path) -> tuple[dict | None, list[str]]:
    from ..safec_bridge import contract as K
    from ..safec_bridge import contracts as C
    from ..safec_bridge import domain as D
    from ..safec_bridge import oracle as O

    try:
        rec = json.loads((Path(ws) / FILE).read_text())
        domain, raw = D.build(ws)
    except (OSError, ValueError, KeyError) as exc:
        return None, [f"SAFEC_ORACLE_BLOCKED:UNREADABLE:{type(exc).__name__}"]
    if rec.get("schema") != "forge-c/lrtx-register-oracle/1":
        return None, ["SAFEC_ORACLE_BLOCKED:SCHEMA"]
    if C.sha256_bytes(raw) != rec["domain_sha256"]:
        return None, ["SAFEC_ORACLE_BLOCKED:DOMAIN_CHANGED (the RM sections differ from those of the frozen contract)"]
    issues = []
    for op in rec["operations"]:
        try:
            ref = K.reference_operation(domain, _intent_of(op))
        except (StopIteration, KeyError, ValueError) as exc:
            issues.append(f"SAFEC_ORACLE_BLOCKED:REFERENCE_UNAVAILABLE:{op.get('intent_id')}:{type(exc).__name__}")
            continue
        issues += [f"SAFEC_ORACLE_BLOCKED:ENGINES_DISAGREE:{op['intent_id']}:{k}" for k, v in ref.items()
                   if op.get(k) != v]
    vc = K.ValidatedContract(rec["contract_semantic_digest"], rec["domain_sha256"], tuple(rec["operations"]),
                             (), (), (), (), {})
    issues += [f"SAFEC_ORACLE_BLOCKED:{i}" for i in O.verify(rec["oracle"], vc, raw)]
    return (None, issues) if issues else (rec, [])


def cases(ws: Path, effects: dict[str, dict], calls: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """effects: register_effects case -> effect (with swr); calls: SWE.2 api_calls case -> {function, args}."""
    from ..layer import layer_of

    if not present(ws) or layer_of(ws) != "LL":
        return [], []
    rec, issues = verified(ws)
    if rec is None:
        return [], issues
    out, notes = [], []
    for c in rec["oracle"]["cases"]:
        name = rec["case_of_intent"].get(c["intent_id"])
        e, call = effects.get(name), calls.get(name)
        if e is None or not isinstance(call, dict) or not call.get("function"):
            notes.append(f"SAFEC_ORACLE_NOT_DERIVABLE:{c['intent_id']}:no SWE.1 effect or SWE.2 call for {name}")
            continue
        out.append({"swr": e.get("swr"), "case": f"{name}@{c['initial']}", "register": c["register"],
                    "function": call["function"], "args": list(call.get("args") or []),
                    "word": int(str(c["offset"]), 0) // 4, "initial": int(c["initial"], 16),
                    "after": int(c["expected_after"], 16),
                    "ret": None if c["expected_return"] is None else int(c["expected_return"])})
    return out, notes


def source(cases_: list[dict], count: int) -> tuple[str, str]:
    """(helper definitions placed before main, the call placed before main returns)."""
    from .register_contract import call_text

    # every other register word starts from a non-zero background, so that a stray write (of 0 in particular, e.g.
    # to a read-only register) changes a word the check compares (F011-T034: a zeroed file hid such writes)
    body = ["static int forge_others_same(const uint32_t *b, unsigned w)", "{", "    unsigned i;",
            f"    for (i = 0U; i < {count}U; i++) {{ if (i != w && regs[i] != b[i]) {{ return 0; }} }}",
            "    return 1;", "}", "static void forge_background(void)", "{", "    unsigned i;",
            f"    for (i = 0U; i < {count}U; i++) {{ regs[i] = 0xA5A50000U | i; }}", "}",
            "static void forge_safec_cases(int first)", "{", f"    uint32_t b[{count}];"]
    for n, c in enumerate(cases_):
        call = call_text(c, "10U")
        body += [f"    /* {c['swr']} {c['case']}: SafeC register-image oracle (contract + RM facts only) */",
                 "    forge_background();", f"    regs[{c['word']}U] = 0x{c['initial']:08X}U;",
                 "    memcpy(b, (const void *)regs, sizeof b);",
                 f"    {{ uint32_t r = (uint32_t)({call});" if c["ret"] is not None else f"    {{ (void){call};",
                 f"      int ok = (regs[{c['word']}U] == 0x{c['after']:08X}U) && forge_others_same(b, {c['word']}U)"
                 + (f" && (r == {c['ret']}U);" if c["ret"] is not None else ";"),
                 f'      printf("OR-%03d {c["swr"]} {c["case"]} %s\\n", first + {n}, ok ? "PASS" : "FAIL"); '
                 "fails += !ok; }"]
    body += ["}"]
    return "\n".join(body), "    forge_safec_cases({first});"
