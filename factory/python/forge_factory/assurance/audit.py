"""EASA-T003/T064/T065 — read-only retrospective audit of sealed review archives (LL r101 / HAL r102).

`freeze()` reads the zip in place (never extracts into, renames or rewrites the archive) and records the archive
digest, every member digest, the bindings the package itself carries (workspace head, dirty flag, Fabro run id,
factory revision if any) and every expected fact that is ABSENT as UNKNOWN - nothing is inferred.
`verify()` re-checks a frozen manifest against the bytes and the commit a review refers to: changed archive ->
STALE_DIGEST, changed member -> MEMBER_CHANGED, different commit -> STALE_BASELINE (AT-073).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from ..common import pretty_json, sha256_file, utc_now

EXPECTED = {  # fact -> where a package would carry it
    "factory_revision": "operations/run/run-summary.json:factory_revision",
    "fabro_run_id": "operations/run/run-summary.json:fabro_run_id",
    "model_per_role": "operations/tokens/usage-by-agent.json:by_stage[].model",
    "silicon_revision": "configuration/target_baseline.json:silicon_revision",
    "errata_baseline": "configuration/target_baseline.json:errata",
    "approved_safety_scope": "configuration/safety_scope.json",
}


def _members(z: zipfile.ZipFile) -> dict[str, str]:
    out = {}
    for info in z.infolist():
        if info.is_dir():
            continue
        h = hashlib.sha256()
        with z.open(info) as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        out[info.filename] = h.hexdigest()
    return out


def _json(z: zipfile.ZipFile, name: str) -> dict | None:
    try:
        return json.loads(z.read(name))
    except (KeyError, ValueError):
        return None


def freeze(zip_path: Path) -> dict:
    zip_path = Path(zip_path)
    side = zip_path.with_name(zip_path.name + ".sha256")
    archive_sha = sha256_file(zip_path)
    sidecar = side.read_text().split()[0] if side.is_file() else None
    with zipfile.ZipFile(zip_path) as z:
        members = _members(z)
        man = _json(z, "manifest.json") or {}
        summary = _json(z, "evidence/operations/run/run-summary.json") or {}
        usage = _json(z, "evidence/operations/tokens/usage-by-agent.json") or {}
        target = _json(z, "evidence/configuration/target_baseline.json") or {}
        sums = z.read("SHA256SUMS.txt").decode() if "SHA256SUMS.txt" in members else ""
    listed = {ln.split(None, 1)[1].lstrip("*").strip(): ln.split()[0] for ln in sums.splitlines() if ln.strip()}
    sums_bad = sorted(n for n, h in listed.items() if members.get(n) != h)
    unlisted = sorted(set(members) - set(listed) - {"SHA256SUMS.txt"})
    facts = {
        "factory_revision": summary.get("factory_revision"),
        "fabro_run_id": summary.get("fabro_run_id"),
        "model_per_role": [s.get("model") for s in usage.get("by_stage") or []] or None,
        "silicon_revision": None if str(target.get("silicon_revision", "")).upper() in ("", "UNSPECIFIED")
        else target.get("silicon_revision"),
        "errata_baseline": target.get("errata"),
        "approved_safety_scope": None if "evidence/configuration/safety_scope.json" not in members else "present",
    }
    unknown = [{"fact": k, "where_expected": EXPECTED[k], "status": "UNKNOWN"} for k, v in facts.items() if not v]
    claims = []
    if man.get("safety_target") and not facts["approved_safety_scope"]:
        claims.append({"code": "SAFETY_TARGET_WITHOUT_APPROVED_SCOPE", "text": man["safety_target"]})
    if summary.get("dirty"):
        claims.append({"code": "BUILT_FROM_DIRTY_WORKSPACE", "text": f"workspace_head {summary.get('workspace_head')}"})
    if usage.get("basis") == "unknown":
        claims.append({"code": "TOKEN_USAGE_BASIS_UNKNOWN", "text": str(usage.get("reason"))})
    return {"schema": "forge-c/easa-frozen-baseline/0.1", "frozen_at": utc_now(), "run_id": man.get("run_id"),
            "archive": str(zip_path), "archive_sha256": archive_sha, "sidecar_sha256": sidecar,
            "sidecar_match": sidecar == archive_sha, "member_count": len(members), "members": members,
            "sha256sums_mismatch": sums_bad, "unlisted_members": unlisted,
            "bindings": {"workspace_head": summary.get("workspace_head"), "workspace_dirty": summary.get("dirty"),
                         "fabro_run_id": summary.get("fabro_run_id"),
                         "factory_revision": summary.get("factory_revision")},
            "package_status": man.get("status"), "package_scope": man.get("scope"),
            "unknown_facts": unknown, "unsupported_claims": claims}


def verify(frozen: dict, zip_path: Path, review_commit: str | None) -> list[str]:
    issues = []
    if sha256_file(Path(zip_path)) != frozen["archive_sha256"]:
        issues.append("STALE_DIGEST:archive")
        with zipfile.ZipFile(zip_path) as z:
            now = _members(z)
        issues += [f"MEMBER_CHANGED:{n}" for n in sorted(set(now) | set(frozen["members"]))
                   if now.get(n) != frozen["members"].get(n)]
    bound = frozen["bindings"].get("factory_revision") or frozen["bindings"].get("workspace_head")
    if review_commit is not None and (not bound or not str(bound).startswith(review_commit[:7])
                                      and not str(review_commit).startswith(str(bound)[:7])):
        issues.append(f"STALE_BASELINE:{review_commit}!={bound}")
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.assurance.audit")
    ap.add_argument("zip", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    before = sha256_file(a.zip)
    rep = freeze(a.zip)
    if sha256_file(a.zip) != before:  # paranoia: the audit must never alter the archive
        print("ARCHIVE_CHANGED_DURING_AUDIT")
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(rep), encoding="utf-8")
    print(f"{rep['run_id']} sha={rep['archive_sha256'][:12]} members={rep['member_count']} "
          f"sidecar_match={rep['sidecar_match']} unknown={len(rep['unknown_facts'])} claims={len(rep['unsupported_claims'])}")
    return 0 if rep["sidecar_match"] and not rep["sha256sums_mismatch"] else 1


if __name__ == "__main__":
    sys.exit(main())
