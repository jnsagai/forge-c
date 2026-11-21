"""Bounded disposable scratch cleanup; never evidence/archives/ledger retention."""

from __future__ import annotations

import math
import os
import stat
import time
from pathlib import Path

from .durable import Refused

SCRATCH_SCAN_LIMIT = 512


def clean(root, *, pinned=(), max_files=32, max_bytes=10 * 1024 * 1024, older_than=86400, now=None):
    root = Path(root)
    now = time.time() if now is None else now
    if (
        type(max_files) is not int or not 0 <= max_files <= 128
        or type(max_bytes) is not int or max_bytes < 0
        or type(older_than) not in (int, float) or not math.isfinite(older_than) or older_than < 3600
        or type(now) not in (int, float) or not math.isfinite(now)
    ):
        raise Refused("HOUSEKEEPING_BOUND_INVALID")
    # Walk and unlink through the same directory descriptor, including if the
    # path is renamed after the disposable marker has been checked.
    try:
        fd = os.open(root, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise Refused("DISPOSABLE_ROOT_REQUIRED") from exc
    try:
        try:
            marker = os.open(".forge-disposable", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                marker_stat = os.fstat(marker)
                contents = os.read(marker, 129) if stat.S_ISREG(marker_stat.st_mode) else b""
                if len(contents) > 128 or contents.strip() != b"forge-c-scratch-v1":
                    raise Refused("DISPOSABLE_ROOT_REQUIRED")
            finally:
                os.close(marker)
        except OSError as exc:
            raise Refused("DISPOSABLE_ROOT_REQUIRED") from exc

        root = root.resolve()
        pins = {Path(p).resolve() for p in pinned}
        count = size = scanned = 0
        scan_limit_reached = False
        with os.scandir(fd) as entries:
            for entry in entries:
                if count >= max_files:
                    break
                if scanned == SCRATCH_SCAN_LIMIT:
                    scan_limit_reached = True
                    break
                scanned += 1
                if entry.name == ".forge-disposable":
                    continue
                path = root / entry.name
                if pins and (path in pins or not pins.isdisjoint(path.parents)):
                    continue
                try:
                    st = entry.stat(follow_symlinks=False)
                    if not stat.S_ISREG(st.st_mode) or now - st.st_mtime < older_than or size + st.st_size > max_bytes:
                        continue
                    os.unlink(entry.name, dir_fd=fd)
                except FileNotFoundError:
                    continue
                count += 1
                size += st.st_size
        return {"deleted_files": count, "deleted_bytes": size, "evidence_deleted": False,
                "scanned_entries": scanned, "scan_limit_reached": scan_limit_reached}
    finally:
        os.close(fd)


def capacity(root, *, reserve_bytes=1024**3):
    import shutil

    root = Path(root)
    try:
        st = os.statvfs(root)
        usage = shutil.disk_usage(root)
        return {
            "ok": usage.free >= reserve_bytes and st.f_favail > 1024 and not st.f_flag & os.ST_RDONLY,
            "free_bytes": usage.free,
            "free_inodes": st.f_favail,
            "reserve_bytes": reserve_bytes,
        }
    except OSError as exc:
        return {"ok": False, "reason": type(exc).__name__}
