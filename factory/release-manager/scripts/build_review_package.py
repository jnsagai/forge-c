#!/usr/bin/env python3
"""Forge-C standalone deterministic handover packager, not an ISO 26262 release tool.

Python 3.10+. No third-party modules. Does not assess actual safety correctness.
Never manufactures missing engineering evidence; incomplete inputs yield BLOCKED package.
"""
from __future__ import annotations

import argparse
import hashlib
import fnmatch
import json
import os
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "forge-c/review-package-manifest/0.3"
STATUS_OK = "READY_FOR_OFFLINE_REVIEW"
STATUS_BAD = "BLOCKED"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def relative_policy_path(raw: str) -> PurePosixPath:
    p = PurePosixPath(raw)
    if not raw or p.is_absolute() or any(part in {"..", "."} for part in raw.split("/")) or "\\" in raw:
        raise ValueError(f"Unsafe policy path: {raw!r}")
    return p


def collect_files(workspace: Path) -> tuple[dict[str, bytes], list[str]]:
    collected: dict[str, bytes] = {}
    hazards: list[str] = []
    if not workspace.is_dir():
        return {}, ["workspace_not_found"]
    for directory, dirnames, filenames in os.walk(workspace, followlinks=False):
        d = Path(directory)
        for name in list(dirnames):
            if (d / name).is_symlink():
                hazards.append(f"symlink_not_allowed:{(d / name).relative_to(workspace).as_posix()}")
                dirnames.remove(name)
        for filename in filenames:
            f = d / filename
            rel = f.relative_to(workspace).as_posix()
            if f.is_symlink():
                hazards.append(f"symlink_not_allowed:{rel}")
                continue
            if not f.is_file():
                hazards.append(f"not_regular_file:{rel}")
                continue
            collected[rel] = f.read_bytes()
    return dict(sorted(collected.items())), sorted(hazards)


def audit_quality(report_bytes: bytes | None, policy: dict) -> tuple[list[str], dict]:
    gaps: list[str] = []
    observed: dict = {"run_status": "UNKNOWN", "checks": {}, "open_findings": []}
    if report_bytes is None:
        return [f"missing_quality_report:{policy['quality_report']}"], observed
    try:
        report = json.loads(report_bytes.decode("utf-8"))
        if not isinstance(report, dict):
            raise ValueError("quality report must be a JSON object")
    except (ValueError, UnicodeError) as exc:
        return [f"invalid_quality_report:{exc}"], observed
    observed = report
    if policy.get("require_completed_run") and report.get("run_status") != "COMPLETED":
        gaps.append(f"run_not_completed:{report.get('run_status', 'MISSING')}")
    checks = report.get("checks")
    if not isinstance(checks, dict):
        gaps.append("invalid_quality_checks")
        checks = {}
    for key in policy.get("required_quality_checks", []):
        if checks.get(key) is not True:
            gaps.append(f"failed_or_missing_quality_check:{key}")
    findings = report.get("open_findings")
    if not isinstance(findings, list):
        gaps.append("invalid_open_findings_list")
    elif policy.get("require_no_open_findings"):
        for i, item in enumerate(findings):
            if isinstance(item, dict):
                finding_id = item.get("id", f"index{i}")
            else:
                finding_id = f"index{i}"
            gaps.append(f"unresolved_finding:{finding_id}")
    return gaps, observed


