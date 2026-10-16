"""Defect register for cross-phase loopbacks (ADR-0008).

A downstream author or inspector that finds a defect it is not allowed to fix (code, architecture, requirement)
reports it here via forge-evidence-mcp.report_defect. Gates route the run back to the phase that owns the defect
(bounded by the run's upstream-loop budget) and later verify it with the SAME, unchanged tests. Agents can only
report, or (target-phase author) reject with a reason; FIXED/VERIFIED are set by deterministic gates only.
Approved inputs and factory assets are never edited by agents: INPUT/FACTORY defects are escalated to a human.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from ..common import pretty_json, sha256_file, utc_now
from .engine import PHASE_PATHS, PHASES

DIR = ".forge-run/defects"
LOOPS = ".forge-run/gates/upstream-loops.jsonl"
SNAPSHOTS = ".forge-run/test-snapshots"  # content-addressed copies of every test file a test tool ran (tools only)
GATE_REPORTER = "route-gate"  # reported_by of a defect filed by the deterministic safety net (ADR-0008 L11)
KINDS = ("CODE", "ARCHITECTURE", "REQUIREMENT", "TEST", "INPUT", "FACTORY")
KIND_TARGET = {"CODE": "SWE.3", "ARCHITECTURE": "SWE.2", "REQUIREMENT": "SWE.1"}  # fixed owner per kind
ESCALATED_KINDS = ("INPUT", "FACTORY")
UPSTREAM_LOOP_BUDGET = 2  # ADR-0008: one loop re-runs every phase from the target onward
MAX_OPEN = 6
OPEN_STATES = ("OPEN", "IN_FIX")
TEST_TOOLS = ("run_unit", "run_integration", "run_renode", "run_robot")
SWR = re.compile(r"\*\*(SWR-[A-Z0-9_.-]+)\*\*")


class DefectError(ValueError):
    pass


def _dir(ws: Path) -> Path:
    return ws / DIR


def all_defects(ws: Path) -> list[dict]:
    d = _dir(ws)
    return [json.loads(p.read_text()) for p in sorted(d.glob("DEF-*.json"))] if d.is_dir() else []


def _save(ws: Path, rec: dict) -> None:
    _dir(ws).mkdir(parents=True, exist_ok=True)
    (_dir(ws) / f"{rec['id']}.json").write_text(pretty_json(rec))


def _event(rec: dict, status: str, **extra) -> None:
    rec["status"] = status
    rec.setdefault("history", []).append({"ts": utc_now(), "status": status, **extra})


def _requirements(ws: Path) -> set[str]:
    p = ws / "workproducts/SWE.1/software_requirements.md"
    return set(SWR.findall(p.read_text(errors="replace"))) if p.is_file() else set()


def _tool_results(ws: Path) -> list[dict]:
    p = ws / "evidence/tool-results.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []


UNDECLARED_CALL = re.compile(r"(?:call to undeclared function|implicit declaration of function) '(\w+)'")


def _undeclared_api_calls(ws: Path, run: dict) -> list[str]:
    """Functions a failing test run could not build against because no product header declares them."""
    names = sorted({m for i in run["result"].get("issues", []) for m in UNDECLARED_CALL.findall(i)})
    heads = " ".join(p.read_text(errors="replace") for d in ("software/hal", "software/ll", "software/include")
                     for p in sorted((ws / d).rglob("*.h")) if (ws / d).is_dir())
    return [n for n in names if not re.search(rf"\b{re.escape(n)}\s*\(", heads)]


def _in_paths(rel: str, phase: str) -> bool:
    return any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in PHASE_PATHS[phase])


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("*", "")).strip().lower()


def _requirement_texts(ws: Path) -> dict[str, str]:
    from .ears import extract

    p = ws / "workproducts/SWE.1/software_requirements.md"
    return {r.req_id: r.text for r in extract(p.read_text(errors="replace"))} if p.is_file() else {}


def report(ws: Path, *, detected_phase: str, reported_by: str, kind: str, summary: str,
           requirement_ids: list[str], test_files: list[str], evidence_refs: list[str],
           requirement_quote: str = "") -> dict:
    """Validate deterministically and record a defect. Raises DefectError with a stable code on refusal."""
    if kind not in KINDS:
        raise DefectError(f"UNKNOWN_KIND:{kind}")
    if detected_phase not in PHASES:
        raise DefectError(f"UNKNOWN_PHASE:{detected_phase}")
    target = detected_phase if kind == "TEST" else KIND_TARGET.get(kind)
    if target is not None and PHASES.index(target) > PHASES.index(detected_phase):
        raise DefectError(f"TARGET_NOT_UPSTREAM:{target}>{detected_phase}")
    if target is not None and kind != "TEST" and target == detected_phase:
        raise DefectError(f"SAME_PHASE_USE_REWORK:{target}")
    if not summary.strip():
        raise DefectError("NO_SUMMARY")
    known = _requirements(ws)
    unknown = [r for r in requirement_ids if r not in known]
    if unknown:
        raise DefectError(f"UNKNOWN_REQUIREMENT:{','.join(unknown[:3])}")
    if kind in ("CODE", "ARCHITECTURE", "REQUIREMENT", "TEST") and not requirement_ids:
        raise DefectError("NO_REQUIREMENT_ID")
    if kind in ("CODE", "TEST", "ARCHITECTURE"):
        # r62: a CODE defect asked for behaviour CONTRARY to SWR-013 ("hardware leaves the bit set") and the fixer
        # complied. CODE = the code violates a requirement AS WRITTEN; TEST = the corrected test checks a clause AS
        # WRITTEN. The clause must be quoted verbatim; disagreeing with the requirement is a REQUIREMENT defect.
        # r70: an ARCHITECTURE defect demanded PLL disable APIs for SWR-008 (a peripheral clock disable) with the
        # invented "quote" 'SWR-008: MSI disable.'; it cost an upstream loop and a cascade. ARCHITECTURE = the API
        # cannot express a clause AS WRITTEN: quoted verbatim as well.
        texts = _requirement_texts(ws)
        q = _norm(requirement_quote)
        if len(q) < 20 or not any(q in _norm(texts.get(r, "")) for r in requirement_ids):
            raise DefectError("REQUIREMENT_QUOTE_REQUIRED:quote >=20 chars verbatim from a cited requirement; if "
                              "the requirement itself is wrong, report kind REQUIREMENT")
    hashes = {}
    for t in test_files:
        p = (ws / t).resolve()
        if not p.is_file() or ws.resolve() not in p.parents:
            raise DefectError(f"TEST_FILE_NOT_FOUND:{t[:60]}")
        hashes[t] = sha256_file(p)
    if kind == "CODE":
        # no blame-shifting without evidence: a failing test run of the detecting phase, or a source location
        failing = [r for r in _tool_results(ws) if r.get("phase") == detected_phase and r.get("op") in TEST_TOOLS
                   and r["result"]["status"] == "FAIL"]
        locs = [e for e in evidence_refs if re.match(r"^[\w./-]+:\d+$", e) and _in_paths(e.rsplit(":", 1)[0], "SWE.3")
                and (ws / e.rsplit(":", 1)[0]).is_file()]
        if not (failing and test_files) and not locs:
            raise DefectError("CODE_DEFECT_NEEDS_EVIDENCE:failing test run of this phase (with test_files) or a "
                              "SWE.3 source location file:line")
        undeclared = _undeclared_api_calls(ws, failing[-1]) if failing else []
        if undeclared and not locs:
            # r70/r73: SWE.4 tests called HAL_RCC_PLLx_Disable, which the API never declared, and blamed the code
            # (r73: triage accepted it and spent the last upstream loop). Code cannot be wrong about an API the
            # architecture does not have: the test must call declared functions, or the API gap is ARCHITECTURE.
            raise DefectError(f"CODE_DEFECT_ON_UNDECLARED_API:{','.join(undeclared[:4])}: your test does not build "
                              "because it calls functions the API headers do not declare. Call only declared "
                              "functions; if a requirement clause needs a missing function, report kind "
                              "ARCHITECTURE quoting that clause")
    if kind == "TEST" and not test_files:
        raise DefectError("TEST_DEFECT_NEEDS_TEST_FILE")
    existing = all_defects(ws)
    same = next((d for d in existing if d["status"] == "OPEN" and d["kind"] == kind
                 and d["detected_phase"] == detected_phase and sorted(d["requirement_ids"]) == sorted(requirement_ids)),
                None)
    if same is not None and kind not in ("TEST", *ESCALATED_KINDS):
        return same  # r66: the same defect reported again while open is the same defect (no duplicate loop)
    if sum(1 for d in existing if d["status"] in OPEN_STATES) >= MAX_OPEN:
        raise DefectError(f"TOO_MANY_OPEN_DEFECTS:{MAX_OPEN}")
    rec = {"schema": "forge-c/defect/0.5", "id": f"DEF-{len(existing) + 1:03d}", "kind": kind,
           "detected_phase": detected_phase, "reported_by": reported_by, "target_phase": target,
           "requirement_ids": requirement_ids, "test_files": hashes, "evidence_refs": evidence_refs[:10],
           "summary": summary[:400], "requirement_quote": requirement_quote[:300]}
    if kind == "TEST":
        rec["code_sha"] = code_hash(ws)  # the product code the correction was declared against (ADR-0008 L14)
    if kind in ESCALATED_KINDS:
        _event(rec, "ESCALATED", note="approved inputs / factory assets are changed by a human only")
    elif kind == "TEST":
        _event(rec, "DECLARED", note="test corrected in its own phase; reviewed by the inspector and the human")
        for d in existing:  # ADR-0008 L15: the reporter retracts its own unverified blame on the same test file
            if d["detected_phase"] == detected_phase and d["kind"] in KIND_TARGET and \
                    d["status"] in ("OPEN", "IN_FIX", "FIXED") and set(d["test_files"]) & set(hashes) and \
                    set(d["requirement_ids"]) & set(requirement_ids):
                _event(d, "WITHDRAWN", by=rec["id"], note="the reporter declared its test wrong (human review)")
                _save(ws, d)
    else:
        _event(rec, "OPEN")
    _save(ws, rec)
    return rec


def reject(ws: Path, defect_id: str, role: str, reason: str) -> dict:
    """The target phase's author may reject a defect (the downstream test is wrong) - with a recorded reason."""
    rec = next((d for d in all_defects(ws) if d["id"] == defect_id), None)
    if rec is None:
        raise DefectError(f"UNKNOWN_DEFECT:{defect_id}")
    if rec["status"] not in OPEN_STATES:
        raise DefectError(f"NOT_OPEN:{rec['status']}")
    if role != f"swe{rec['target_phase'][-1]}-author":
        raise DefectError(f"NOT_TARGET_AUTHOR:{role}")
    if len(reason.strip()) < 10:
        raise DefectError("REASON_REQUIRED")
    _event(rec, "REJECTED", by=role, reason=reason[:400])
    _save(ws, rec)
    return rec


