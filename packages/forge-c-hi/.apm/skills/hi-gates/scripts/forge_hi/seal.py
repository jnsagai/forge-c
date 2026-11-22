"""Sealed offline review package (`hi seal`): READY_FOR_OFFLINE_REVIEW or BLOCKED with a gap list.

The manifest and hashing approach is adapted from Forge-C factory/release-manager/scripts/build_review_package.py
(Apache-2.0). Sealing never manufactures evidence and never upgrades a result:

- the deterministic gates (validate, quality, trace, doc-sources, independence) are re-run now, so the package
  reflects the files as they are;
- the scope gate and tool gates are taken as recorded; a required gate that never ran is a gap;
- every stage in scope must have been accepted by the conductor, and unchanged since;
- open blocking findings, blocking open points and suspect links are gaps.

A package is produced in every case. READY requires zero gaps.
"""
from __future__ import annotations

import gzip
import io
import platform
import shutil
import tarfile
from pathlib import Path

from . import __version__, gate_result, gates, report, trace
from .config import effective_rigor, load_profile, load_project, stages
from .io import read_json, sha256_file, write_json, write_text
from .provenance import new_run_id, utc_now

READY, BLOCKED = "READY_FOR_OFFLINE_REVIEW", "BLOCKED"
FIXED_MTIME = 315532800  # 1980-01-01T00:00:00Z
PKG_ROOT = Path("hi") / "packages"
TOP_FILES = ("manifest.json", "review.tar.gz", "review.tar.gz.sha256")


def _gap(code: str, source: str, message: str) -> dict:
    return {"code": code, "source": source, "message": message[:300]}


def wp_sha(root: Path, stage: str) -> str | None:
    p = Path(root) / stages()[stage]["outputs"][0]
    return sha256_file(p) if p.is_file() else None


def collect_gaps(root: Path, project: dict) -> tuple[list[dict], dict]:
    root = Path(root)
    gaps: list[dict] = []
    verdicts: dict[str, dict] = {}
    accepted = gates.accepted_stages(root)
    for s in trace.checked_stages(project, None):
        if wp_sha(root, s) is None:
            gaps.append(_gap("STAGE-MISSING", s, f"{stages()[s]['outputs'][0]} does not exist"))
            continue
        st = accepted.get(s, {})
        if st.get("state") != "accepted":
            gaps.append(_gap("NOT-ACCEPTED", s, f"stage {s} was not accepted by the conductor "
                             f"(state: {st.get('state', 'never run')}; {st.get('reason', '')})"))
        elif st.get("wp_sha256") and st["wp_sha256"] != wp_sha(root, s):
            gaps.append(_gap("CHANGED-AFTER-INSPECTION", s, "the workproduct changed after the stage was accepted"))
        verdicts[s] = {}
        for g in gates.required_gates(project, s):
            if g == "validate":
                res = gates.validate_stage(root, s)
            elif g == "quality":
                from . import quality
                res = quality.run(root, s)
            elif g == "trace":
                res = trace.run(root, s)
            elif g == "doc-sources":
                res = gates.doc_sources(root, s)
            elif g == "independence":
                res = gates.independence(root, s)
            else:
                p = root / "hi" / s / "gates" / f"{g}.json"
                res = read_json(p) if p.is_file() else None
            if res is None:
                verdicts[s][g] = "MISSING"
                gaps.append(_gap("GATE-MISSING", f"{s}/{g}", f"required gate {g} has no recorded result"))
                continue
            verdicts[s][g] = res["verdict"]
            if res["verdict"] == "NOT_RUN":
                gaps.append(_gap("GATE-NOT-RUN", f"{s}/{g}", res.get("not_run_reason", "not run")))
            elif res["verdict"] == "FAIL":
                codes = sorted({i["code"] for i in res["issues"]})
                if g == "trace" and "TR-SUSPECT" in codes:
                    gaps.append(_gap("TRACE-SUSPECT", f"{s}/trace", "suspect links: " + ", ".join(
                        i["message"] for i in res["issues"] if i["code"] == "TR-SUSPECT")[:250]))
                    codes.remove("TR-SUSPECT")
                if g == "independence":
                    gaps.append(_gap("INDEPENDENCE", f"{s}/independence", "; ".join(i["message"] for i in res["issues"])))
                elif codes:
                    gaps.append(_gap("GATE-FAIL", f"{s}/{g}", f"{len(res['issues'])} issue(s): {', '.join(codes[:8])}"))
        for f in gates.findings(root, s):
            if f.get("status") in ("open", "carried") and f.get("severity") in ("blocking", "major"):
                # guideline DoD: no open blocking or correctable (major) finding without a recorded disposition
                code = "FINDING-BLOCKING" if f["severity"] == "blocking" else "FINDING-MAJOR"
                gaps.append(_gap(code, f"{s}/{f['id']}", f"{f['target_id']} {f['checklist_item']}: "
                                 f"{f.get('description', '')}"))
        for o in read_json(root / stages()[s]["outputs"][0]).get("open_points", []):
            if isinstance(o, dict) and o.get("blocks"):
                gaps.append(_gap("OPEN-POINT-BLOCKING", f"{s}/{o.get('id')}", str(o.get("text", ""))))
    return gaps, verdicts


