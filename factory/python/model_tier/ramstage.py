"""RAM staging of model files (feature 017, FR-031, research R3c).

Every catalog model that is off the GPU is kept ready in host RAM so a swap never reads model files from disk.
Engines without a sleep mode get their weight file copied once into a RAM-backed directory (``/dev/shm``), verified
against the pinned SHA-256, and memory-mapped from there on each load. ``mlock`` is not used (the host's
locked-memory limit is far below a model's size); residency is checked with ``mincore`` before each load instead.

When the RAM budget or the host reserve does not allow a warm copy, :meth:`RamStage.decide` answers ``cold`` and
records an infrastructure finding; the caller then loads from disk and still answers correctly (FR-031).
Findings hold metadata only.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import json
import os
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

GIB = 1024**3
CHUNK = 8 * 1024 * 1024
SIDECAR = "staged.json"
_NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class RamStageError(RuntimeError):
    """Staging failure; the message is a machine reason such as ``SHA256_MISMATCH:...`` or ``BAD_NAME:...``."""


@dataclass(frozen=True)
class Staged:
    name: str
    path: Path
    sha256: str
    size: int
    inode: int


def residency(path: Path) -> float:
    """Fraction of the file's pages resident in RAM (``mmap`` + ``mincore`` through libc); 0.0 on any error."""
    try:
        size = path.stat().st_size
        if size == 0:
            return 1.0
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        libc.mmap.restype = ctypes.c_void_p
        libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
        libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
        page = os.sysconf("SC_PAGE_SIZE")
        pages = (size + page - 1) // page
        fd = os.open(path, os.O_RDONLY)
        try:
            addr = libc.mmap(None, size, 0x1, 0x1, fd, 0)  # PROT_READ, MAP_SHARED
        finally:
            os.close(fd)
        if addr is None or addr == ctypes.c_void_p(-1).value:
            return 0.0
        try:
            vec = (ctypes.c_ubyte * pages)()
            if libc.mincore(addr, size, vec) != 0:
                return 0.0
            resident = bytes(vec).translate(bytes(i & 1 for i in range(256))).count(1)
        finally:
            libc.munmap(addr, size)
        return resident / pages
    except Exception:  # noqa: BLE001 - any failure means "not known resident"
        return 0.0


_default_residency = residency


def mem_available_gib(meminfo: Path) -> float:
    for line in meminfo.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024 / GIB
    raise ValueError("MemAvailable missing")


