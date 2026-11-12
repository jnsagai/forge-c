"""Bounded disposable scratch cleanup; never evidence/archives/ledger retention."""

from __future__ import annotations

import os
import time
from pathlib import Path

from .durable import Refused


def clean(root, *, pinned=(), max_files=32, max_bytes=10 * 1024 * 1024, older_than=86400, now=None):
    root = Path(root)
    now = time.time() if now is None else now
    if max_files < 0 or max_files > 128 or max_bytes < 0 or older_than < 3600:
        raise Refused("HOUSEKEEPING_BOUND_INVALID")
    # Only an explicit private disposable root can be cleaned. It cannot be the application data root.
    marker = root / ".forge-disposable"
    if root.is_symlink() or not marker.is_file() or marker.is_symlink() or marker.read_text().strip() != "forge-c-scratch-v1":
        raise Refused("DISPOSABLE_ROOT_REQUIRED")
    root = root.resolve()
    pins = [Path(p).resolve() for p in pinned]
    count = size = 0
    # No recursion, no symlink following, no deletion outside a bounded direct scratch inventory.
    for p in sorted(root.iterdir())[: max_files + 1]:
        if count >= max_files:
            break
        if p == marker or p.is_symlink() or not p.is_file() or any(p.resolve() == q or q in p.resolve().parents for q in pins):
            continue
        st = p.stat()
        if now - st.st_mtime < older_than or size + st.st_size > max_bytes:
            continue
        p.unlink()
        count += 1
        size += st.st_size
    return {"deleted_files": count, "deleted_bytes": size, "evidence_deleted": False}


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
