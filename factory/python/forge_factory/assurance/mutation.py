"""EASA-T043/T047/T067 and AT-044/AT-047/AT-075 — deterministic mutation campaign (project measure, NOT an ISO
26262 threshold).

Every mutant has a content-addressed id and a recorded outcome:
  KILLED      a test failed / crashed / timed out on the mutant
  SURVIVED    every test passed on the mutant           -> adequacy claim UNSUPPORTED until reviewed
  INVALID     the mutant does not compile (stillborn)    -> excluded, counted
  EQUIVALENT  provably no behaviour change, with a recorded reason (unused definition, unreachable from the unit
              under test) - never assumed silently
A score without mutant ids, or counts that do not add up, is rejected (AT-075).
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import contracts

OPS = [  # name, regex, replacement (None = computed)
    ("OR_TO_AND", r"\|= ", "&= "), ("CLR_TO_SET", r"&= ~", "|= "), ("NE0_TO_EQ0", r"!= 0U", "== 0U"),
    ("EQ0_TO_NE0", r"== 0U", "!= 0U"), ("LT_TO_LE", r" < ", " <= "), ("GT_TO_GE", r" > ", " >= "),
    ("OK_TO_ERROR", r"= HAL_OK;", "= HAL_ERROR;"), ("TIMEOUT_TO_OK", r"= HAL_TIMEOUT;", "= HAL_OK;"),
    ("RET1_TO_0", r"\? 1U : 0U", "? 0U : 1U"),
    ("DROP_CALL", r"^(\s+)((?:disable_osc|enable)|LL_RCC_\w+)\(\);", r"\1/*dropped*/;"),
    ("INC_DROP", r"count\+\+;", ";"), ("HSI_TO_HSE_MSK", r"HSION_MSK", "HSEON_MSK"),
    ("HSE_TO_HSI_MSK", r"HSEON_MSK", "HSION_MSK"), ("ADC_TO_DMA", r"ADC12EN_MSK", "GPDMA1EN_MSK"),
    ("SR_TO_CR", r"LL_RCC_SR_OFFSET / 4U", "LL_RCC_CR_OFFSET / 4U"),
    ("DEF_BIT_SHIFT", r"(#define LL_RCC_\w+_MSK )0x0000000([1248])U", None),
    ("DEF_OFFSET_SHIFT", r"(#define LL_RCC_\w+_OFFSET )0x(\w+)U", None),
]
OPERATOR_SET_VERSION = "forge-mut-ops/1.0"
RCC_ONLY = {"HSI_TO_HSE_MSK", "HSE_TO_HSI_MSK", "ADC_TO_DMA", "SR_TO_CR"}  # RCC register/field names


def ops_for(prefix: str = "RCC") -> list[tuple]:
    """Feature 009: the operator set for a peripheral - the generic operators on its LL_<PPP>_ names; the operators
    written for RCC fields/registers apply to RCC only (they cannot match another peripheral's code)."""
    if prefix == "RCC":
        return OPS
    return [(n, rx.replace("LL_RCC_", f"LL_{prefix}_"), rep) for n, rx, rep in OPS if n not in RCC_ONLY]


def mutants(text: str, prefix: str = "RCC") -> list[dict]:
    out = []
    for name, rx, rep in ops_for(prefix):
        for m in re.finditer(rx, text, re.M):
            if name == "DEF_BIT_SHIFT":
                new = m.group(1) + "0x0000000%xU" % ((int(m.group(2)) << 1) & 0xF or 1)
            elif name == "DEF_OFFSET_SHIFT":
                new = m.group(1) + "0x%03XU" % (int(m.group(2), 16) + 4)
            else:
                new = m.expand(rep)
            mtext = text[:m.start()] + new + text[m.end():]
            line = text.count("\n", 0, m.start()) + 1
            mid = "MUT-" + hashlib.sha256(f"{name}|{line}|{m.start()}|{new}".encode()).hexdigest()[:12]
            out.append({"id": mid, "op": name, "line": line, "original": text.splitlines()[line - 1].strip(),
                        "text": mtext})
    return out


def equivalence_reason(text: str, mut: dict, used_symbols: set[str], referenced: set[str] | None = None) -> str | None:
    """Only two mechanically provable equivalence classes; anything else is not assumed equivalent.
    A definition is equivalent only if NOTHING references it: not the file itself, not another source, not a test
    (a test using the macro shares the definition as its oracle - that mutant must stay a survivor)."""
    line = text.splitlines()[mut["line"] - 1]
    d = re.match(r"\s*#\s*define\s+(\w+)", line)
    if d:
        return f"definition {d.group(1)} is referenced by no code or test" if d.group(1) not in (referenced or set()) \
            else None
    fn = None
    for m in re.finditer(r"^[\w\s\*]*?\b(\w+)\s*\([^;{)]*\)\s*\{", text, re.M):
        if text.count("\n", 0, m.start()) + 1 <= mut["line"]:
            fn = m.group(1)
    if fn and fn not in used_symbols and not line.lstrip().startswith("#"):
        return f"mutated function {fn} is not called by the unit under test"
    return None


def run_campaign(sw_dir: Path, target_rel: str, test_files: list[Path], *, used_symbols: set[str] | None = None,
                 extra_sources: list[str] | None = None, timeout_s: int = 5, cc: str = "gcc", prefix: str = "RCC",
                 ll_unit: str = "stm32n6xx_ll_rcc.c") -> dict:
    """`prefix`/`ll_unit` (feature 009): the work order's register prefix and generated LL compile unit."""
    """Mutate one file of a copied tree, rebuild every test program and run it. Never touches `sw_dir`."""
    src = (Path(sw_dir) / target_rel).read_text()
    code_hash = hashlib.sha256(src.encode()).hexdigest()
    used = used_symbols if used_symbols is not None else set()
    others = [p.read_text(errors="replace") for p in Path(sw_dir).rglob("*") if p.is_file() and p.suffix in (".c", ".h")
              and p.resolve() != (Path(sw_dir) / target_rel).resolve()
              and p.read_text(errors="replace") != src] + [t.read_text(errors="replace") for t in test_files]
    # (byte-identical copies of the target, e.g. the packager's flat include/ view, are the same definition)
    own_body = "\n".join(ln for ln in src.splitlines() if not re.match(r"\s*#\s*define\b", ln))
    referenced = set(re.findall(r"\b[A-Za-z_]\w*\b", own_body + "\n".join(others)))
    results = []
    tool = subprocess.run([cc, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    for mu in mutants(src, prefix):
        eq = equivalence_reason(src, mu, used, referenced) if used_symbols is not None else None
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "sw"
            shutil.copytree(sw_dir, t)
            (t / target_rel).write_text(mu["text"])
            if target_rel.startswith("ll/") and (t / "include").is_dir():
                shutil.copy(t / target_rel, t / "include" / Path(target_rel).name)
            inc = sum((["-I", str(t / d)] for d in ("tests/unit/ll_fake", "include", "ll", "hal") if (t / d).is_dir()), [])
            # driver compile units: software/src (packaged flat view) or software/hal (live workspace); the generated
            # LL compile unit only includes the header and is skipped (the tests include the header themselves)
            by_name = {p.name: str(p) for d in ("src", "hal") for p in sorted((t / d).glob("*.c"))
                       if not p.name.endswith(ll_unit.removeprefix("stm32n6xx_"))}  # flat view duplicates hal/*.c
            if target_rel.endswith(".c"):
                by_name[Path(target_rel).name] = str(t / target_rel)  # always the mutated copy
            srcs = sorted(by_name.values()) + [str(t / s) for s in (extra_sources or [])]
            outcome, detail = "SURVIVED", None
            for tc in test_files:
                exe = Path(td) / ("x_" + tc.stem)
                b = subprocess.run([cc, "-std=c99", "-O0", "-w", *inc, *srcs, str(tc), "-o", str(exe)],
                                   capture_output=True, text=True)
                if b.returncode:
                    outcome, detail = "INVALID", b.stderr.strip().splitlines()[-1][:120] if b.stderr.strip() else "build"
                    break
                try:
                    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=timeout_s)
                    if r.returncode or re.search(r"\bFAIL\b", r.stdout):
                        outcome, detail = "KILLED", f"{tc.name}: " + next((x for x in r.stdout.splitlines() if "FAIL" in x),
                                                                        f"exit {r.returncode}")[:80]
                        break
                except subprocess.TimeoutExpired:
                    outcome, detail = "KILLED", f"{tc.name}: timeout"
                    break
        if outcome == "SURVIVED" and eq:
            outcome, detail = "EQUIVALENT", eq
        results.append({k: v for k, v in mu.items() if k != "text"} | {"outcome": outcome, "detail": detail})
    n = {k: sum(r["outcome"] == k for r in results) for k in ("KILLED", "SURVIVED", "INVALID", "EQUIVALENT")}
    rec = {"campaign_id": "MC-" + hashlib.sha256((code_hash + "".join(t.name for t in test_files)).encode()).hexdigest()[:12],
           "code_hash": code_hash, "operator_set": [OPERATOR_SET_VERSION] + sorted({o[0] for o in ops_for(prefix)}),
           "eligible": n["KILLED"] + n["SURVIVED"], "killed": n["KILLED"], "survived": n["SURVIVED"],
           "equivalent": n["EQUIVALENT"], "invalid": n["INVALID"], "mutant_refs": [r["id"] for r in results],
           "tool_version": tool, "result": "MEASURED" if results else "UNKNOWN"}
    return {"record": rec, "mutants": results, "schema_issues": contracts.errors("mutation-campaign", rec)}


def validate_campaign(rec: dict) -> list[str]:
    """AT-075: a mutation claim needs per-mutant ids and consistent populations; a bare score is rejected."""
    issues = contracts.errors("mutation-campaign", rec)
    if rec.get("result") == "MEASURED":
        refs = rec.get("mutant_refs") or []
        if not refs:
            issues.append("MUTATION_SCORE_WITHOUT_MUTANT_IDS")
        total = sum(int(rec.get(k) or 0) for k in ("killed", "survived", "equivalent", "invalid"))
        if refs and total != len(refs):
            issues.append(f"MUTANT_POPULATION_MISMATCH:{total}!={len(refs)}")
        if rec.get("eligible") != (rec.get("killed") or 0) + (rec.get("survived") or 0):
            issues.append("ELIGIBLE_NOT_KILLED_PLUS_SURVIVED")
    for k in ("score", "mutation_score", "percent"):
        if k in rec:
            issues.append(f"SCORE_FIELD_NOT_ALLOWED:{k}")
    return issues


def adequacy_claim(campaign: dict, reviewed_survivors: dict[str, str] | None = None) -> dict:
    """AT-047: unit-test adequacy is SUPPORTED only if every survivor has a recorded human review disposition."""
    from .policy import _human

    reviewed = {k: v for k, v in (reviewed_survivors or {}).items() if _human(v)}
    open_ = [m["id"] for m in campaign["mutants"] if m["outcome"] == "SURVIVED" and m["id"] not in reviewed]
    killed = [m["id"] for m in campaign["mutants"] if m["outcome"] == "KILLED"]
    return {"claim": "UNIT_TESTS_DETECT_BEHAVIOURAL_FAULTS", "status": "UNSUPPORTED" if open_ else "SUPPORTED",
            "survivors_open": open_, "killed_provenance": killed,
            "note": "mutation score is a Forge-C project measure; no ISO 26262 threshold exists for it"}
