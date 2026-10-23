"""F011-T033 (Forge-C side of S013-T018): deductive proofs of an LL implementation's register effects with Frama-C WP,
from the C11/ACSL obligations of the frozen semantic SWE.1.

The obligations are SafeC's lowering of the validated contract, kept only after Forge-C re-derived every one
(safec_bridge.obligations), and checked again here against the rebuilt domain before use. For each operation, one
wrapper function carries the obligations WP was measured to decide (FIELD_VALUE, WHOLE_WORD, RETURN_FIELD, FRAME,
NO_WRITE) and makes the SWE.2 call of its requirement on the real LL code, which Frama-C inlines. Bit preservation
(PRESERVED_BITS) is left to the bounded CBMC proof (register_proof), where it is decided.

Statuses: PROVED (every goal of the wrapper proved, runtime-error guards included), NOT_PROVED (a goal is open: WP
cannot tell a false obligation from one it cannot decide, so this is never reported as a refutation),
NOT_DERIVABLE, BLOCKED (the obligations do not verify), UNSUPPORTED (no Frama-C). Model and limits, recorded with
every result: registers as plain memory (volatile accesses read as memory), one thread, no interrupts, one call.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from .formal import tool

WP_ARGS = ["-inline-calls", "@inline", "-wp", "-wp-rte", "-wp-no-volatile", "-wp-prover", "alt-ergo,cvc5",
           "-wp-timeout", "20", "-wp-cache", "none"]
OBLIGATIONS_FILE = "workproducts/SWE.1/register_obligations.json"


def verified(ws: Path) -> tuple[dict | None, list[str]]:
    """The recorded obligations, re-verified against the oracle record's operations and the rebuilt domain."""
    from ..safec_bridge import contract as K
    from ..safec_bridge import domain as D
    from ..safec_bridge import obligations as OB
    from . import safec_oracle as SO

    p = Path(ws) / OBLIGATIONS_FILE
    if not p.is_file():
        return None, ["WP_OBLIGATIONS_ABSENT"]
    rec, issues = SO.verified(ws)
    if rec is None:
        return None, issues
    try:
        ob = json.loads(p.read_text())
        _domain, raw = D.build(ws)
    except (OSError, ValueError, KeyError) as exc:
        return None, [f"WP_OBLIGATIONS_UNREADABLE:{type(exc).__name__}"]
    if ob.get("schema") != "forge-c/lrtx-register-obligations/1" or ob.get("contract_semantic_digest") != \
            rec["contract_semantic_digest"]:
        return None, ["WP_OBLIGATIONS_NOT_OF_THIS_CONTRACT"]
    vc = K.ValidatedContract(rec["contract_semantic_digest"], rec["domain_sha256"], tuple(rec["operations"]),
                             (), (), (), (), {})
    issues = OB.verify(ob["obligations"], vc, raw)
    return (None, issues) if issues else ({**rec, "obligations": ob["obligations"]}, [])


def _goals(text: str) -> tuple[int, int] | None:
    m = re.search(r"Proved goals:\s*(\d+)\s*/\s*(\d+)", text)
    return (int(m[1]), int(m[2])) if m else None


def prove(ws: Path, include_dirs: list[Path], api_header: str) -> dict:
    """One WP run per contract operation of the frozen SWE.1, on the LL implementation found in include_dirs."""
    from ..layer import layer_of, profile
    from ..safec_bridge import obligations as OB
    from . import register_contract as RC
    from .register_contract import call_text
    from .register_proof import identity

    ws = Path(ws)
    if layer_of(ws) != "LL" or not (ws / OBLIGATIONS_FILE).is_file():
        return {"status": "NOT_APPLICABLE", "reason": "only LL work orders with frozen SafeC formal obligations"}
    fc = tool("frama-c")
    if fc is None:
        return {"status": "UNSUPPORTED", "reason": "Frama-C is not installed on this host"}
    rec, issues = verified(ws)
    if rec is None:
        return {"status": "BLOCKED", "reason": issues[0], "issues": issues}
    calls = json.loads((ws / RC.CALLS).read_text()).get("calls") or {}
    pr = profile(ws)
    block, count = pr["ll"]["register_block"], pr["ll"]["register_count"]
    per = {}
    inc = " ".join(f"-I{Path(d).resolve()}" for d in include_dirs)
    with tempfile.TemporaryDirectory() as td:
        for n, op in enumerate(rec["operations"]):
            c = calls.get(rec["case_of_intent"].get(op["intent_id"]))
            if not isinstance(c, dict) or not c.get("function"):
                per[op["intent_id"]] = {"status": "NOT_DERIVABLE", "reason": "no SWE.2 call for its case"}
                continue
            clauses, _ = OB.lower(op, block)
            used = [(i, a) for i, a in clauses if OB.applicability(i)[OB.WP] == "SUPPORTED"]
            call = call_text({"function": c["function"], "args": list(c.get("args") or [])}, "10U")
            body = f"return (uint32_t)({call});" if op["write_kind"] == "none" else f"(void){call};"
            ret = "uint32_t" if op["write_kind"] == "none" else "void"
            h = Path(td) / f"wp_{n}.c"
            h.write_text("\n".join(["#include <stdint.h>", f"volatile uint32_t {block}[{count}];",
                                    f'#include "{api_header}"',
                                    "/*@ " + "\n    ".join(a for _, a in used) + " */",
                                    f"{ret} wp_{n}(void)", "{", f"    {body}", "}"]) + "\n")
            try:
                r = subprocess.run([fc, f"-cpp-extra-args={inc}", *WP_ARGS, "-wp-fct", f"wp_{n}", str(h)],
                                   capture_output=True, text=True, timeout=900, cwd=td)
                goals = _goals(r.stdout)
            except subprocess.TimeoutExpired:
                goals = None
            if goals is None:
                per[op["intent_id"]] = {"status": "NOT_PROVED", "reason": "Frama-C gave no goal count",
                                        "obligations": [i for i, _ in used]}
                continue
            per[op["intent_id"]] = {"status": "PROVED" if goals[0] == goals[1] else "NOT_PROVED",
                                    "goals_proved": goals[0], "goals": goals[1], "obligations": [i for i, _ in used],
                                    "left_to_cbmc": [i for i, a in clauses if (i, a) not in used]}
    sts = {v["status"] for v in per.values()}
    status = "PROVED" if sts == {"PROVED"} else ("NOT_PROVED" if "NOT_PROVED" in sts else "NOT_DERIVABLE")
    return {"status": status, "operations": per, "wp_arguments": WP_ARGS,
            "tools": [t for t in identity() if t["tool"] in ("frama-c", "why3", "alt-ergo", "cvc5")],
            "contract_semantic_digest": rec["contract_semantic_digest"],
            "obligations_digest": rec["obligations"]["obligations_digest"],
            "model": ["host C semantics; registers as plain memory (volatile accesses read as memory)",
                      "single thread, no interrupts; one call per operation"],
            "not_covered": ["bit preservation (PRESERVED_BITS): decided by the bounded CBMC proof, not by WP here",
                            "key sequence order, hardware side effects, reset and timing, concurrency",
                            "target compiler and silicon behaviour"]}