def open_from(ws: Path, phase: str) -> list[dict]:
    """OPEN upstream defects reported by `phase` (route leaves the phase instead of burning rework cycles)."""
    return [d for d in all_defects(ws) if d["detected_phase"] == phase and d["status"] == "OPEN"
            and d["target_phase"] and d["target_phase"] != phase]


def loops_used(ws: Path) -> int:
    p = ws / LOOPS
    return len(p.read_text().splitlines()) if p.is_file() else 0


def take_upstream(ws: Path, target: str) -> list[dict]:
    """Chain node `upstream_<target>`: claim every OPEN defect owned by `target` if loop budget remains."""
    todo = [d for d in all_defects(ws) if d["status"] == "OPEN" and d["target_phase"] == target]
    if not todo or loops_used(ws) >= UPSTREAM_LOOP_BUDGET:
        return []
    for d in todo:
        _event(d, "IN_FIX", loop=loops_used(ws) + 1)
        _save(ws, d)
    p = ws / LOOPS
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"ts": utc_now(), "target": target, "defects": [d["id"] for d in todo]}) + "\n")
    return todo


def mark_fixed(ws: Path, phase: str, baseline_id: str) -> list[str]:
    """Inspection gate PASS of the target phase: its IN_FIX defects are FIXED (verification happens downstream)."""
    out = []
    for d in all_defects(ws):
        if d["status"] == "IN_FIX" and d["target_phase"] == phase:
            _event(d, "FIXED", baseline_id=baseline_id)
            _save(ws, d)
            out.append(d["id"])
    return out


