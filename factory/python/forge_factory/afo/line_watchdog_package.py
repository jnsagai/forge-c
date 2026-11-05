"""Reproducible host-side watchdog code archive from committed source, without runtime state or policy copies.

Build only: installation/activation and authenticated operator intent remain explicit deployment actions.
The host interpreter and archive must live outside the application data volume. Authoritative policy/state
remain on that volume; missing volume therefore refuses recovery while the host check can still execute.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import io
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import zipfile
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, data_root

# The normal CRE policy path imports YAML and JSON Schema, including rpds' native module.
# Keep this explicit closure small; exact versions come from the committed project lock.
DEPENDENCIES = ("PyYAML", "jsonschema", "attrs", "jsonschema-specifications", "referencing", "rpds-py",
                "typing-extensions")


def _dependency_files(repo: Path, revision: str) -> tuple[dict[str, bytes], dict]:
    lock = subprocess.run(["git", "show", f"{revision}:requirements/forge-factory.lock"], cwd=repo,
                          check=True, capture_output=True, timeout=30, text=True).stdout
    pins = dict(re.findall(r"^([a-z0-9-]+)==([^\s]+)", lock, re.M))
    files: dict[str, bytes] = {}
    distributions = {}
    for name in DEPENDENCIES:
        normalized = name.lower().replace("_", "-")
        distribution = importlib.metadata.distribution(name)
        if distribution.version != pins.get(normalized):
            raise ValueError(f"WATCHDOG_DEPENDENCY_VERSION_MISMATCH:{name}")
        distributions[normalized] = distribution.version
        for record in distribution.files or ():
            relative = Path(str(record))
            # Distribution RECORD also lists console scripts outside site-packages. None are needed here.
            if relative.is_absolute() or ".." in relative.parts or "__pycache__" in relative.parts:
                continue
            source = Path(distribution.locate_file(record))
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"WATCHDOG_DEPENDENCY_FILE_INVALID:{name}:{relative}")
            body = source.read_bytes()
            if record.hash is not None:
                if record.hash.mode != "sha256":
                    raise ValueError("WATCHDOG_DEPENDENCY_HASH_ALGORITHM_UNSUPPORTED")
                actual = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=").decode()
                if actual != record.hash.value:
                    raise ValueError(f"WATCHDOG_DEPENDENCY_RECORD_HASH_MISMATCH:{name}:{relative}")
            path = relative.as_posix()
            if path in files and files[path] != body:
                raise ValueError("WATCHDOG_DEPENDENCY_PATH_COLLISION")
            files[path] = body
    if not files or not any(name.startswith("rpds/") and name.endswith(".so") for name in files):
        raise ValueError("WATCHDOG_DEPENDENCIES_INCOMPLETE")
    manifest = {"schema": "forge-c/line-watchdog-dependencies/1", "distributions": distributions,
                "lock_sha256": hashlib.sha256(lock.encode()).hexdigest(),
                "interpreter": {"cache_tag": sys.implementation.cache_tag, "platform": sysconfig.get_platform(),
                                "soabi": sysconfig.get_config_var("SOABI")},
                "files": {name: hashlib.sha256(body).hexdigest() for name, body in sorted(files.items())}}
    return files, manifest


def _publish_dependencies(destination: Path, files: dict[str, bytes], manifest: dict) -> None:
    expected = files | {"watchdog-dependencies-manifest.json": canonical_json(manifest) + b"\n"}
    if destination.exists():
        actual = {p.relative_to(destination).as_posix(): p for p in destination.rglob("*") if p.is_file()}
        if (set(actual) != set(expected) or any(p.is_symlink() for p in destination.rglob("*"))
                or any(actual[name].read_bytes() != body for name, body in expected.items())):
            raise ValueError("WATCHDOG_DEPENDENCIES_ALREADY_EXIST_WITH_OTHER_CONTENT")
        return
    temporary = Path(tempfile.mkdtemp(prefix=".watchdog-dependencies-", dir=destination.parent))
    try:
        for name, body in sorted(expected.items()):
            path = temporary / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            path.chmod(0o444)
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def verify_runtime_dependencies() -> dict:
    """Validate the archive-bound native/Python dependency tree before normal policy loading.

    Source-tree execution is the existing development path. A zipimport deployment must
    explicitly name its complete sibling tree in PYTHONPATH; nothing is installed or fetched.
    """
    archive = getattr(__loader__, "archive", None)
    if archive is None:
        return {"packaged": False}
    from .durable import strict_json

    sys.dont_write_bytecode = True
    root = Path(str(archive) + ".dependencies")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("WATCHDOG_DEPENDENCY_TREE_MISSING_OR_SYMLINK")
    with zipfile.ZipFile(archive) as code:
        expected = strict_json(code.read("watchdog-code-manifest.json"), 4 * 1024 * 1024)
    manifest_path = root / "watchdog-dependencies-manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("WATCHDOG_DEPENDENCY_MANIFEST_SYMLINK")
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected.get("dependencies_manifest_sha256"):
        raise ValueError("WATCHDOG_DEPENDENCY_MANIFEST_CHANGED")
    manifest = strict_json(raw, 4 * 1024 * 1024)
    interpreter = {"cache_tag": sys.implementation.cache_tag, "platform": sysconfig.get_platform(),
                   "soabi": sysconfig.get_config_var("SOABI")}
    if manifest.get("interpreter") != interpreter:
        raise ValueError("WATCHDOG_DEPENDENCY_INTERPRETER_ABI_MISMATCH")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("WATCHDOG_DEPENDENCY_MANIFEST_INVALID")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("WATCHDOG_DEPENDENCY_SYMLINK")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(files) | {manifest_path.name}:
        raise ValueError("WATCHDOG_DEPENDENCY_INVENTORY_CHANGED")
    for name, digest in files.items():
        if (not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("WATCHDOG_DEPENDENCY_MANIFEST_INVALID")
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("WATCHDOG_DEPENDENCY_FILE_CHANGED")
    if str(root.absolute()) not in {str(Path(p).absolute()) for p in sys.path if p}:
        raise ValueError("WATCHDOG_DEPENDENCY_PATH_NOT_CONFIGURED")
    # Fail before importing a foreign site-package copy even when the correct tree is also present.
    import importlib.util

    for module in ("yaml", "jsonschema", "attr", "attrs", "jsonschema_specifications", "referencing", "rpds"):
        spec = importlib.util.find_spec(module)
        if spec is None or not spec.origin or not Path(spec.origin).absolute().is_relative_to(root.absolute()):
            raise ValueError(f"WATCHDOG_DEPENDENCY_IMPORT_OUTSIDE_BUNDLE:{module}")
    return {"packaged": True, "manifest_sha256": hashlib.sha256(raw).hexdigest()}


def build(destination: Path, *, repo: Path = REPO_ROOT, application_data: Path | None = None) -> dict:
    destination = Path(destination)
    data = Path(application_data or data_root()).resolve()
    if destination.is_symlink() or destination.resolve().is_relative_to(data):
        raise ValueError("WATCHDOG_ARCHIVE_MUST_BE_OUTSIDE_APPLICATION_VOLUME")
    dependencies = destination.with_name(destination.name + ".dependencies")
    if dependencies.is_symlink() or dependencies.resolve().is_relative_to(data):
        raise ValueError("WATCHDOG_DEPENDENCIES_MUST_BE_OUTSIDE_APPLICATION_VOLUME")
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
    dependency_files, dependency_manifest = _dependency_files(repo, revision)
    dependency_hash = hashlib.sha256(canonical_json(dependency_manifest) + b"\n").hexdigest()
    manifest = {"schema": "forge-c/line-watchdog-code/1", "source_revision": revision,
                "dependencies_manifest_sha256": dependency_hash,
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
    destination.parent.mkdir(parents=True, exist_ok=True)
    _publish_dependencies(dependencies, dependency_files, dependency_manifest)
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
            "dependency_path": str(dependencies), "dependencies": str(dependencies),
            "dependencies_manifest_sha256": dependency_hash,
            "pythonpath": os.pathsep.join((str(destination), str(dependencies))),
            "dependency_interpreter": dependency_manifest["interpreter"],
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