def provenance_summary(root: Path, project: dict) -> list[dict]:
    out = []
    for s in trace.checked_stages(project, None):
        p = Path(root) / stages()[s]["outputs"][0]
        records = [read_json(p).get("provenance") or {}] if p.is_file() else []
        records += [f["raised_by"] for f in gates.findings(root, s)[:1] if isinstance(f.get("raised_by"), dict)]
        for prov in records:
            rec = {"stage": s, "model": prov.get("model"), "model_family": prov.get("model_family")}
            rec.update({k: str(prov[k]) for k in ("role", "harness") if prov.get(k) is not None})
            out.append(rec)
    return out


def package_files(root: Path, project: dict) -> list[Path]:
    """Relative paths copied into the package. Reference documents and their local indexes are never included."""
    root = Path(root)
    rels: set[str] = set()
    for name in ("project.json", "inputs.lock.json", "state.json", "trace-baseline.json"):
        if (root / ".hi" / name).is_file():
            rels.add(f".hi/{name}")
    for inp in project.get("inputs", []):
        if inp.get("kind") in ("needs", "constraints") and (root / inp["path"]).is_file():
            rels.add(inp["path"])
    for s in trace.checked_stages(project, None):
        d = root / "hi" / s
        if d.is_dir():
            rels |= {p.relative_to(root).as_posix() for p in d.rglob("*") if p.is_file()}
    for f in ("hi/trace.json", "hi/trace-matrix.md"):
        if (root / f).is_file():
            rels.add(f)
    runs = root / ".hi" / "runs"
    if runs.is_dir():
        for r in runs.iterdir():
            for f in ("events.jsonl", "summary.json"):
                if (r / f).is_file():
                    rels.add(f".hi/runs/{r.name}/{f}")
    return [Path(r) for r in sorted(rels) if not r.startswith(".hi/docs/")]


def render_findings(root: Path, project: dict, profile: dict, level: str) -> str:
    lines = ["# Inspection findings", ""] + report.header(profile, level)
    for s in trace.checked_stages(project, None):
        fs = gates.findings(root, s)
        lines += [f"## {report.stage_label(profile, s)}", ""]
        if not fs:
            lines += ["No findings recorded.", ""]
            continue
        lines += ["| Id | Phase | Round | Item | Checklist | Severity | Status | Description |", "|---|---|---|---|---|---|---|---|"]
        for f in fs:
            desc = str(f.get("description", "")).replace("|", "/").replace("\n", " ")
            lines.append(f"| {f['id']} | {f['phase']} | {f['round']} | {f['target_id']} | {f['checklist_item']} | "
                         f"{f['severity']} | {f['status']} | {desc} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_gates(verdicts: dict, gaps: list[dict], status: str, profile: dict, level: str) -> str:
    lines = ["# Gate results and gaps", "", f"**Status: {status}**", ""] + report.header(profile, level) + [
        f"> {profile['disclaimer']}", "", "| Stage | Clause references | Gate | Verdict |", "|---|---|---|---|"]
    for s, gs in verdicts.items():
        lines += [f"| {report.stage_label(profile, s)} | {report.clause_refs(profile, s)} | {g} | {v} |"
                  for g, v in gs.items()]
    lines += ["", "## Gaps", ""]
    lines += [f"- `{g['code']}` {g['source']}: {g['message']}" for g in gaps] or ["None."]
    return "\n".join(lines) + "\n"


def deterministic_tar(src_dir: Path, out: Path, names: list[str]) -> Path:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name in sorted(names):
            data = (src_dir / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(data), FIXED_MTIME, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    with open(out, "wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
        gz.write(buf.getvalue())
    return out


def seal(root: Path) -> dict:
    root = Path(root)
    project = load_project(root)
    rigor = effective_rigor(project)
    profile = load_profile(rigor["profile"])
    gaps, verdicts = collect_gaps(root, project)
    status = READY if not gaps else BLOCKED
    acc = gates.accepted_stages(root)
    run_id = next((acc[s]["run_id"] for s in reversed(list(acc)) if acc[s].get("run_id")), None) or new_run_id()
    pkg_id = f"{run_id}-{utc_now().replace(':', '').replace('-', '')}"
    pkg = root / PKG_ROOT / pkg_id
    files_dir = pkg / "files"
    for rel in package_files(root, project):
        dst = files_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, dst)
    if (root / "hi/trace-matrix.md").is_file():
        shutil.copyfile(root / "hi/trace-matrix.md", pkg / "trace-matrix.md")
    write_text(pkg / "findings.md", render_findings(root, project, profile, rigor["level"]))
    write_text(pkg / "gates.md", render_gates(verdicts, gaps, status, profile, rigor["level"]))
    names = sorted(p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file())
    manifest = {
        "schema": "forge-c-hi/review-manifest@1", "run_id": run_id, "status": status, "gaps": gaps,
        "files": [{"path": n, "sha256": sha256_file(pkg / n)} for n in names if n not in TOP_FILES],
        "profile": rigor["profile"], "integrity_level": rigor["level"], "level_name": rigor["level_name"],
        "provenance_summary": provenance_summary(root, project),
        "tool_versions": {"forge-c-hi": __version__, "python": platform.python_version()},
        "disclaimer": profile["disclaimer"], "created_utc": utc_now(),
    }
    write_json(pkg / "manifest.json", manifest)
    tar = deterministic_tar(pkg, pkg / "review.tar.gz", [n for n in names if n not in TOP_FILES] + ["manifest.json"])
    write_text(pkg / "review.tar.gz.sha256", f"{sha256_file(tar)}  review.tar.gz\n")
    return {"status": status, "gaps": gaps, "package": pkg.relative_to(root).as_posix(), "run_id": run_id,
            "files": len(manifest["files"])}