def verify_on_freeze(ws: Path, phase: str) -> list[str]:
    """Author gate of the detecting phase: a fixed defect is VERIFIED only with byte-identical cited tests and a
    test-tool PASS recorded after the fix. Returns blocking issues (cited test changed)."""
    issues = []
    results = _tool_results(ws)
    for d in all_defects(ws):
        if d["detected_phase"] != phase or d["status"] not in ("FIXED", "IN_FIX"):
            continue
        changed = [t for t, h in d["test_files"].items()
                   if not (ws / t).is_file() or sha256_file(ws / t) != h]
        if changed:
            issues.append(f"DEFECT_TEST_CHANGED:{d['id']}:{changed[0][:60]}")
            continue
        if d["status"] != "FIXED":
            continue
        fixed_at = d["history"][-1]["ts"]
        latest: dict[str, dict] = {}  # newest result per test tool of this phase, run after the fix
        for r in results:
            if r.get("phase") == phase and r.get("op") in TEST_TOOLS and r.get("ts_utc", "") > fixed_at:
                latest[r["op"]] = r
        if latest and all(r["result"]["status"] == "PASS" for r in latest.values()):
            _event(d, "VERIFIED", tools=sorted(latest))
            _save(ws, d)
    return issues


def gaps(ws: Path) -> list[str]:
    """Release finalizer: every defect not VERIFIED/REJECTED/DECLARED/WITHDRAWN is a gap."""
    out = []
    for d in all_defects(ws):
        if d["status"] == "ESCALATED":
            out.append(f"escalated_defect:{d['id']}:{d['kind']}")
        elif d["status"] not in ("VERIFIED", "REJECTED", "DECLARED", "WITHDRAWN"):
            out.append(f"open_defect:{d['id']}:{d['kind']}:{d['status']}"
                       + (":gate-filed" if d.get("reported_by") == GATE_REPORTER else ""))
    return out


