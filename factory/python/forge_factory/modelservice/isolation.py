"""In-boundary isolation checker of the factory machine (feature 017, User Story 5, FR-021, research R9).

Runs INSIDE the factory machine (VM, or the container stand-in until the `kvm` group is granted) and proves from there
that the only route to the model is the model channel:

- ``boundary_present``: the checker runs inside a VM or container, not on the model-tier host itself.
- ``gpu_device_absent``: no ``/dev/nvidia*`` device, no ``/proc/driver/nvidia``, no ``nvidia-smi`` on PATH.
- ``host_model_paths_absent``: none of the host's model stores (weights, RAM stage, Ollama models) is visible.
- ``only_model_channel_reachable``: every TCP attempt to a host service port fails (and is recorded); the model channel
  answers HTTP (any status, 401 included: reachability, not authorisation, is checked here).

A container stand-in report also lists ``standin_limitations``: the production properties a container does not prove.
Every probe is injectable (``Probes``) so the checker is unit-tested without a GPU, a container or a network.

CLI: ``python -m forge_factory.modelservice.isolation --channel URL --out report.json`` exits 0 only if all checks pass.
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import os
import shutil
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "forge-c/017/isolation-report"

# Host services that must NOT be reachable from inside the boundary: Ollama/legacy model ports, the Fabro monitor and
# factory floor dashboards, the Fabro API, ssh, and the model-tier engine port (which would bypass the tenant gateway).
DEFAULT_FORBIDDEN_PORTS: tuple[int, ...] = (11455, 11456, 11457, 11460, 8787, 8788, 32397, 22, 18502)

# Host model stores (Omniverse2 layout); none may be visible inside the factory machine.
DEFAULT_HOST_MODEL_PATHS: tuple[str, ...] = (
    "/mnt/data/forge-c/model-service/models",
    "/mnt/data/forge-c/model-service/images",
    "/dev/shm/forge-model-tier",
    "/mnt/data/forge-c/ollama-models",
    "/usr/share/ollama/.ollama/models",
)

# Hosts a factory machine could use to reach the model-tier host besides the channel: the Docker bridge gateway, the
# Docker Desktop alias and the qemu user-mode host address. The default IPv4 gateway and the channel host are added.
DEFAULT_PROBE_HOSTS: tuple[str, ...] = ("172.17.0.1", "host.docker.internal", "10.0.2.2")

GPU_DEVICE_GLOBS: tuple[str, ...] = ("/dev/nvidia*", "/dev/nvidia-caps/*")
GPU_DRIVER_PATHS: tuple[str, ...] = ("/proc/driver/nvidia",)
GPU_TOOLS: tuple[str, ...] = ("nvidia-smi",)

# What a container stand-in does not prove about the production VM (research R9, FR-021).
CONTAINER_LIMITATIONS: tuple[str, ...] = (
    "separate kernel: a container shares the model-tier host's kernel; a VM boots its own",
    "VM network stack: a container uses a Docker bridge on the host's network stack, not a virtual NIC behind a hypervisor",
    "VM memory limits: cgroup memory limits are not the fixed guest RAM of a VM",
    "boot from production image: the container is built from ubuntu:22.04, not booted from the Ubuntu 22.04.5 VM image",
)

CONTAINER_CGROUP_MARKERS: tuple[str, ...] = ("docker", "containerd", "kubepods", "libpod", "lxc")
VM_DMI_MARKERS: tuple[str, ...] = ("qemu", "kvm", "vmware", "virtualbox", "hyper-v", "microsoft corporation", "xen", "bochs")


def _tcp_connect(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolve(host: str) -> str | None:
    try:
        return socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)[0][4][0]
    except (OSError, IndexError, UnicodeError):
        return None


def _http_status(url: str, timeout: float) -> int | None:
    """Any HTTP status means the channel answered; None means no HTTP answer (refused, reset, timeout, garbage)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as r:  # noqa: S310 (configured channel)
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except (OSError, ValueError, urllib.error.URLError):
        return None


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return None


