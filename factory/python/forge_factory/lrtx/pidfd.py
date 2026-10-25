"""pidfd system calls with a raw-syscall fallback.

Some CPython builds omit os.pidfd_open / signal.pidfd_send_signal although the kernel
supports them (2026-10-25: the uv-managed CPython 3.13.13 on omniverse2, glibc 2.35,
kernel 6.8). Signalling through a pidfd is what keeps a reused PID from being signalled;
the fallback issues the same system calls and never degrades to os.kill(pid).
"""

from __future__ import annotations

import ctypes
import os
import platform
import signal

# Unified syscall numbers (identical on x86_64 and aarch64): pidfd_send_signal 424, pidfd_open 434.
_NUMBERS = {"x86_64": (434, 424), "aarch64": (434, 424), "arm64": (434, 424)}


def _syscall(index: int, *args) -> int:
    numbers = _NUMBERS.get(platform.machine())
    if numbers is None:
        raise OSError(38, "pidfd system call unavailable on " + platform.machine())  # ENOSYS
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    result = libc.syscall(ctypes.c_long(numbers[index]), *args)
    if result < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))  # ESRCH becomes ProcessLookupError
    return int(result)


def open_pid(pid: int) -> int:
    if hasattr(os, "pidfd_open"):
        return os.pidfd_open(pid)
    return _syscall(0, ctypes.c_int(pid), ctypes.c_uint(0))


def send_signal(descriptor: int, sig: int) -> None:
    if hasattr(signal, "pidfd_send_signal"):
        signal.pidfd_send_signal(descriptor, sig)
        return
    _syscall(1, ctypes.c_int(descriptor), ctypes.c_int(int(sig)), ctypes.c_void_p(None), ctypes.c_uint(0))