# ---- anti-bending (ADR-0008 L4) ------------------------------------------------------------------------------
CODE_DIRS = ("software/hal", "software/ll", "software/src", "software/include")


def code_hash(ws: Path) -> str:
    """Hash of the product code (SWE.3 sources) at the time of a test run."""
    import hashlib

    h = hashlib.sha256()
    for d in CODE_DIRS:
        for p in sorted((ws / d).rglob("*")) if (ws / d).is_dir() else []:
            if p.is_file():
                h.update(p.relative_to(ws).as_posix().encode() + b"\0" + sha256_file(p).encode())
    return h.hexdigest()


def integrity(ws: Path, test_files: list[Path], assertion_failed: list[Path]) -> dict:
    """Recorded with every test-tool result: which test files had RUNTIME assertion failures (not build errors),
    the hash of every test file and of the product code, so a later 'fixed' test can be checked deterministically."""
    rel = {p.resolve().relative_to(ws.resolve()).as_posix(): sha256_file(p) for p in test_files if p.is_file()}
    snap = ws / SNAPSHOTS  # the exact files of every run, so a failing test can be cited and restored later (L11)
    snap.mkdir(parents=True, exist_ok=True)
    for f, h in rel.items():
        if not (snap / h).is_file():
            shutil.copyfile(ws / f, snap / h)
    return {"code_sha": code_hash(ws), "files": rel,
            "assert_failed": sorted(p.resolve().relative_to(ws.resolve()).as_posix() for p in assertion_failed
                                    if p.is_file())}


INTEGRITY_LOG = "evidence/test-integrity.jsonl"  # written by the test tools only (no agent write scope)


def record_integrity(ws: Path, phase: str | None, op: str, status: str, data: dict) -> None:
    p = ws / INTEGRITY_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts_utc": utc_now(), "phase": phase, "op": op, "status": status, **data},
                           sort_keys=True) + "\n")


def _integrity_runs(ws: Path) -> list[dict]:
    p = ws / INTEGRITY_LOG
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []


def _declared_code(d: dict, runs: list[dict]) -> str:
    """Product code a TEST declaration was made against: recorded since L14, else the newest test run before it."""
    if d.get("code_sha"):
        return d["code_sha"]
    before = [r for r in runs if r.get("ts_utc", "") <= d["history"][0]["ts"]]
    return before[-1]["code_sha"] if before else ""


def _covers(d: dict, f: str, failed: dict, runs: list[dict]) -> bool:
    """ADR-0008 L14 (owner decision 2026-10-16, r72): a TEST declaration of file f covers its correction after a
    failure recorded before the declaration AND later corrections of f while the product code is the one the
    declaration was made against (r72: declared at 21:22, edited again after six later failures, all on unchanged
    code; the 18/18 suite was rejected). An upstream fix changes the code: a new declaration is needed. The
    observability check, the inspector (every declared test file vs. its requirement) and SUP.9 guard the content."""
    if f not in d["test_files"]:
        return False
    return d["history"][0]["ts"] >= failed.get("ts_utc", "") or _declared_code(d, runs) == failed["code_sha"]


