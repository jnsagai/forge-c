"""Narrow read-only host-kernel view for the trusted existing provider namespace.

Only the guardian's stat/uid_map and original socket inode are bound. This
is not a host /proc mount or a privileged proxy. Untrusted SDK test sandboxes do
not receive these mounts. The existing serving-instance record pins the view.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from .durable import Refused, digest


def _fail(code):
    raise Refused("OWNER_DEVELOPMENT_VIEW_" + code)


def prepare(root, record):
    """Called only at the existing trusted provider creation effect boundary."""
    from .owner_supervised_development import guardian_alive

    if not guardian_alive(record) or not shutil.which("bwrap"):
        _fail("HOST_GUARDIAN_UNPROVEN")
    root = Path(root).resolve()
    if root != Path(record["store_path"]).parents[2]:
        _fail("CANONICAL_ROOT_CHANGED")
    folder = root / "run/owner-development-views" / digest(record)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.is_symlink() or folder.stat().st_uid != os.getuid() or folder.stat().st_mode & 0o077:
        _fail("MOUNTPOINT_DIRECTORY_CHANGED")
    expected_names = {"stat", "uid_map", "socket"}
    if any(
        p.name not in expected_names
        or p.is_symlink()
        or not p.is_file()
        or p.stat().st_size != 0
        or p.stat().st_uid != os.getuid()
        for p in folder.iterdir()
    ):
        _fail("MOUNTPOINT_CONTENT_CHANGED")
    files = {name: str(folder / name) for name in ("stat", "uid_map", "socket")}
    pid = record["guardian_pid"]
    sources = dict(
        stat=f"/proc/{pid}/stat",
        uid_map=f"/proc/{pid}/uid_map",
        socket=record["guardian_socket"],
    )
    args = [
        shutil.which("bwrap"),
        "--bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--unshare-user",
        "--unshare-pid",
        "--as-pid-1",
        "--new-session",
        # No --die-with-parent: the line launcher starts this from a short-lived
        # `stack start` process. Retirement is by exact instance, as without a view.
    ]
    handles = []
    try:
        for name, target in files.items():
            flags = os.O_PATH if name == "socket" else os.O_RDONLY
            fd = os.open(sources[name], flags | os.O_CLOEXEC)
            handles.append(fd)
            if name == "socket":
                st = os.fstat(fd)
                if dict(device=st.st_dev, inode=st.st_ino) != record["guardian_socket_identity"]:
                    _fail("SOCKET_NODE_REBOUND")
            args += ["--ro-bind-fd", str(fd), target]
    except BaseException:
        close_handles(handles)
        raise
    view = dict(
        schema="forge-c/owner-development-kernel-view/1",
        record_sha256=digest(record),
        root=str(root),
        files=files,
        socket_identity=record["guardian_socket_identity"],
        store_path=record["store_path"],
        store_identity=record["store_identity"],
    )
    return args + ["--proc", "/proc", "--", "sleep", "infinity"], view, tuple(handles)


def close_handles(handles):
    for fd in handles:
        os.close(fd)


def _mount(path):
    def unescape(value):
        return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)

    matches = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        head, tail = line.split(" - ", 1)
        a = head.split()
        b = tail.split()
        if unescape(a[4]) == str(path):
            matches.append(dict(root=unescape(a[3]), options=a[5].split(","), filesystem=b[0]))
    if len(matches) != 1 or "ro" not in matches[0]["options"]:
        _fail("READONLY_KERNEL_MOUNT_REQUIRED")
    return matches[0]


def verify_mounted(record, view, instance, store):
    """Validate actual mounts/process facts; caller data never invents kernel identity."""
    from ..lrtx.provider_process import boot_id

    root = Path(record["store_path"]).parents[2]
    expected = root / "run/owner-development-views" / digest(record)
    files = {name: str(expected / name) for name in ("stat", "uid_map", "socket")}
    if (
        view
        != dict(
            schema="forge-c/owner-development-kernel-view/1",
            record_sha256=digest(record),
            root=str(root),
            files=files,
            socket_identity=record["guardian_socket_identity"],
            store_path=record["store_path"],
            store_identity=record["store_identity"],
        )
        or instance["root"] != str(root)
        or instance["profile"] != record["profile"]
        or instance["profile_sha256"] != record["profile_sha256"]
        or instance["init"]["pid_namespace"] != os.readlink("/proc/self/ns/pid")
        or instance["init_owner_view"]["user_namespace"] != os.readlink("/proc/self/ns/user")
        or Path(store.path).resolve() != Path(record["store_path"])
    ):
        _fail("INSTANCE_OR_STORE_CHANGED")
    for name in ("stat", "uid_map"):
        mount = _mount(files[name])
        if mount["filesystem"] != "proc" or mount["root"] != f"/{record['guardian_pid']}/{name}":
            _fail("PROC_IDENTITY_CHANGED")
    _mount(files["socket"])
    st = Path(files["socket"]).stat()
    if dict(device=st.st_dev, inode=st.st_ino) != record["guardian_socket_identity"]:
        _fail("SOCKET_NODE_REBOUND")
    # procfs translates IDs for the opening observer: an ancestor task PID
    # outside this PID namespace renders0; initial outside UID0 may render the
    # invalid-UID sentinel. Exact proc mount roots still pin the original PID,
    # and only the kernel's entire valid UID extent (not a child count1 map)
    # is accepted. The current userns is pinned to this provider above.
    raw = Path(files["stat"]).read_text()
    fields = raw[raw.rfind(")") + 2 :].split()
    if (
        int(raw.split("(", 1)[0].strip()) not in (0, record["guardian_pid"])
        or fields[0] == "Z"
        or fields[19] != record["guardian"]["start_ticks"]
        or boot_id() != record["guardian"]["boot_id"]
        or [list(map(int, line.split())) for line in Path(files["uid_map"]).read_text().splitlines()]
        not in ([[0, 0, 4294967295]], [[0, 4294967295, 4294967295]])
    ):
        _fail("HOST_GUARDIAN_NOT_LIVE")
    return files["socket"]


def current(record, store):
    from .provider_recovery import current_instance

    instance = current_instance()
    if not instance or not isinstance(instance.get("owner_development_view"), dict):
        _fail("TRUSTED_PROVIDER_VIEW_REQUIRED")
    return verify_mounted(record, instance["owner_development_view"], instance, store)
