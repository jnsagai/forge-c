#!/usr/bin/env python3
"""Independent re-check of a sealed forge-c-hi review package (T046). Standard library only, no forge-c-hi import.

    python3 verify_package.py <package-dir>

Checks that every file listed in manifest.json exists with the listed sha256, that review.tar.gz matches its .sha256
file and contains exactly the listed files plus manifest.json with the same bytes, that READY has no gaps, and that the
disclaimer is present. Prints one JSON object; exit 0 when every check passes, 1 otherwise, 2 on usage error.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tarfile
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(pkg: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest_bytes = (pkg / "manifest.json").read_bytes()
        m = json.loads(manifest_bytes)
    except (OSError, ValueError) as exc:
        return [f"manifest.json unreadable: {exc}"]
    if m.get("schema") != "forge-c-hi/review-manifest@1":
        errors.append("unexpected manifest schema")
    if m.get("status") not in ("READY_FOR_OFFLINE_REVIEW", "BLOCKED"):
        errors.append(f"invalid status {m.get('status')!r}")
    if m.get("status") == "READY_FOR_OFFLINE_REVIEW" and m.get("gaps"):
        errors.append("READY package lists gaps")
    if len(str(m.get("disclaimer", ""))) < 20:
        errors.append("disclaimer missing")
    listed = {}
    for f in m.get("files", []):
        p = pkg / f["path"]
        if ".." in Path(f["path"]).parts or Path(f["path"]).is_absolute():
            errors.append(f"unsafe path {f['path']}")
            continue
        listed[f["path"]] = f["sha256"]
        if not p.is_file():
            errors.append(f"missing {f['path']}")
        elif sha(p.read_bytes()) != f["sha256"]:
            errors.append(f"hash mismatch {f['path']}")
    on_disk = {p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file()}
    extra = on_disk - set(listed) - {"manifest.json", "review.tar.gz", "review.tar.gz.sha256"}
    errors += [f"unlisted file {e}" for e in sorted(extra)]
    tar_path = pkg / "review.tar.gz"
    try:
        want = (pkg / "review.tar.gz.sha256").read_text().split()[0]
        if sha(tar_path.read_bytes()) != want:
            errors.append("review.tar.gz does not match review.tar.gz.sha256")
        with tarfile.open(tar_path, "r:gz") as tar:
            members = {mi.name: mi for mi in tar.getmembers()}
            if set(members) != set(listed) | {"manifest.json"}:
                errors.append(f"archive members differ from the manifest ({len(members)} vs {len(listed) + 1})")
            for name, mi in members.items():
                data = tar.extractfile(mi).read()
                if name == "manifest.json":
                    if data != manifest_bytes:
                        errors.append("archived manifest differs from manifest.json")
                elif name in listed and sha(data) != listed[name]:
                    errors.append(f"archived {name} hash mismatch")
    except (OSError, IndexError, tarfile.TarError) as exc:
        errors.append(f"archive check failed: {exc}")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"status": "ERROR", "error": "usage: verify_package.py <package-dir>"}))
        return 2
    pkg = Path(argv[1])
    errors = verify(pkg)
    status = json.loads((pkg / "manifest.json").read_text()).get("status") if not errors or (pkg / "manifest.json").is_file() else None
    print(json.dumps({"verified": not errors, "package_status": status, "errors": errors[:20]}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
