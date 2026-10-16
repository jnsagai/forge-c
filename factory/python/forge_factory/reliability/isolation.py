"""CRE-T049 (owner choice 2026-10-16: option 2, storage on loop10) — separate OS identities without admin rights.

Rootless Podman (user namespaces + the owner's subordinate UIDs 100000-165535) runs the CRE verification runner and
repair-candidate code as DIFFERENT host UIDs from the production account:
  production (Fabro, agents, MCP tools)  -> the owner account (uid 1000)
  verifier   (reproducers, benchmarks, promotion quality gate) -> container uid 2001 = host uid 102000
  repair     (candidate code under evaluation)                    -> container uid 2002 = host uid 102001
Kernel-enforced: the host filesystem is visible READ-ONLY (only the toolchain/repo/data-root paths it needs are
bind-mounted), /tmp is private, the only writable place is a per-run scratch directory owned by the sandbox UID,
the network is off for the verifier, HOME is empty, and the owner's 0600 credentials (dashboard tokens, Fabro dev
token, vault env) are unreadable because the sandbox UID is not their owner.
All Podman storage, the stub root filesystem, worktrees and scratch live on the loop10 data volume.

Limits (recorded, not hidden): the production account is still the owner account (moving Fabro itself into a
separate identity needs root or a full container image); membership of the owner in the `docker` group remains a
root-equivalent path outside this sandbox.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from ..common import REPO_ROOT, data_root

ROLES = {"verifier": 2001, "repair": 2002}
SHORT = Path.home() / ".forge-podman"  # podman limits runroot paths to 50 chars: short symlink -> loop10
MODE_ENV = "FORGE_CRE_ISOLATION"  # podman (default when available) | none


def base() -> Path:
    return data_root() / "podman"


def _podman() -> list[str]:
    return ["podman", "--root", str(SHORT / "root"), "--runroot", str(SHORT / "run")]


def available() -> bool:
    if os.environ.get(MODE_ENV, "podman") == "none" or not shutil.which("podman"):
        return False
    return True


def setup() -> Path:
    b = base()
    for d in ("root", "run", "scratch", "work", "rootfs/usr", "rootfs/etc", "rootfs/tmp", "rootfs/home", "rootfs/media"):
        (b / d).mkdir(parents=True, exist_ok=True)
    for name, target in (("bin", "usr/bin"), ("lib", "usr/lib"), ("lib64", "usr/lib64"), ("sbin", "usr/sbin")):
        link = b / "rootfs" / name
        if not link.is_symlink():
            link.symlink_to(target)
    if SHORT.is_symlink() and SHORT.resolve() != b.resolve():
        SHORT.unlink()
    if not SHORT.exists():
        SHORT.symlink_to(b)
    return b


def work_dir(prefix: str) -> Path:
    """Per-run working directory on loop10 (worktrees, scratch)."""
    d = setup() / "work" / f"{prefix}-{uuid.uuid4().hex[:10]}"
    d.mkdir(parents=True)
    return d


def scratch(role: str) -> Path:
    """A writable directory owned by the role's host UID (via the user namespace)."""
    d = setup() / "scratch" / f"{role}-{uuid.uuid4().hex[:10]}"
    d.mkdir(parents=True)
    uid = ROLES[role]
    subprocess.run([*_podman(), "unshare", "chown", f"{uid}:{uid}", str(d)], check=True, capture_output=True, timeout=60)
    return d


def remove(path: Path) -> None:
    """Scratch files belong to a sub-UID: remove them inside the user namespace."""
    if path.exists():
        subprocess.run([*_podman(), "unshare", "rm", "-rf", str(path)], capture_output=True, timeout=120)


def _ro_roots() -> list[str]:
    paths = {"/usr", "/etc", str(REPO_ROOT), str(data_root())}
    pyenv = Path.home() / ".pyenv"
    if pyenv.is_dir():
        paths.add(str(pyenv))
    return sorted(paths)


def read_only_mounts() -> list[str]:
    out = []
    for p in _ro_roots():
        out += ["-v", f"{p}:{p}:ro"]
    return out


def argv(role: str, cmd: list[str], *, cwd: Path, env: dict[str, str], writable: list[Path], ro_extra: list[Path] = (),
         network: bool = False) -> list[str]:
    """The podman command that runs `cmd` as the role's UID; paths keep their host names inside."""
    uid = ROLES[role]
    a = [*_podman(), "run", "--rm", "--user", f"{uid}:{uid}", "--tmpfs", "/tmp:rw,size=2g,mode=1777",
         "--security-opt", "label=disable", "-w", str(cwd)]
    if not network:
        a += ["--network", "none"]
    a += read_only_mounts()
    for p in ro_extra:
        if not any(str(p).startswith(m + "/") or str(p) == m for m in _ro_roots()):
            a += ["-v", f"{p}:{p}:ro"]
    for p in writable:
        a += ["-v", f"{p}:{p}:rw"]
    keep = {k: v for k, v in env.items() if not k.endswith(("TOKEN", "KEY", "SECRET", "PASSWORD"))}
    for k, v in sorted(keep.items()):
        a += ["-e", f"{k}={v}"]
    a += ["--rootfs", str(base() / "rootfs"), *cmd]
    return a


def run(role: str, cmd: list[str], *, cwd: Path, env: dict[str, str], writable: list[Path],
        ro_extra: list[Path] = (), network: bool = False, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(argv(role, cmd, cwd=cwd, env=env, writable=writable, ro_extra=ro_extra, network=network),
                          capture_output=True, timeout=timeout)


def new_dir(prefix: str) -> Path:
    """Scratch/worktree root: on loop10 (visible to the sandbox) when isolating, else a normal temp dir."""
    return work_dir(prefix) if available() else Path(tempfile.mkdtemp(prefix=f"{prefix}-"))


def hand_over(role: str, d: Path) -> None:
    """After the owner has populated `d`, give it to the role's sub-UID (owner loses write access to it)."""
    if available():
        uid = ROLES[role]
        subprocess.run([*_podman(), "unshare", "chown", "-R", f"{uid}:{uid}", str(d)], check=True,
                       capture_output=True, timeout=120)


def discard(d: Path) -> None:
    if available():
        remove(d)
    else:
        shutil.rmtree(d, ignore_errors=True)


def execute(role: str, cmd: list[str], *, cwd: Path, env: dict[str, str], writable: list[Path],
            readable: list[Path] = (), timeout: int = 1800) -> subprocess.CompletedProcess:
    """Run `cmd` as the role's OS identity when the sandbox is available, otherwise as a plain subprocess."""
    if not available():
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    env = {**env, "HOME": str(writable[0]) if writable else "/tmp"}
    return run(role, cmd, cwd=cwd, env=env, writable=writable, ro_extra=list(readable), timeout=timeout)


def level() -> str:
    return "podman-rootless-subuid" if available() else "none (same OS user)"