def build(workspace: Path, out_dir: Path, run_id: str, policy_file: Path) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id):
        raise ValueError("run-id must be 1-80 alphanumeric, dot, dash, or underscore characters")
    if not policy_file.is_file():
        raise ValueError("release package policy not found")
    policy = json.loads(policy_file.read_text(encoding="utf-8"))
    if not isinstance(policy, dict):
        raise ValueError("policy must be a JSON object")
    sections = [str(relative_policy_path(x)) for x in policy["required_sections"]]
    required_files = [str(relative_policy_path(x)) for x in policy.get("required_files", [])]
    required_patterns = [str(relative_policy_path(x)) for x in policy.get("required_patterns", [])]
    quality_path = str(relative_policy_path(policy["quality_report"]))
    if any(not isinstance(x, str) or not re.fullmatch(r"[a-z0-9_]+", x) for x in policy["required_quality_checks"]):
        raise ValueError("Invalid quality check name in policy")
    workspace = workspace.resolve(strict=False)
    out_dir = out_dir.resolve(strict=False)
    # Avoid recursive ZIP self-inclusion. Use a sibling artifacts directory.
    if out_dir == workspace or workspace in out_dir.parents:
        raise ValueError("out-dir must not be inside the workspace")
    out_dir.mkdir(parents=True, exist_ok=True)
    files, hazards = collect_files(workspace)
    gaps: list[str] = list(hazards)
    for sec in sections:
        # Files under the required logical section; placeholders/empty dirs do not count.
        if not any(rel.startswith(sec.rstrip("/") + "/") and len(data) for rel, data in files.items()):
            gaps.append(f"missing_or_empty_section:{sec}")
    for path in required_files:
        if not files.get(path):
            gaps.append(f"missing_or_empty_file:{path}")
    for pattern in required_patterns:
        if not any(fnmatch.fnmatchcase(name, pattern) and len(blob) for name, blob in files.items()):
            gaps.append(f"missing_required_pattern:{pattern}")
    quality_gaps, report = audit_quality(files.get(quality_path), policy)
    gaps.extend(quality_gaps)
    gaps = sorted(set(gaps))
    status = STATUS_OK if not gaps else STATUS_BAD

    indexed = [
        {"path": "evidence/" + p, "size": len(data), "sha256": sha256(data)}
        for p, data in files.items()
    ]
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "status": status,
        "scope": "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED",
        "baseline": str(policy.get("baseline", "UNSPECIFIED")),
        "safety_target": str(policy.get("safety_target", "UNSPECIFIED")),
        "quality_report": quality_path,
        "quality_run_status": str(report.get("run_status", "UNKNOWN")),
        "reviewer": "EXTERNAL_HUMAN_REVIEW_REQUIRED",
        "file_count": len(indexed),
        "gap_count": len(gaps),
        "gaps": gaps,
        "files": indexed,
    }
    lines = [
        "# Forge-C — Offline Review Handover", "",
        f"**Run ID:** `{run_id}`", f"**Status:** `{status}`", f"**Evidence files:** {len(indexed)}",
        f"**Gaps:** {len(gaps)}", "",
        "This is an automatically generated evidence inventory, **not a production release**,",
        "ASPICE capability determination, tool qualification, or ISO 26262 ASIL B approval.",
        "The entire assessment and release decision is performed by authorized humans offline.", "",
        "## Gaps and unresolved blockers", "",
    ]
    lines += [f"- `{gap}`" for gap in gaps] if gaps else ["- No missing mechanical requirement detected against this package policy."]
    lines += ["", "## Independent review instructions", "", "1. Verify the archive SHA-256 against a separately obtained trusted checksum.", "2. Verify SHA256SUMS within the archive.", "3. Inspect `manifest.json`, quality reports, raw evidence, findings and traceability.", "4. Independently evaluate safety correctness, verification adequacy and process compliance.", "5. Document human disposition outside Fabro; never interpret a machine PASS as safety approval.", ""]

    contents: dict[str, bytes] = {"evidence/" + path: data for path, data in files.items()}
    contents["manifest.json"] = json_bytes(manifest)
    contents["missing_artifacts.json"] = json_bytes({"run_id": run_id, "status": status, "gaps": gaps})
    contents["REVIEW_SUMMARY.md"] = ("\n".join(lines)).encode("utf-8")
    checksum_lines = [f"{sha256(data)}  {name}" for name, data in sorted(contents.items())]
    contents["SHA256SUMS.txt"] = ("\n".join(checksum_lines) + "\n").encode("utf-8")
    name = f"forge-c-{run_id}-review.zip"
    archive_path = out_dir / name
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arcname, data in sorted(contents.items()):
            zi = zipfile.ZipInfo(arcname, date_time=FIXED_ZIP_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    archive_hash = sha256(archive_path.read_bytes())
    (out_dir / (name + ".sha256")).write_text(f"{archive_hash}  {name}\n", encoding="ascii")
    return {"run_id": run_id, "package_status": status, "archive": str(archive_path), "archive_sha256": archive_hash,
            "gap_count": len(gaps), "evidence_file_count": len(indexed)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--policy", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(args.workspace, args.out_dir, args.run_id, args.policy)
        print(json.dumps(result, sort_keys=True))
        return 0  # BLOCKED is a valid handover outcome; consumer reads machine status
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"fatal_packaging_error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