@dataclass
class Probes:
    """Every observation the checker makes; tests replace these with fakes."""

    exists: Callable[[str], bool] = os.path.exists
    glob: Callable[[str], list[str]] = _glob.glob
    which: Callable[[str], str | None] = shutil.which
    read_text: Callable[[str], str | None] = _read_text
    resolve: Callable[[str], str | None] = _resolve
    tcp_connect: Callable[[str, int, float], bool] = _tcp_connect
    http_status: Callable[[str, float], int | None] = _http_status


@dataclass
class Env:
    channel_url: str
    forbidden_ports: Sequence[int] = DEFAULT_FORBIDDEN_PORTS
    host_model_paths: Sequence[str] = DEFAULT_HOST_MODEL_PATHS
    probe_hosts: Sequence[str] = DEFAULT_PROBE_HOSTS
    timeout_s: float = 1.0
    boundary_override: str | None = None  # "vm" | "container" | "host"; None = detect
    probes: Probes = field(default_factory=Probes)


def default_gateway(read_text: Callable[[str], str | None]) -> str | None:
    """IPv4 default gateway from /proc/net/route (little-endian hex), or None."""
    text = read_text("/proc/net/route") or ""
    for line in text.splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 3 and cols[1] == "00000000":
            try:
                return socket.inet_ntoa(int(cols[2], 16).to_bytes(4, "little"))
            except (ValueError, OverflowError):
                return None
    return None


def detect_boundary(probes: Probes) -> tuple[str, list[str]]:
    """(kind, evidence): container before vm (a container inside a VM is still a container boundary)."""
    evidence: list[str] = []
    if probes.exists("/.dockerenv"):
        evidence.append("/.dockerenv present")
    if probes.exists("/run/.containerenv"):
        evidence.append("/run/.containerenv present")
    cg = (probes.read_text("/proc/1/cgroup") or "").lower()
    hits = [m for m in CONTAINER_CGROUP_MARKERS if m in cg]
    if hits:
        evidence.append(f"/proc/1/cgroup mentions {','.join(hits)}")
    if evidence:
        return "container", evidence
    for p in ("/sys/class/dmi/id/sys_vendor", "/sys/class/dmi/id/product_name"):
        v = (probes.read_text(p) or "").strip()
        if v and any(m in v.lower() for m in VM_DMI_MARKERS):
            evidence.append(f"{p}={v}")
    flags = next((ln for ln in (probes.read_text("/proc/cpuinfo") or "").splitlines() if ln.startswith("flags")), "")
    if "hypervisor" in flags.split(":", 1)[-1].split():
        evidence.append("cpu flag hypervisor")
    if evidence:
        return "vm", evidence
    return "host", ["no container marker, no hypervisor marker"]


def _channel_endpoint(url: str) -> tuple[str, int]:
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError(f"model channel URL must be http(s)://host[:port]/...: {url!r}")
    return u.hostname, u.port or (443 if u.scheme == "https" else 80)


def _check(cid: str, reasons: list[str], observed: dict) -> dict:
    return {"id": cid, "status": "FAIL" if reasons else "PASS", "reasons": reasons, "observed": observed}


def _gpu(p: Probes) -> dict:
    devices = sorted({d for g in GPU_DEVICE_GLOBS for d in p.glob(g)})
    drivers = [d for d in GPU_DRIVER_PATHS if p.exists(d)]
    tools = {t: w for t in GPU_TOOLS if (w := p.which(t))}
    reasons = [f"GPU device visible: {d}" for d in devices]
    reasons += [f"GPU driver interface visible: {d}" for d in drivers]
    reasons += [f"GPU tool installed: {t} at {w}" for t, w in tools.items()]
    return _check("gpu_device_absent", reasons, {"devices": devices, "drivers": drivers, "tools": tools})


def _model_paths(p: Probes, paths: Sequence[str]) -> dict:
    visible = [x for x in paths if p.exists(x)]
    return _check("host_model_paths_absent", [f"host model path visible: {x}" for x in visible],
                  {"checked": list(paths), "visible": visible})


