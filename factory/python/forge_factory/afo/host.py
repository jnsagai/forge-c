"""AFO-T010 (AFO-FR-011, AT-006) - stable data-volume sentinel and fail-closed preflight.

Every AFO-managed service runs `python -m forge_factory.afo.host preflight` as ExecStartPre (and the unit also has
RequiresMountsFor=<data root>). It refuses to start (exit 1) unless ALL hold:
  * the data root exists and is not on the root filesystem's device (an unmounted mount point would be);
  * the filesystem holding it has the UUID recorded at install time in the sentinel `<data root>/<marker>`;
  * the sentinel names this data root (a volume mounted elsewhere is refused);
  * a write probe (create, fsync, read back, delete) succeeds.
So a missing or wrong volume never receives writes. `init` writes the sentinel - an operator action, done once.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import uuid
from pathlib import Path

from ..common import data_root, utc_now

MARKER = "state/.forge-volume-id"
MAX_SENTINEL_BYTES = 4096


def fs_info(path: Path) -> dict:
    try:
        r = subprocess.run(["findmnt", "-n", "-J", "-o", "TARGET,SOURCE,FSTYPE,UUID", "--target", str(path)],
                           capture_output=True, text=True, timeout=10, check=True)
        fs = json.loads(r.stdout)["filesystems"][0]
        if not isinstance(fs, dict) or not all(isinstance(fs.get(k), str) and fs[k] for k in ("target", "source")):
            return {}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
        return {}
    return {k: fs.get(k) or "" for k in ("target", "source", "fstype", "uuid")}


def read_sentinel(path: Path) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("volume sentinel must be a regular file")
        data = stream.read(MAX_SENTINEL_BYTES + 1)
    if len(data) > MAX_SENTINEL_BYTES:
        raise ValueError("volume sentinel is too large")
    sentinel = json.loads(data)
    if not isinstance(sentinel, dict) or any(
        not isinstance(sentinel.get(key), str) or not sentinel[key].strip() for key in ("uuid", "data_root")
    ):
        raise ValueError("volume sentinel requires a UUID and data root")
    return sentinel


def preflight(root: Path | None = None, marker: str = MARKER) -> dict:
    root = Path(root or data_root())
    issues = []
    if not root.is_dir():
        return {"ok": False, "issues": [f"DATA_ROOT_MISSING:{root}"], "root": str(root)}
    fs, rootfs = fs_info(root), fs_info(Path("/"))
    if not fs or not rootfs:
        issues.append("MOUNT_UNKNOWN")
    elif fs["target"] == "/" or fs.get("source") == rootfs.get("source"):
        issues.append(f"DATA_ROOT_ON_ROOT_FS:{fs.get('source')} (volume not mounted?)")
    elif not isinstance(fs.get("uuid"), str) or not fs["uuid"].strip():
        issues.append("MOUNT_UUID_UNAVAILABLE")
    s = root / marker
    try:
        sentinel = read_sentinel(s)
    except (OSError, ValueError):
        issues.append(f"SENTINEL_MISSING_OR_INVALID:{s}")
    else:
        if fs and sentinel.get("uuid") != fs.get("uuid"):
            issues.append(f"VOLUME_UUID_MISMATCH:sentinel={sentinel.get('uuid')} mounted={fs.get('uuid')}")
        if sentinel.get("data_root") != str(root):
            issues.append(f"SENTINEL_FOR_OTHER_ROOT:{sentinel.get('data_root')}")
    if not issues:
        probe = root / "state" / f".afo-write-probe-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        created = False
        try:
            with probe.open("xb") as f:
                created = True
                f.write(b"forge")
                f.flush()
                os.fsync(f.fileno())
            ok = probe.read_bytes() == b"forge"
        except OSError as exc:
            ok = False
            issues.append(f"WRITE_PROBE_FAILED:{type(exc).__name__}")
        finally:
            if created:
                try:
                    probe.unlink()
                except OSError as exc:
                    issues.append(f"WRITE_PROBE_CLEANUP_FAILED:{type(exc).__name__}")
        if not ok and not issues:
            issues.append("WRITE_PROBE_MISMATCH")
    return {"ok": not issues, "issues": issues, "root": str(root), "filesystem": fs, "checked_at": utc_now()}


def init(root: Path | None = None, marker: str = MARKER) -> Path:
    """Operator action: record the mounted volume's UUID in the sentinel (refuses a root-filesystem data root)."""
    root = Path(root or data_root())
    fs, rootfs = fs_info(root), fs_info(Path("/"))
    if not fs.get("uuid") or fs.get("target") == "/" or fs.get("source") == rootfs.get("source"):
        raise SystemExit(f"REFUSED: {root} is not on a separately mounted volume with a UUID ({fs})")
    s = root / marker
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text(json.dumps({"uuid": fs["uuid"], "data_root": str(root), "fstype": fs.get("fstype"),
                             "created_at": utc_now()}) + "\n")
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.afo.host")
    ap.add_argument("cmd", choices=["preflight", "init"])
    ap.add_argument("--root", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "init":
        print(init(a.root))
        return 0
    r = preflight(a.root)
    print(json.dumps(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
