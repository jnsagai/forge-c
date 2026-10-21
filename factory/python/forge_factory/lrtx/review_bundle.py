"""LRTX-T025: package the feature 010 results for offline review (never a release, never an automatic promotion).

    python -m forge_factory.lrtx.review_bundle --out-dir <dir outside the repository>

The bundle is a deterministic zip of the committed feature files at HEAD:
- the specification, plan, tasks and validation record;
- ADR-0013/0014 and the start guide;
- every LRTX evidence run;
- the CRE decisions the validation record cites.

It also holds a manifest (git head, per-task tick state and evidence status, per-file SHA-256) and SHA256SUMS.txt, and a
sidecar `<zip>.sha256` is written next to it. A working tree with uncommitted feature files is refused, so the bundle
always names a reproducible revision. Task states are copied from tasks.md and the evidence records, never inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

from ..common import REPO_ROOT, utc_now

FEATURE = "specs/010-local-rtx-optimization"
INCLUDE = (FEATURE, "docs/adr/ADR-0013-preserve-codex-claude-local-rtx-line.md",
           "docs/adr/ADR-0014-structured-local-author-tasks.md", "LOCAL_RTX_START.md",
           "config/factory/profiles/local-rtx-v1.yaml")
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
README = """# Feature 010 local RTX profile: offline review bundle

This bundle is a candidate for offline review. It is not a release and not a qualification. Nothing in it promotes,
merges or deploys anything: PR #34 is merged into main only after the owner accepts it. Task states are copied from
tasks.md and the recorded evidence runs; BLOCKED and NOT_RUN results stay as they are. No compliance or safety
approval is claimed.
"""


def _git(*a: str, repo: Path) -> str:
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def files(repo: Path) -> list[str]:
    tracked = set(_git("ls-files", repo=repo).splitlines())
    want = [f for f in tracked if any(f == p or f.startswith(p.rstrip("/") + "/") for p in INCLUDE)]
    want += [f for f in tracked if re.match(r"evidence/v0\.4/runs/LRTX-[^/]+/", f)]
    val = (repo / FEATURE / "validation.md").read_text() if (repo / FEATURE / "validation.md").is_file() else ""
    for pid in sorted(set(re.findall(r"pd-[0-9a-f]{8,20}", val))):
        want += [f for f in tracked if f.startswith(f"evidence/cre/decisions/{pid}")]
    return sorted(set(want))


def tasks(repo: Path) -> list[dict]:
    """Per task: the tick state and the status of every evidence record its tasks.md line cites (or, when it cites
    none, the record named after the task). A tick without an evidence-run record says so and names what it cites."""
    out = []
    for line in (repo / FEATURE / "tasks.md").read_text().splitlines():
        m = re.match(r"- \[( |x|X)\] (LRTX-T\d{3})\b", line)
        if not m:
            continue
        refs = re.findall(r"`(evidence/v0\.4/runs/[^`]+/latest\.json)`", line) or \
            [f"evidence/v0.4/runs/{m.group(2)}/latest.json"]
        recs = {r: json.loads((repo / r).read_text())["status"] for r in refs if (repo / r).is_file()}
        if recs:
            st = "PASS" if all(v == "PASS" for v in recs.values()) and len(recs) == len(refs) else "NOT_PASS"
        else:
            cites = [c for c in re.findall(r"`([^`]+)`", line) if not c.startswith("evidence/v0.4/runs/")]
            st = "NO_EVIDENCE_RUN" + (f" (cites {', '.join(cites)})" if cites else "")
        out.append({"task": m.group(2), "ticked": m.group(1) != " ", "evidence_status": st, "evidence": recs})
    return out


def build(out_dir: Path, repo: Path = REPO_ROOT) -> dict:
    dirty = _git("status", "--porcelain", "--", *INCLUDE, "evidence/v0.4/runs", "evidence/cre/decisions", repo=repo)
    if dirty:
        raise SystemExit(f"UNCOMMITTED_FEATURE_FILES (commit first so the bundle names a revision):\n{dirty[:600]}")
    head = _git("rev-parse", "HEAD", repo=repo)
    fl = files(repo)
    sums = {f: hashlib.sha256((repo / f).read_bytes()).hexdigest() for f in fl}
    manifest = {"schema": "forge-c/lrtx-review-bundle/1", "feature": "010-local-rtx-optimization", "git_head": head,
                "built_at": utc_now(), "status": "OFFLINE_REVIEW_CANDIDATE (not a release; no automatic promotion)",
                "tasks": tasks(repo), "files": len(fl)}
    out_dir.mkdir(parents=True, exist_ok=True)
    z = out_dir / f"forge-c-feature-010-review-{head[:12]}.zip"

    def add(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
        zi = zipfile.ZipInfo(name, FIXED_TIME)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o444 << 16
        zf.writestr(zi, data)

    with zipfile.ZipFile(z, "w") as zf:
        add(zf, "README.md", README.encode())
        add(zf, "MANIFEST.json", json.dumps({k: v for k, v in manifest.items() if k != "built_at"}, indent=1,
                                            sort_keys=True).encode())
        add(zf, "SHA256SUMS.txt", "".join(f"{h}  {f}\n" for f, h in sums.items()).encode())
        for f in fl:
            add(zf, f"files/{f}", (repo / f).read_bytes())
    digest = hashlib.sha256(z.read_bytes()).hexdigest()
    z.with_name(z.name + ".sha256").write_text(f"{digest}  {z.name}\n")
    return {**manifest, "zip": str(z), "sha256": digest}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.out_dir.resolve().is_relative_to(REPO_ROOT.resolve()):
        raise SystemExit("OUT_DIR_INSIDE_REPOSITORY: archives are kept outside the repository")
    r = build(a.out_dir)
    print(json.dumps({k: r[k] for k in ("zip", "sha256", "git_head", "files")} |
                     {"ticked": sum(t["ticked"] for t in r["tasks"]), "tasks": len(r["tasks"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
