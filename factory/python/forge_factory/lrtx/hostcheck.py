"""LRTX-T025 (LRTX-FR-004/FR-003): the existing deployment is still usable after the local-profile work, and the
profile can be rolled back without touching it.

    python -m forge_factory.lrtx.hostcheck --snapshot <T003 backup>/snapshot.json [--out <json>]

Read-only. Compares the deployment with the T003 preservation snapshot:
- the checkouts the services run from (HEAD, clean tree);
- the non-secret configuration hashes;
- every preserved review archive, still present with the same hash (new archives are allowed and listed);
- no profile work order, archive or meter in the deployment's state;
- the deployment services answering on their own ports with the same model digests.

It also checks from inside the profile namespace that external network access is still refused, and builds the
rollback plan for the profile:
- stop the stack by recorded PID;
- remove the profile root, the run worktrees and the monitor source.

Every removal path is checked never to lie inside a deployment root. The plan is a dry run: nothing is deleted here.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from ..common import pretty_json, sha256_file, utc_now
from . import hostsnap
from . import profile as lp


def _inside(p: Path, root: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def checkouts(snap: dict) -> list[dict]:
    rows = []
    for c in snap.get("checkouts") or []:
        root = Path(c["path"])
        head = hostsnap._run("git", "rev-parse", "HEAD", cwd=root)
        st = hostsnap._run("git", "status", "--porcelain", "--untracked-files=no", cwd=root)
        moved = head != c["head"]
        anc = moved and subprocess.run(["git", "merge-base", "--is-ancestor", c["head"], head], cwd=root,
                                       capture_output=True).returncode == 0
        rows.append({"path": str(root), "head_at_t003": c["head"], "head_now": head, "clean": st == "",
                     "status": "UNCHANGED" if not moved else ("ADVANCED (owner merges; T003 head is an ancestor)"
                                                              if anc else "DIVERGED"),
                     "ok": st == "" and (not moved or anc)})
    return rows


def configs(snap: dict) -> list[dict]:
    rows = []
    for c in snap.get("config_files") or []:
        p = Path(c["path"])
        now = sha256_file(p) if p.is_file() else None
        rows.append({"path": c["path"], "unchanged": now == c["sha256"], "sha256_now": now})
    return rows


def archives(snap: dict) -> dict:
    src = Path((snap.get("archives") or {}).get("source", ""))
    rows = snap.get("archive_rows") or []
    missing, changed = [], []
    for r in rows:
        z = src / r["work_order"] / r["archive"]
        if not z.is_file():
            missing.append(r["work_order"])
        elif sha256_file(z) != r["original_sha256"]:
            changed.append(r["work_order"])
    known = {r["work_order"] for r in rows}
    new = sorted(d.name for d in src.glob("*") if d.is_dir() and d.name not in known and d.name != "staging")
    prof = [n for n in new if "lrtx" in n.lower()]
    return {"preserved": len(rows), "missing": missing, "changed": changed, "new_since_t003": new,
            "profile_archives_in_deployment": prof, "ok": bool(rows) and not missing and not changed and not prof}


def deployment_state(data_root: Path) -> dict:
    wos = sorted(p.name for p in (data_root / "state/workorders").glob("*lrtx*")) \
        if (data_root / "state/workorders").is_dir() else []
    return {"profile_work_orders_in_deployment_state": wos, "ok": not wos}


def services(snap: dict) -> dict:
    m = snap.get("models") or {}
    now = hostsnap.ollama_models(m.get("url", "http://127.0.0.1:11435"))
    want = {x["name"]: x["digest"] for x in m.get("models") or []}
    got = {x["name"]: x["digest"] for x in now.get("models") or []}
    fabro = os.environ.get("FORGE_DEPLOYMENT_FABRO_HEALTH", "http://127.0.0.1:32290/health")
    fh = hostsnap._get_json(fabro)
    return {"ollama": {"url": now.get("url"), "status": now["status"], "version": now.get("version"),
                       "digests_unchanged": all(got.get(k) == v for k, v in want.items())},
            "fabro": {"health_url": fabro, "status": "OK" if fh is not None else "UNREACHABLE"},
            "ok": now["status"] == "OK" and all(got.get(k) == v for k, v in want.items()) and fh is not None}


def namespace_network(stack_python: str, repo: Path) -> dict:
    """Run the profile's own network check inside the namespace (needs the stack up); DOWN is reported, not failed."""
    p = subprocess.run([stack_python, "-m", "forge_factory.lrtx.stack", "exec", "--", "python", "-c",
                        "import json; from forge_factory.lrtx import profile as p; "
                        "print(json.dumps(p.network_enforcement()))"],
                       cwd=repo, capture_output=True, text=True, timeout=120,
                       env={**os.environ, "PYTHONPATH": str(repo / "factory/python")})
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {"status": "STACK_DOWN_OR_UNREADABLE", "detail": (p.stderr or p.stdout)[-300:], "ok": None}
    return {**r, "ok": r.get("status") == "DENIED_VERIFIED"}


