"""Read-only GPU probe (feature 017, T013). Factory-agnostic: it reports processes, memory and cgroups, nothing else.

Processes are told apart by cgroup and network namespace, never by port (two lanes on Omniverse2 use the same
port in different namespaces)."""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

Runner = Callable[..., subprocess.CompletedProcess]


def _smi(args: list[str], run: Runner) -> list[list[str]]:
    r = run(["nvidia-smi", *args, "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=20, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"NVIDIA_SMI_FAILED:{r.returncode}")
    return [[c.strip() for c in line.split(",")] for line in r.stdout.splitlines() if line.strip()]


def cgroup_of(pid: int, proc: Path = Path("/proc")) -> str:
    try:
        lines = (proc / str(pid) / "cgroup").read_text().splitlines()
    except OSError:
        return ""
    return next((line.split(":", 2)[2] for line in lines if line.startswith("0::")), lines[0].split(":", 2)[-1] if lines else "")


def netns_of(pid: int, proc: Path = Path("/proc")) -> str:
    try:
        return (proc / str(pid) / "ns/net").readlink().as_posix()
    except OSError:
        return ""


def compute_apps(run: Runner = subprocess.run, proc: Path = Path("/proc")) -> list[dict]:
    """Every process holding GPU memory: pid, used MiB, cgroup and network namespace."""
    out = []
    for row in _smi(["--query-compute-apps=pid,used_memory"], run):
        if len(row) < 2 or not row[0].isdigit():
            continue
        pid = int(row[0])
        out.append({"pid": pid, "used_mib": int(row[1]) if row[1].isdigit() else None,
                    "cgroup": cgroup_of(pid, proc), "netns": netns_of(pid, proc)})
    return out


def memory_mib(run: Runner = subprocess.run) -> dict:
    total, used, free = (int(x) for x in _smi(["--query-gpu=memory.total,memory.used,memory.free"], run)[0][:3])
    return {"total": total, "used": used, "free": free}