class RamStage:
    """Warm copies of model files in a RAM-backed directory, accounted against a budget (FR-031)."""

    def __init__(self, stage_dir: Path, budget_gib: float, reserve_gib: float, meminfo: Path = Path("/proc/meminfo"),
                 residency: Callable[[Path], float] | None = None):
        self.stage_dir = Path(stage_dir)
        self.budget_gib = float(budget_gib)
        self.reserve_gib = float(reserve_gib)
        self.meminfo = Path(meminfo)
        self._residency = residency or _default_residency
        self._staged: dict[str, Staged] = {}
        self._reserved: dict[str, float] = {}
        self._findings: list[dict] = []
        self._load_existing()

    # -- accounting ---------------------------------------------------------------------------------------------
    def used_gib(self) -> float:
        return sum(s.size for s in self._staged.values()) / GIB + sum(self._reserved.values())

    def reserve(self, name: str, gib: float) -> None:
        """Count RAM held by a warm copy not managed as a file here (e.g. sleeping engine weights) against the budget."""
        self._check_name(name)
        self._reserved[name] = float(gib)

    def release(self, name: str) -> None:
        self._reserved.pop(name, None)

    def decide(self, need_gib: float) -> tuple[str, str]:
        """``('warm', '')`` only if ``need_gib`` fits the remaining budget and leaves the host reserve free; else cold."""
        free_budget = self.budget_gib - self.used_gib()
        if need_gib > free_budget:
            return self._cold(f"RAM_BUDGET:need={need_gib:.1f},free={free_budget:.1f}", need_gib)
        try:
            avail = mem_available_gib(self.meminfo)
        except (OSError, ValueError):
            return self._cold("MEMINFO_UNREADABLE", need_gib)
        if avail - need_gib < self.reserve_gib:
            return self._cold(f"RAM_RESERVE:available={avail:.1f},need={need_gib:.1f},reserve={self.reserve_gib:.1f}", need_gib)
        return "warm", ""

    def _cold(self, reason: str, need_gib: float) -> tuple[str, str]:
        self._finding("RAM_WARM_UNAVAILABLE", reason, need_gib=round(need_gib, 3))
        return "cold", reason

    # -- staging ------------------------------------------------------------------------------------------------
    def stage(self, name: str, src: Path, sha256: str) -> Staged:
        """Copy ``src`` to ``stage_dir/<name>/<src.name>`` via a ``.part`` file, hashing while copying.

        A digest mismatch deletes the copy and raises ``SHA256_MISMATCH``. Idempotent when the same file is already
        staged with the recorded size and digest. The caller decides first (:meth:`decide`); staging does not.
        """
        self._check_name(name)
        src = Path(src)
        want = sha256.lower()
        size = src.stat().st_size
        d = self._name_dir(name)
        dest = d / src.name
        side = self._read_sidecar(name)
        if side and side.get("sha256") == want and side.get("size") == size and side.get("file") == src.name:
            try:
                st = dest.stat()
            except OSError:
                st = None
            if st is not None and st.st_size == size:
                staged = Staged(name, dest, want, size, st.st_ino)
                self._staged[name] = staged
                return staged
        self._ensure_dir(self.stage_dir)
        self._ensure_dir(d)
        part = d / (src.name + ".part")
        part.unlink(missing_ok=True)
        h = hashlib.sha256()
        fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as out, src.open("rb") as inp:
                while chunk := inp.read(CHUNK):
                    h.update(chunk)
                    out.write(chunk)
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        got = h.hexdigest()
        if got != want:
            part.unlink(missing_ok=True)
            self._finding("STAGE_REFUSED", f"SHA256_MISMATCH:{name}", want=want[:16], got=got[:16])
            raise RamStageError(f"SHA256_MISMATCH:{name}:want={want[:16]},got={got[:16]}")
        os.chmod(part, 0o600)
        os.replace(part, dest)
        self._write_sidecar(name, {"name": name, "file": src.name, "sha256": want, "size": size})
        staged = Staged(name, dest, want, size, dest.stat().st_ino)
        self._staged[name] = staged
        return staged

    def check(self, staged: Staged, min_residency: float = 0.95) -> tuple[bool, str]:
        """Before a load: size and inode unchanged and at least ``min_residency`` of the pages in RAM."""
        try:
            st = staged.path.stat()
        except OSError:
            return self._not_ok(staged, "MISSING")
        if st.st_size != staged.size or st.st_ino != staged.inode:
            return self._not_ok(staged, "CHANGED")
        frac = self._residency(staged.path)
        if frac < min_residency:
            return self._not_ok(staged, f"NOT_RESIDENT:{frac:.3f}")
        return True, ""

    def _not_ok(self, staged: Staged, reason: str) -> tuple[bool, str]:
        self._finding("STAGED_COPY_NOT_READY", reason, name=staged.name)
        return False, reason

    def unstage(self, name: str) -> None:
        """Remove only ``stage_dir/<name>``; names that resolve elsewhere are refused."""
        self._check_name(name)
        d = self._name_dir(name)
        if d.exists():
            shutil.rmtree(d)
        self._staged.pop(name, None)

    def staged(self) -> dict[str, Staged]:
        return dict(self._staged)

    def findings(self) -> list[dict]:
        """Infrastructure findings recorded by decide/stage/check (metadata only)."""
        return list(self._findings)

    # -- helpers ------------------------------------------------------------------------------------------------
    def _finding(self, code: str, reason: str, **meta) -> None:
        self._findings.append({"ts": time.time(), "kind": "infrastructure", "code": code, "reason": reason, **meta})

    @staticmethod
    def _check_name(name: str) -> None:
        if not isinstance(name, str) or not _NAME.match(name) or name in (".", ".."):
            raise RamStageError(f"BAD_NAME:{name!r}")

    def _name_dir(self, name: str) -> Path:
        """``stage_dir/<name>``; the name pattern forbids separators and a symlinked entry is refused."""
        d = self.stage_dir / name
        if d.is_symlink():
            raise RamStageError(f"BAD_NAME:{name!r}")
        return d

    @staticmethod
    def _ensure_dir(d: Path) -> None:
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(d, 0o700)

    def _read_sidecar(self, name: str) -> dict | None:
        try:
            return json.loads((self._name_dir(name) / SIDECAR).read_text())
        except (OSError, ValueError):
            return None

    def _write_sidecar(self, name: str, data: dict) -> None:
        p = self._name_dir(name) / SIDECAR
        fd = os.open(p.with_suffix(".tmp"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(p.with_suffix(".tmp"), p)

    def _load_existing(self) -> None:
        """Re-account copies that survived a restart (tmpfs outlives the process) and still match their sidecar."""
        if not self.stage_dir.is_dir():
            return
        for d in sorted(self.stage_dir.iterdir()):
            if d.is_symlink() or not d.is_dir() or not _NAME.match(d.name):
                continue
            side = self._read_sidecar(d.name)
            if not side or not isinstance(side.get("file"), str):
                continue
            f = d / side["file"]
            try:
                st = f.stat()
            except OSError:
                continue
            if st.st_size == side.get("size"):
                self._staged[d.name] = Staged(d.name, f, str(side.get("sha256", "")), st.st_size, st.st_ino)
