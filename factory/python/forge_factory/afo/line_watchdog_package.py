"""Reproducible host-side watchdog code archive from committed source, without runtime state or policy copies.

Build only: installation/activation and authenticated operator intent remain explicit deployment actions.
The host interpreter and archive must live outside the application data volume. Authoritative policy/state
remain on that volume; missing volume therefore refuses recovery while the host check can still execute.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile

from ..common import REPO_ROOT, canonical_json, data_root


def build(destination: Path, *, repo: Path = REPO_ROOT, application_data: Path | None = None) -> dict:
    destination = Path(destination)
    data = Path(application_data or data_root()).resolve()
    if destination.is_symlink() or destination.resolve().is_relative_to(data):
        raise ValueError("WATCHDOG_ARCHIVE_MUST_BE_OUTSIDE_APPLICATION_VOLUME")
    revision = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=repo,
                              check=True, capture_output=True, timeout=30, text=True).stdout.strip()
    raw = subprocess.run(["git", "archive", "--format=tar", revision, "factory/python/forge_factory"],
                         cwd=repo, check=True, capture_output=True, timeout=30).stdout
    files = {}
    prefix = "factory/python/"
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for entry in archive.getmembers():
            if entry.isfile() and entry.name.startswith(prefix) and entry.name.endswith(".py"):
                name = entry.name[len(prefix):]
                if ".." in Path(name).parts:
                    raise ValueError("WATCHDOG_ARCHIVE_PATH_ESCAPE")
                files[name] = archive.extractfile(entry).read()
    required = {"forge_factory/afo/line_watchdog.py", "forge_factory/afo/operations.py",
                "forge_factory/afo/host.py"}
    if not required <= files.keys():
        raise ValueError("WATCHDOG_SOURCE_INCOMPLETE")
    manifest = {"schema": "forge-c/line-watchdog-code/1", "source_revision": revision,
                "purpose": "HOST_CODE_ONLY_NO_POLICY_OR_RUNTIME_AUTHORITY",
                "files": {name: hashlib.sha256(body).hexdigest() for name, body in sorted(files.items())}}
    files["watchdog-code-manifest.json"] = canonical_json(manifest) + b"\n"
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o444 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body)
    output = memory.getvalue()
    if destination.exists():
        if destination.read_bytes() != output:
            raise ValueError("WATCHDOG_ARCHIVE_ALREADY_EXISTS_WITH_OTHER_CONTENT")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".watchdog-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(output)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o444)
            os.replace(temporary, destination)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()
    return {"source_revision": revision, "archive": str(destination),
            "sha256": hashlib.sha256(output).hexdigest(), "source_files": len(manifest["files"]),
            "status": "BUILT_NOT_INSTALLED_OR_AUTHORIZED"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--application-data", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.destination, application_data=args.application_data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