def rollback_plan(prof: dict, snap: dict, worktrees: list[Path], monitor_config: Path | None) -> dict:
    dep = [Path(snap["data_root"]), *(Path(c["path"]) for c in snap.get("checkouts") or [])]
    root = Path(os.environ.get(prof["deployment"]["root_env"]) or prof["deployment"]["default_root"])
    remove = [root, *worktrees]
    # the worktrees live under <data_root>/repos by convention: a removal is a conflict only if it would delete or
    # contain a deployment root other than that repos folder (checkouts, state, archives, the data root itself)
    keep = [Path(snap["data_root"]) / n for n in ("state", "archives", "fabro", "fabro-cloud", "venv", "toolchains",
                                                  "inputs", "standards", "ollama-models")]
    keep += [Path(c["path"]) for c in snap.get("checkouts") or []] + [Path(snap["data_root"])]
    conflicts = [f"{r} vs {d}" for r in remove for d in keep if _inside(d, r) or (d != Path(snap["data_root"])
                                                                                    and _inside(r, d))]
    steps = ["python -m forge_factory.lrtx.stack stop   # recorded PIDs only, incl. the API relay",
             *[f"git worktree remove {w}" for w in worktrees], f"rm -rf {root}   # profile root (after review)"]
    if monitor_config:
        steps.append(f"remove source 'forge-c-lrtx' from {monitor_config}; restart fabro-monitor.service")
    return {"dry_run": True, "remove": [str(r) for r in remove], "deployment_roots": [str(d) for d in dep],
            "conflicts": conflicts, "steps": steps, "ok": not conflicts}


PROFILE_FILE = "config/factory/profiles/local-rtx-v1.yaml"


def profile_worktrees(repo: Path, snap: dict) -> list[Path]:
    """Run worktrees of the profile: `forge-c-run-*` checkouts next to the repository that contain the profile file and
    whose HEAD is not in the history of a deployment checkout (after a merge, a main-line run is not the profile's).
    2026-10-21: selecting by the name `forge-c-run-lrtx*` missed the t016/t021/t023 measurement worktrees."""
    deployed = [c["head"] for c in snap.get("checkouts") or []] + [
        hostsnap._run("git", "rev-parse", "HEAD", cwd=Path(c["path"])) for c in snap.get("checkouts") or []]
    out = []
    for w in sorted(Path(repo).parent.glob("forge-c-run-*")):
        if not (w / PROFILE_FILE).is_file():
            continue
        head = hostsnap._run("git", "rev-parse", "HEAD", cwd=w)
        if not any(d and subprocess.run(["git", "merge-base", "--is-ancestor", head, d], cwd=w,
                                        capture_output=True).returncode == 0 for d in set(deployed)):
            out.append(w)
    return out


def check(snapshot: Path, repo: Path, stack_python: str | None = None) -> dict:
    snap = json.loads(snapshot.read_text())
    prof = lp.load(os.environ.get("FORGE_LRTX_PROFILE", "local-rtx-v1"))
    data_root = Path(snap["data_root"])
    wts = profile_worktrees(repo, snap)
    mon = Path.home() / "fabro_dashboard/config.local.json"
    rec = {"schema": "forge-c/lrtx-hostcheck/1", "checked_at": utc_now(), "snapshot": str(snapshot),
           "snapshot_sha256": sha256_file(snapshot), "checkouts": checkouts(snap), "config_files": configs(snap),
           "archives": archives(snap), "deployment_state": deployment_state(data_root), "services": services(snap),
           "namespace_network": namespace_network(stack_python, repo) if stack_python else {"status": "NOT_RUN",
                                                                                            "ok": None},
           "rollback": rollback_plan(prof, snap, wts, mon if mon.is_file() else None)}
    parts = [all(c["ok"] for c in rec["checkouts"]), all(c["unchanged"] for c in rec["config_files"]),
             rec["archives"]["ok"], rec["deployment_state"]["ok"], rec["services"]["ok"], rec["rollback"]["ok"],
             rec["namespace_network"]["ok"] is not False]
    # a network check that could not run leaves the record INCOMPLETE, never PASS
    rec["status"] = "FAIL" if not all(parts) else ("PASS" if rec["namespace_network"]["ok"] else "INCOMPLETE")
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    ap.add_argument("--stack-python", default=None, help="python that runs lrtx.stack (namespace network check)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    rec = check(a.snapshot, a.repo, a.stack_python)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(pretty_json(rec))
    print(json.dumps({"status": rec["status"], "checkouts": [c["status"] for c in rec["checkouts"]],
                      "archives": {k: rec["archives"][k] for k in ("preserved", "missing", "changed")},
                      "services_ok": rec["services"]["ok"], "network": rec["namespace_network"].get("status"),
                      "rollback_conflicts": rec["rollback"]["conflicts"]}))
    return 0 if rec["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