def _bent(ws: Path, phase: str) -> list[tuple[str, dict]]:
    """(test file, failing run) for every test changed to pass against unchanged code and not declared."""
    allruns = [r for r in _integrity_runs(ws) if r.get("op") in TEST_TOOLS]
    runs = [r for r in allruns if r.get("phase") == phase]
    declared = [d for d in all_defects(ws) if d["kind"] == "TEST" and d["detected_phase"] == phase]
    out: list[tuple[str, dict]] = []
    for op in sorted({r["op"] for r in runs}):
        seq = [r for r in runs if r["op"] == op]
        final = seq[-1]
        fin = final
        if final["status"] != "PASS":
            continue
        for r in seq[:-1]:
            it = r
            for f in it["assert_failed"]:
                if f not in fin["files"] or fin["files"][f] == it["files"].get(f) or fin["code_sha"] != it["code_sha"]:
                    continue  # unchanged test, removed test, or the code changed (upstream fix): not bending
                ok = any(_covers(d, f, r, allruns) for d in declared)
                if not ok and f not in [x for x, _ in out]:
                    out.append((f, r))
    return out


def bent_tests(ws: Path, phase: str) -> list[str]:
    """A test file that failed at runtime and passes in the newest run of the same tool after being EDITED, while
    the product code is unchanged, is a test changed to fit the code. It needs a declared TEST defect (reason,
    reviewed by inspector and human); otherwise the phase is not frozen (r60: SWR-014 scenario rewritten)."""
    return [f"TEST_CHANGED_AFTER_FAIL:{f}" for f, _ in _bent(ws, phase)]


def declare_post_fix_adaptations(ws: Path, phase: str) -> list[dict]:
    """ADR-0008 L13 (owner decision 2026-10-15, r71): an upstream fix changed behaviour, so a test that PASSED with
    the same content on the pre-fix code fails afterwards and the author adapts it without declaring it. The gate
    declares it (kind TEST, reported_by route-gate) citing the fix defect's requirement clause, so the phase can
    proceed; the inspector must check the changed test against the requirement and the package lists it for human
    review. A test that never passed before the fix is still plain bending (blocked)."""
    runs = [r for r in _integrity_runs(ws) if r.get("op") in TEST_TOOLS]
    fixes = [d for d in all_defects(ws) if d["kind"] in KIND_TARGET and d["status"] in ("FIXED", "VERIFIED")]
    out = []
    for f, failed in _bent(ws, phase):
        before = [r for r in runs if r["op"] == failed["op"] and r["status"] == "PASS"
                  and r.get("ts_utc", "") < failed.get("ts_utc", "") and r["files"].get(f) == failed["files"].get(f)
                  and r["code_sha"] != failed["code_sha"]]
        if not before:
            continue
        passed = before[-1]
        fix = next((d for d in reversed(fixes) if any(
            h["status"] == "FIXED" and passed["ts_utc"] < h["ts"] <= failed["ts_utc"] for h in d["history"])), None)
        if fix is None:
            continue
        rec = report(ws, detected_phase=phase, reported_by=GATE_REPORTER, kind="TEST",
                     summary=f"Gate-declared: {f} passed on the pre-fix code and failed after the {fix['id']} fix "
                             f"({fix['kind']}, {', '.join(fix['requirement_ids'])}); the author adapted it without "
                             "declaring it. Inspector: check the changed test against the requirement; human review.",
                     requirement_ids=fix["requirement_ids"], test_files=[f],
                     evidence_refs=[f"{INTEGRITY_LOG}@{passed['ts_utc']}", f"{INTEGRITY_LOG}@{failed['ts_utc']}"],
                     requirement_quote=fix.get("requirement_quote", ""))
        rec["gate_declared"] = {"fix_defect": fix["id"], "passed_before_fix": passed["ts_utc"],
                                "failed_after_fix": failed["ts_utc"]}
        _save(ws, rec)
        out.append(rec)
    return out


def review_items(ws: Path) -> list[str]:
    """Defects the gate filed or declared on its own, and defects their reporter withdrew: listed for the human
    reviewer (not gaps by themselves)."""
    return [f"{d['id']} {d['kind']} {d['status']} ({d['detected_phase']}): {d['summary'][:200]}"
            for d in all_defects(ws) if d.get("reported_by") == GATE_REPORTER or d["status"] == "WITHDRAWN"]