def _reachability(env: Env) -> tuple[dict, list[dict]]:
    p = env.probes
    ch_host, ch_port = _channel_endpoint(env.channel_url)
    hosts: list[str] = [ch_host]
    gw = default_gateway(p.read_text)
    for h in ([gw] if gw else []) + list(env.probe_hosts):
        if h not in hosts:
            hosts.append(h)
    ports = list(dict.fromkeys(int(x) for x in env.forbidden_ports))
    attempts: list[dict] = []
    reasons: list[str] = []
    unresolved: list[str] = []
    for h in hosts:
        if h != ch_host and p.resolve(h) is None:
            unresolved.append(h)
            continue
        # On any host other than the channel's, the channel port itself is a second route to the model: forbidden.
        for port in ports + ([ch_port] if h != ch_host and ch_port not in ports else []):
            if h == ch_host and port == ch_port:
                continue
            ok = p.tcp_connect(h, port, env.timeout_s)
            attempts.append({"host": h, "port": port, "expected": "unreachable", "reachable": ok,
                             "result": "VIOLATION" if ok else "blocked"})
            if ok:
                reasons.append(f"host service reachable: {h}:{port}")
    probe_url = env.channel_url.rstrip("/") + "/models"
    status = p.http_status(probe_url, max(env.timeout_s, 3.0))
    attempts.append({"host": ch_host, "port": ch_port, "expected": "reachable", "reachable": status is not None,
                     "http_status": status, "result": "ok" if status is not None else "VIOLATION"})
    if status is None:
        reasons.append(f"model channel not reachable: {probe_url}")
    observed = {"channel": {"host": ch_host, "port": ch_port, "http_status": status}, "hosts": hosts,
                "unresolved_hosts": unresolved, "ports": ports}
    return _check("only_model_channel_reachable", reasons, observed), attempts


def check(env: Env) -> dict:
    """Run every isolation check inside the boundary and return the report (status PASS only if all checks pass)."""
    p = env.probes
    if env.boundary_override:
        kind, evidence = env.boundary_override, [f"override: {env.boundary_override}"]
    else:
        kind, evidence = detect_boundary(p)
    if kind not in ("vm", "container", "host"):
        raise ValueError(f"boundary kind must be vm|container|host, not {kind!r}")
    no_boundary = ["running on the host: no machine boundary between the factory and the model tier"]
    boundary = _check("boundary_present", no_boundary if kind == "host" else [], {"kind": kind, "evidence": evidence})
    reach, attempts = _reachability(env)
    checks = [boundary, _gpu(p), _model_paths(p, env.host_model_paths), reach]
    failed = [c for c in checks if c["status"] != "PASS"]
    return {
        "schema": SCHEMA,
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "boundary": {"kind": kind, "evidence": evidence},
        "channel_url": env.channel_url,
        "checks": checks,
        "attempts": attempts,
        "standin_limitations": list(CONTAINER_LIMITATIONS) if kind == "container" else [],
        "status": "FAIL" if failed else "PASS",
        "open_issues": sum(len(c["reasons"]) for c in failed),
    }


def write_report(report: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, out)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m forge_factory.modelservice.isolation", description=__doc__.splitlines()[0])
    ap.add_argument("--channel", required=True, help="model channel base URL as seen from inside, e.g. http://127.0.0.1:18480/v1")
    ap.add_argument("--out", required=True, type=Path, help="report JSON path")
    ap.add_argument("--port", type=int, action="append", help="forbidden host port (repeatable; replaces the default list)")
    ap.add_argument("--host", action="append", help="extra host to probe (repeatable; added to the defaults)")
    ap.add_argument("--model-path", action="append", help="extra host model path that must be invisible (repeatable)")
    ap.add_argument("--timeout", type=float, default=1.0, help="per-attempt TCP timeout in seconds")
    ap.add_argument("--boundary", choices=("vm", "container", "host"), help="override boundary detection")
    a = ap.parse_args(argv)
    env = Env(channel_url=a.channel, forbidden_ports=tuple(a.port) if a.port else DEFAULT_FORBIDDEN_PORTS,
              host_model_paths=DEFAULT_HOST_MODEL_PATHS + tuple(a.model_path or ()),
              probe_hosts=DEFAULT_PROBE_HOSTS + tuple(a.host or ()), timeout_s=a.timeout, boundary_override=a.boundary,
              probes=Probes())
    try:
        report = check(env)
    except ValueError as e:
        print(f"isolation ERROR {e}", file=sys.stderr)
        return 2
    write_report(report, a.out)
    print(f"isolation {report['status']} boundary={report['boundary']['kind']} open_issues:{report['open_issues']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
