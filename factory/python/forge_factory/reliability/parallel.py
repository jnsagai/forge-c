"""Bounded CPU-only verification capacity; model calls and dependent SWE phases are never parallelized here."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAX_JOBS = 16
CPU_RESERVE = 8
MEMORY_RESERVE_MB = 16384
MEMORY_PER_JOB_MB = 4096


def memory_available_mb() -> int:
    try:
        with open("/proc/meminfo") as f:
            available = next(int(x.split()[1]) // 1024 for x in f if x.startswith("MemAvailable:"))
        group = next(x.split(":", 2)[2].strip() for x in Path("/proc/self/cgroup").read_text().splitlines()
                     if x.startswith("0::"))
        root = Path("/sys/fs/cgroup") / group.lstrip("/")
        limit = (root / "memory.max").read_text().strip()
        if limit != "max":
            remaining = max(0, int(limit) - int((root / "memory.current").read_text())) // (1024 * 1024)
            available = min(available, remaining)
        return available
    except (OSError, StopIteration, ValueError):
        return MEMORY_RESERVE_MB + MEMORY_PER_JOB_MB


def capacity(requested: int | None = None, *, cpus: int | None = None, available_mb: int | None = None) -> int:
    requested = int(os.environ.get("FORGE_CPU_JOBS", "1")) if requested is None else requested
    if requested < 1:
        raise ValueError("FORGE_CPU_JOBS_MUST_BE_POSITIVE")
    if cpus is None:
        cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 1
    if available_mb is None:
        available_mb = memory_available_mb()  # unknown capacity never opens more concurrency
    return max(1, min(requested, MAX_JOBS, max(1, cpus - CPU_RESERVE),
                      max(1, (available_mb - MEMORY_RESERVE_MB) // MEMORY_PER_JOB_MB)))


def ordered_map(fn, items, *, jobs: int | None = None):
    """Every case runs unchanged in its own existing sandbox; deterministic input/result order is retained."""
    items = list(items)
    workers = min(capacity(jobs), len(items)) if items else 1
    if workers == 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="forge-cpu-verifier") as pool:
        # executor.map preserves input order and propagates exceptions; the context waits before source cleanup.
        return list(pool.map(fn, items))