# ---- safety net (ADR-0008 L11, owner decision 2026-10-15) -----------------------------------------------------
def auto_code_defect(ws: Path, phase: str, since: str) -> dict | None:
    """When a test phase is about to BLOCK without having reported anything, file the CODE defect its own recorded
    evidence already proves (r67-r69: the SWE.6 author edited a correct failing check instead of reporting it).

    Evidence = the newest test run of this phase in this run where the product code is byte-identical to now, every
    scenario built, and EVERY failed check calls the driver and tests a token the tagged requirement names (e.g.
    'rc == HAL_ERROR with rc = HAL_RCC_HSI_Enable(0U)' for 'shall return HAL_ERROR'), and that requirement was not
    reported unobserved. The run's test files are restored from the tool snapshots (it reproduces exactly: same code,
    same tests) and cited, so the fix is verified with the very test that failed. The SWE.3 author still judges and
    may reject_defect with a reason. Nothing is filed when the same tests were already the subject of a defect."""
    cur = code_hash(ws)
    texts = _requirement_texts(ws)
    runs = [r for r in _integrity_runs(ws) if r.get("phase") == phase and r.get("status") == "FAIL"
            and r.get("ts_utc", "") >= since and r.get("failed_checks")]
    for r in reversed(runs):
        fc = r["failed_checks"]
        reqs = sorted({q for c in fc for q in c["requirements"]})
        if r["code_sha"] != cur or r.get("build_failed") or not reqs or set(reqs) & set(r.get("unobserved", [])) \
                or any(q not in texts for q in reqs) \
                or not all(c["requirements"] and c["observes"] and c["driver_call"] for c in fc):
            continue
        scns = {c["scenario"] for c in fc}
        cited = {f: h for f, h in r["files"].items() if f.endswith(".robot") or f.rsplit("/", 1)[-1] in scns}
        if any(sorted(d["requirement_ids"]) == reqs and d["test_files"] == cited for d in all_defects(ws)):
            return None  # these exact tests were already reported, fixed, verified or rejected
        if not all((ws / SNAPSHOTS / h).is_file() for h in r["files"].values()):
            continue
        restored = []
        for f, h in sorted(r["files"].items()):
            p = ws / f
            if not p.is_file() or sha256_file(p) != h:
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ws / SNAPSHOTS / h, p)
                restored.append(f)
        exprs = [f"{c['scenario']}#{c['check']}: {c['expr']}" for c in fc]
        rec = report(ws, detected_phase=phase, reported_by=GATE_REPORTER, kind="CODE",
                     summary=f"Filed by the route gate (the {phase} author did not report it): {'; '.join(exprs)} "
                             f"fails against the unchanged driver code; the check calls the driver and tests what "
                             f"{', '.join(reqs)} names. Fix the code, or reject_defect with the reason the test is "
                             "wrong.",
                     requirement_ids=reqs, test_files=sorted(cited),
                     evidence_refs=[f"CHECK_EXPR:{e}"[:160] for e in exprs][:8] + [f"{INTEGRITY_LOG}@{r['ts_utc']}"],
                     requirement_quote=texts[reqs[0]])
        rec["auto_filed"] = {"integrity_ts": r["ts_utc"], "restored_test_files": restored,
                             "failed_checks": fc[:10]}
        _save(ws, rec)
        return rec
    return None


# ---- triage before the upstream fix (ADR-0008 L12, owner decision 2026-10-15) -----------------------------------
def last_loop(ws: Path) -> dict | None:
    p = ws / LOOPS
    lines = [x for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []
    return json.loads(lines[-1]) if lines else None


def rejected_loop_return(ws: Path) -> str | None:
    """r70: SWE.2 rejected a wrong ARCHITECTURE defect but its author re-ran its normal steps, re-froze and cascaded
    into SWE.3. When the owner's triage rejected EVERY defect of the latest loop, the run returns to the phase that
    reported them (the most downstream detecting phase); nothing upstream is re-frozen. Otherwise None (fix path)."""
    loop = last_loop(ws)
    if loop is None:
        return None
    recs = [d for d in all_defects(ws) if d["id"] in loop["defects"]]
    if not recs or any(d["status"] != "REJECTED" for d in recs):
        return None
    return max((d["detected_phase"] for d in recs), key=PHASES.index)
