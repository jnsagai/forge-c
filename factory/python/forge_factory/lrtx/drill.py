"""F011-T040 (F011-AT-033): v2-only shutdown, restart and rollback drill, with an interrupted semantic engine.

    python -m forge_factory.lrtx.drill --profile local-rtx-v2-omniverse2 --out <json> [--protect <path>]...

Run on the host of the v2 stack, outside its namespace, while no work order runs on it. Each step is recorded:
1. protected fingerprint: every existing-deployment checkout of the profile (HEAD, clean tree), every --protect path
   (sha256 of each file: archives, the original read-only snapshot), the targets of the profile's shared read-only
   references, and the listeners on the profile's forbidden ports (the v1 line and other services);
2. interrupted engine: a real request to the pinned SafeC engine is cancelled as soon as the engine process exists:
   the outcome is ERROR/CANCELLED, nothing is admissible and no sealed evidence is finalized; a fresh request then gets
   an engine result that the client revalidates without any issue, sealed evidence included (the engine is not left
   damaged; the drill request carries no register domain, so the engine's own verdict on it is not the point);
3. stop: only the v2 stack stops (status DOWN); the forbidden-port listeners are unchanged;
4. restart: the v2 stack starts and every service answers its health check;
5. rollback: with the stack stopped, the profile root is moved aside (the v2-owned writable state); the stack then
   refuses to start; the root is restored (always, also on error) and the stack started again. Re-selecting the profile
   is an explicit operator step; nothing is deleted;
6. the protected fingerprint after equals the one before; the drill writes no CRE decision and promotes nothing.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import threading
from pathlib import Path

from ..common import pretty_json, sha256_file, utc_now
from ..safec_bridge import client as CL
from ..safec_bridge import contracts as C
from . import profile as lp
from . import stack


def _tree(p: Path) -> dict:
    p = Path(p)
    if p.is_file():
        return {str(p): sha256_file(p)}
    return {str(f): sha256_file(f) for f in sorted(p.rglob("*")) if f.is_file() and not f.is_symlink()}


def _checkout(root: Path) -> dict:
    def git(*a: str) -> str:
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, timeout=60).stdout.strip()

    return {"head": git("rev-parse", "HEAD"), "dirty": git("status", "--porcelain", "--untracked-files=no")}


def listeners(ports: list[int]) -> list[int]:
    """The forbidden ports something listens on in the host network namespace."""
    out = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True, timeout=30).stdout
    found = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3].rsplit(":", 1)[-1].isdigit():
            found.add(int(parts[3].rsplit(":", 1)[-1]))
    return sorted(found & set(ports))


def fingerprint(prof: dict, protect: list[Path]) -> dict:
    dep = prof["deployment"]
    return {"checkouts": {r: _checkout(Path(r)) for r in prof["existing_deployment"]["roots"]},
            "protected": {str(p): _tree(p) for p in protect},
            "shared_readonly": {k: str(Path(v).resolve()) for k, v in dep["shared_readonly"].items()},
            "listeners": listeners(dep["forbidden_ports"])}


def pin_of(prof: dict) -> CL.EnginePin:
    e = prof["safec"]["engine"]
    return CL.EnginePin(Path(e["binary"]), e["binary_sha256"], e["source_commit_sha"], e["semantic_profile"])


def _request(pin: CL.EnginePin, rid: str) -> tuple[dict, bytes]:
    return C.build_request(request_id=rid, operation="validate_intents", engine=pin.expected(),
                           binding={"workorder_id": "WO-F011-T040-DRILL", "workorder_sha256": "1" * 64,
                                    "source_manifest_sha256": "2" * 64, "policy_sha256": "3" * 64},
                           intents=[{"intent_id": "DRILL", "source_fact_ids": ["F-X"], "register": "X", "field": "Y",
                                     "action": "set_field"}])


def interrupted_engine(pin: CL.EnginePin, work: Path) -> dict:
    cancel = threading.Event()
    cancel.set()  # observed by the client's watch loop right after the engine process starts
    req, raw = _request(pin, "REQ-T040-INTERRUPTED")
    cut = CL.invoke(pin, req, raw, work / "interrupted", cancel=cancel)
    finalized = (work / "interrupted/evidence/sealed/FINALIZED").exists()
    req2, raw2 = _request(pin, "REQ-T040-AFTER")
    after = CL.invoke(pin, req2, raw2, work / "after")
    ok = (cut.status == "ERROR" and "CANCELLED" in cut.issues and not cut.admissible and cut.result is None
          and not finalized and not cut.refused
          and after.result is not None and not after.refused and after.issues == [])
    return {"ok": ok, "interrupted": {"status": cut.status, "issues": cut.issues, "admissible": cut.admissible,
                                      "exit_code": cut.exit_code, "sealed_finalized": finalized},
            "after": {"status": after.status, "issues": after.issues[:8], "admissible": after.admissible,
                      "engine_findings": [f.get("check_id") for f in (after.result or {}).get("findings", [])][:4]}}


def _healthy(st: dict) -> bool:
    return st.get("status") == "UP" and bool(st.get("health")) and all(st["health"].values())


def rollback(s: dict) -> dict:
    """Move the v2 root aside with the stack stopped, show the stack refuses to start, restore it (always)."""
    root = Path(s["root"])
    aside = root.with_name(root.name + ".t040-rollback")
    if aside.exists():
        return {"ok": False, "issue": f"ROLLBACK_TARGET_EXISTS:{aside}"}
    root.rename(aside)
    try:
        moved = not root.exists() and aside.is_dir()
        try:
            stack.start(s)
            refused = None
        except (RuntimeError, OSError, lp.ProfileRefused) as exc:
            refused = f"{type(exc).__name__}: {exc}"[:200]
        if refused is None:  # it must not run without its root; stop whatever it started
            stack.stop(s)
    finally:
        leftovers: list[str] = []
        if root.exists():  # a start attempt created state under the missing root: kept aside, never deleted
            leftovers = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
            root.rename(root.with_name(root.name + ".t040-leftovers"))
        aside.rename(root)
    return {"ok": moved and refused is not None and not leftovers and root.is_dir() and not aside.exists(),
            "moved_aside": moved, "start_refused": refused, "restored": root.is_dir(), "leftovers": leftovers}


def drill(profile_id: str, protect: list[Path], work: Path) -> dict:
    s = stack.settings(profile_id)
    prof = s["profile"]
    rec: dict = {"schema": "forge-c/f011-t040-drill/1", "profile": profile_id, "profile_sha256": prof["_sha256"],
                 "root": str(s["root"]), "started_at": utc_now(), "steps": {}}
    steps = rec["steps"]
    before = fingerprint(prof, protect)
    steps["fingerprint_before"] = {"ok": True, "listeners": before["listeners"],
                                   "checkouts": before["checkouts"],
                                   "protected_files": sum(len(v) for v in before["protected"].values())}
    steps["interrupted_engine"] = interrupted_engine(pin_of(prof), work)
    up = stack.status(s)
    steps["running_before"] = {"ok": _healthy(up), "status": up.get("status")}
    stopped = stack.stop(s)
    down = stack.status(s)
    steps["stop"] = {"ok": down["status"] == "DOWN" and listeners(prof["deployment"]["forbidden_ports"]) ==
                     before["listeners"], "stopped": stopped["stopped"], "status": down["status"]}
    stack.start(s)
    again = stack.status(s)
    steps["restart"] = {"ok": _healthy(again), "health": again.get("health")}
    stack.stop(s)
    steps["rollback"] = rollback(s)
    stack.start(s)
    final = stack.status(s)
    steps["restart_after_rollback"] = {"ok": _healthy(final), "health": final.get("health")}
    after = fingerprint(prof, protect)
    diff = [k for k in before if before[k] != after[k]]
    steps["fingerprint_after"] = {"ok": not diff, "changed": diff}
    steps["no_promotion"] = {"ok": True, "note": "the drill writes no CRE decision, deployment or release"}
    rec["finished_at"] = utc_now()
    rec["status"] = "PASS" if all(v["ok"] for v in steps.values()) else "FAIL"
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--protect", action="append", default=[], type=Path)
    ap.add_argument("--work", type=Path, required=True, help="new directory for the engine drill (not inside the root)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    a.work.mkdir(parents=True, exist_ok=False)
    rec = drill(a.profile, a.protect, a.work)
    a.out.write_text(pretty_json(rec))
    print(json.dumps({"status": rec["status"], **{k: v["ok"] for k, v in rec["steps"].items()}}))
    return 0 if rec["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
