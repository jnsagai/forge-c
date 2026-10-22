"""F011-T035 (and the narrow lowering of F011-T033): register-effect proofs of an LL implementation with CBMC, from the
validated register contract of the frozen semantic SWE.1, plus an identity probe of the formal tools on this host.

For each contract operation the harness calls the SWE.2 call of its requirement on the real LL code. Every register
word starts unconstrained (any initial value), and CBMC must show, for EVERY initial value:
- a write: the field holds the encoded value and the preserved bits keep their initial value;
- a whole-register write: the register holds the encoded value;
- a read: the return value is the field of the initial value and the register is unchanged;
- one register word other than the operated one, chosen nondeterministically, is unchanged. That covers every other
  word at once, without a loop over the register file.

Model and limits (recorded with every result): the C semantics on the host with registers as plain memory (no
hardware side effects, a register does not change between two reads), single thread, no interrupts. LL functions are
straight-line; loops are unwound to UNWIND with unwinding assertions, and a function that needs more is INCONCLUSIVE,
never PROVED. A proof says nothing about timing, ordering against other registers, the compiler for the target or
the silicon. It complements the oracle's concrete images, it is not a generalized hardware proof.

    python -m forge_factory.assurance.register_proof --probe --out <identity.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from ..common import pretty_json, utc_now
from . import swe3
from .formal import tool

UNWIND = 8
TOOLS = (("cbmc", ["--version"]), ("goto-cc", ["--version"]), ("frama-c", ["-version"]), ("why3", ["--version"]),
         ("alt-ergo", ["--version"]), ("cvc5", ["--version"]), ("z3", ["--version"]), ("kind2", ["--version"]))
NOT_APPLICABLE = {"kind2": "Kind 2 checks Lustre models; the register-io obligations here are C functions"}


def identity() -> list[dict]:
    """Exact identity of each formal tool on this host; an absent tool is ABSENT, never assumed."""
    out = []
    for name, flag in TOOLS:
        exe = tool(name)
        row = {"tool": name, "path": exe, "status": "PRESENT" if exe else "ABSENT"}
        if exe:
            r = subprocess.run([exe, *flag], capture_output=True, text=True, timeout=60)
            row["version"] = (r.stdout or r.stderr).strip().splitlines()[0][:160] if (r.stdout or r.stderr) else None
            row["sha256"] = hashlib.sha256(Path(exe).resolve().read_bytes()).hexdigest()
        if name in NOT_APPLICABLE:
            row["applicability"] = f"UNSUPPORTED: {NOT_APPLICABLE[name]}"
        out.append(row)
    return out


def _harness(n: int, op: dict, call: str, block: str, count: int) -> list[str]:
    w = int(str(op["offset"]), 0) // 4
    mask, pres = int(op["field_mask"], 16), int(op["preserved_mask"], 16)
    enc = int(op["encoded_value"], 16) if op.get("encoded_value") else 0
    lines = [f"void harness_{n}(void)", "{", f"    __CPROVER_havoc_object((void *){block});",
             "    unsigned k = nondet_u32();", f"    __CPROVER_assume(k < {count}U && k != {w}U);",
             f"    uint32_t other = {block}[k];", f"    uint32_t init = {block}[{w}];"]
    if op["write_kind"] == "none":
        lines += [f"    uint32_t r = (uint32_t)({call});",
                  f'    __CPROVER_assert(r == ((init & 0x{mask:08X}U) >> {op["lsb"]}U), "return is the field");',
                  f'    __CPROVER_assert({block}[{w}] == init, "a read does not write");']
    elif op["write_kind"] == "full_register_write":
        lines += [f"    (void){call};", f'    __CPROVER_assert({block}[{w}] == 0x{enc:08X}U, "whole-register value");']
    else:
        lines += [f"    (void){call};",
                  f'    __CPROVER_assert(({block}[{w}] & 0x{mask:08X}U) == 0x{enc & mask:08X}U, "field value");',
                  f'    __CPROVER_assert(({block}[{w}] & 0x{pres:08X}U) == (init & 0x{pres:08X}U), "preserved bits");']
    return lines + [f'    __CPROVER_assert({block}[k] == other, "other registers unchanged");', "}"]


def prove(ws: Path, include_dirs: list[Path], api_header: str) -> dict:
    """One CBMC proof per contract operation of the frozen SWE.1, on the LL implementation found in include_dirs."""
    from ..layer import layer_of, profile
    from . import register_contract as RC
    from . import safec_oracle as SO
    from .register_contract import call_text

    ws = Path(ws)
    if layer_of(ws) != "LL" or not SO.present(ws):
        return {"status": "NOT_APPLICABLE", "reason": "only LL work orders with a frozen SafeC register contract"}
    if tool("cbmc") is None:
        return {"status": "UNSUPPORTED", "reason": "CBMC is not installed on this host"}
    rec, issues = SO.verified(ws)
    if rec is None:
        return {"status": "BLOCKED", "reason": issues[0], "issues": issues}
    calls = json.loads((ws / RC.CALLS).read_text()).get("calls") or {}
    pr = profile(ws)
    block, count = pr["ll"]["register_block"], pr["ll"]["register_count"]
    per, ops = {}, list(rec["operations"])
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "register_proof.c"
        body = ["#include <stdint.h>", "uint32_t nondet_u32(void);", f"volatile uint32_t {block}[{count}];",
                f'#include "{api_header}"']
        names = {}
        for n, op in enumerate(ops):
            c = calls.get(rec["case_of_intent"].get(op["intent_id"]))
            if not isinstance(c, dict) or not c.get("function"):
                per[op["intent_id"]] = {"status": "NOT_DERIVABLE", "reason": "no SWE.2 call for its case"}
                continue
            names[n] = op["intent_id"]
            body += _harness(n, op, call_text({"function": c["function"], "args": list(c.get("args") or [])}, "10U"),
                             block, count)
        h.write_text("\n".join(body) + "\n")
        for n, iid in names.items():
            r = swe3.bounded_proof(h, include_dirs, unwind=UNWIND, function=f"harness_{n}")
            failed = [c[0] for c in r.get("claims", []) if c[1] == "FAILURE"]
            st = {"PASS": "PROVED", "FAIL": "FAILED"}.get(r["status"], r["status"])
            if st == "FAILED" and all(".unwind." in c for c in failed):
                st = "INCONCLUSIVE"
            per[iid] = {"status": st, "failed_claims": failed[:10], "exit_code": r.get("exit_code")}
    sts = {v["status"] for v in per.values()}
    status = "FAILED" if "FAILED" in sts else ("PROVED" if sts == {"PROVED"} else "INCONCLUSIVE")
    return {"status": status, "operations": per, "unwind": UNWIND, "tools": [t for t in identity() if t["tool"] == "cbmc"],
            "contract_semantic_digest": rec["contract_semantic_digest"],
            "model": ["host C semantics; registers as plain memory with any initial value (no hardware side effects)",
                      "single thread, no interrupts", f"loops unwound to {UNWIND} with unwinding assertions"],
            "not_covered": ["timing and ordering against other registers", "target compiler and silicon behaviour",
                            "errata (not baselined)"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true", help="record the identity of the formal tools on this host")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rep = {"schema": "forge-c/formal-tool-identity/1", "at": utc_now(), "tools": identity(),
           "note": "Identity only. A present tool is not a proof capability for a property until a proof of that "
                   "property ran; no Windows/WSL evidence is reused."}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(rep))
    print(json.dumps([{k: t.get(k) for k in ("tool", "status", "version")} for t in rep["tools"]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
