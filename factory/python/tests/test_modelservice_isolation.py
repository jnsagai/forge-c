"""Feature 017 T057 (+ static checks of T058-T062): the factory machine's only route to the model is the model channel."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from forge_factory.modelservice import isolation as I

ROOT = Path(__file__).resolve().parents[3]
FM = ROOT / "deploy/recipe/factory-machine"
PROVISION = FM / "provision.sh"
RUN_VM = FM / "vm/run-vm.sh"
CHANNEL = "http://127.0.0.1:18480/v1"


# ------------------------------------------------------------------------------------------------ fake environment
def fake(*, files: dict[str, str] | None = None, exists: set[str] = frozenset(), devices: list[str] = (),
         tools: dict[str, str] | None = None, open_ports: set[tuple[str, int]] = frozenset(), channel_status: int | None = 401,
         resolvable: set[str] = frozenset()) -> I.Probes:
    files = dict(files or {})
    tools = dict(tools or {})
    calls: list[tuple[str, int]] = []

    def tcp(h: str, p: int, _t: float) -> bool:
        calls.append((h, p))
        return (h, p) in open_ports

    probes = I.Probes(
        exists=lambda p: p in exists or p in files,
        glob=lambda g: [d for d in devices if d.startswith(g.rstrip("*"))],
        which=lambda t: tools.get(t),
        read_text=lambda p: files.get(p),
        resolve=lambda h: h if h in resolvable or re.fullmatch(r"[0-9.]+", h) else None,  # IP literals always resolve
        tcp_connect=tcp,
        http_status=lambda _u, _t: channel_status,
    )
    probes.calls = calls  # type: ignore[attr-defined]
    return probes


CONTAINER = {"/.dockerenv": ""}
ROUTE = "Iface\tDestination\tGateway\tFlags\nEth0\t00000000\t010012AC\t0003\n"  # default via 172.18.0.1


def _run(probes: I.Probes, **kw) -> dict:
    return I.check(I.Env(channel_url=CHANNEL, probes=probes, **kw))


def _chk(report: dict, cid: str) -> dict:
    return next(c for c in report["checks"] if c["id"] == cid)


def test_all_good_container_passes_and_lists_standin_limitations():
    r = _run(fake(files={**CONTAINER, "/proc/net/route": ROUTE}))
    assert r["status"] == "PASS" and r["open_issues"] == 0, r
    assert r["boundary"]["kind"] == "container"
    lim = " ".join(r["standin_limitations"])
    for prop in ("separate kernel", "VM network stack", "VM memory limits", "boot from production image"):
        assert prop in lim
    assert {c["id"] for c in r["checks"]} == {"boundary_present", "gpu_device_absent", "host_model_paths_absent",
                                               "only_model_channel_reachable"}
    blocked = [a for a in r["attempts"] if a["expected"] == "unreachable"]
    assert blocked and all(a["result"] == "blocked" for a in blocked)  # every attempt recorded (US5 scenario 1)
    hosts = {a["host"] for a in blocked}
    assert {"127.0.0.1", "172.18.0.1", "172.17.0.1", "10.0.2.2"} <= hosts and "host.docker.internal" not in hosts
    assert ("172.17.0.1", 18480) in {(a["host"], a["port"]) for a in blocked}  # gateway port on another address = 2nd route
    assert ("127.0.0.1", 18480) not in {(a["host"], a["port"]) for a in blocked}  # the channel itself is not a violation
    assert {(a["host"], a["port"]) for a in r["attempts"] if a["expected"] == "reachable"} == {("127.0.0.1", 18480)}
    for port in (11455, 11456, 11457, 11460, 8787, 8788, 32397, 22, 18502):
        assert ("127.0.0.1", port) in {(a["host"], a["port"]) for a in blocked}


def test_vm_has_no_standin_limitations():
    r = _run(fake(files={"/sys/class/dmi/id/sys_vendor": "QEMU\n"}))
    assert r["status"] == "PASS" and r["boundary"]["kind"] == "vm" and r["standin_limitations"] == []
    r = _run(fake(files={"/proc/cpuinfo": "processor\t: 0\nflags\t\t: fpu vme hypervisor lm\n"}))
    assert r["boundary"]["kind"] == "vm"


def test_host_without_boundary_fails():
    r = _run(fake(files={"/proc/cpuinfo": "flags\t\t: fpu vme lm\n", "/sys/class/dmi/id/sys_vendor": "Dell Inc.\n"}))
    assert r["status"] == "FAIL" and r["boundary"]["kind"] == "host"
    assert "no machine boundary" in _chk(r, "boundary_present")["reasons"][0]


def test_container_detected_from_cgroup():
    assert I.detect_boundary(fake(files={"/proc/1/cgroup": "0::/system.slice/docker-abc.scope\n"}))[0] == "container"


@pytest.mark.parametrize("devices,tools,needle", [
    (["/dev/nvidia0"], {}, "GPU device visible: /dev/nvidia0"),
    (["/dev/nvidiactl", "/dev/nvidia-uvm"], {}, "/dev/nvidiactl"),
    ([], {"nvidia-smi": "/usr/bin/nvidia-smi"}, "GPU tool installed: nvidia-smi"),
])
def test_gpu_visible_fails(devices, tools, needle):
    r = _run(fake(files=CONTAINER, devices=devices, tools=tools))
    c = _chk(r, "gpu_device_absent")
    assert r["status"] == "FAIL" and c["status"] == "FAIL" and any(needle in x for x in c["reasons"]), c


def test_gpu_driver_interface_fails():
    r = _run(fake(files=CONTAINER, exists={"/proc/driver/nvidia"}))
    assert _chk(r, "gpu_device_absent")["reasons"] == ["GPU driver interface visible: /proc/driver/nvidia"]


@pytest.mark.parametrize("path", list(I.DEFAULT_HOST_MODEL_PATHS))
def test_host_model_path_visible_fails(path):
    r = _run(fake(files=CONTAINER, exists={path}))
    c = _chk(r, "host_model_paths_absent")
    assert r["status"] == "FAIL" and c["reasons"] == [f"host model path visible: {path}"]


def test_configurable_model_paths():
    r = _run(fake(files=CONTAINER, exists={"/models/x"}), host_model_paths=("/models/x",))
    assert _chk(r, "host_model_paths_absent")["observed"]["visible"] == ["/models/x"]


@pytest.mark.parametrize("hp", [("127.0.0.1", 22), ("127.0.0.1", 8787), ("172.17.0.1", 11460), ("10.0.2.2", 32397),
                                ("172.17.0.1", 18480), ("127.0.0.1", 18502)])
def test_other_host_port_reachable_fails(hp):
    r = _run(fake(files=CONTAINER, open_ports={hp}))
    c = _chk(r, "only_model_channel_reachable")
    assert r["status"] == "FAIL" and c["reasons"] == [f"host service reachable: {hp[0]}:{hp[1]}"]
    viol = [a for a in r["attempts"] if a["result"] == "VIOLATION"]
    assert [(a["host"], a["port"]) for a in viol] == [hp]


def test_channel_unreachable_fails_but_any_http_status_counts_as_reachable():
    r = _run(fake(files=CONTAINER, channel_status=None))
    assert r["status"] == "FAIL"
    assert _chk(r, "only_model_channel_reachable")["reasons"] == [f"model channel not reachable: {CHANNEL}/models"]
    for status in (200, 401, 403, 503):
        assert _run(fake(files=CONTAINER, channel_status=status))["status"] == "PASS"


def test_unresolvable_hosts_are_recorded_not_probed():
    p = fake(files=CONTAINER)
    r = _run(p)
    assert _chk(r, "only_model_channel_reachable")["observed"]["unresolved_hosts"] == ["host.docker.internal"]
    assert {h for h, _ in p.calls} == {"127.0.0.1", "172.17.0.1", "10.0.2.2"}  # type: ignore[attr-defined]
    p = fake(files=CONTAINER, resolvable={"host.docker.internal"})
    _run(p)
    assert "host.docker.internal" in {h for h, _ in p.calls}  # type: ignore[attr-defined]


def test_default_gateway_parse_and_bad_channel():
    assert I.default_gateway(lambda _p: ROUTE) == "172.18.0.1"
    assert I.default_gateway(lambda _p: None) is None
    with pytest.raises(ValueError):
        I.check(I.Env(channel_url="unix:///x", probes=fake(files=CONTAINER)))


def test_boundary_override_validated():
    assert _run(fake(), boundary_override="vm")["boundary"]["kind"] == "vm"
    with pytest.raises(ValueError):
        _run(fake(), boundary_override="cloud")


def test_cli_writes_report_and_exit_code(tmp_path, monkeypatch):
    good = fake(files=CONTAINER)
    bad = fake(files=CONTAINER, devices=["/dev/nvidia0"])
    monkeypatch.setattr(I, "Probes", lambda: good)
    out = tmp_path / "r/report.json"
    assert I.main(["--channel", CHANNEL, "--out", str(out), "--port", "22"]) == 0
    rep = json.loads(out.read_text())
    assert rep["schema"] == I.SCHEMA and rep["status"] == "PASS" and rep["standin_limitations"]
    assert {a["port"] for a in rep["attempts"] if a["expected"] == "unreachable" and a["host"] == "127.0.0.1"} == {22}
    monkeypatch.setattr(I, "Probes", lambda: bad)
    assert I.main(["--channel", CHANNEL, "--out", str(out)]) == 1
    assert json.loads(out.read_text())["status"] == "FAIL"
    assert I.main(["--channel", "ftp://x", "--out", str(out)]) == 2


# ----------------------------------------------------------------------------------------------- provision.sh (T058)
def _lock(tmp: Path, factory_revision=None, **toolchain) -> Path:
    doc = json.loads((ROOT / "deploy/recipe/recipe.lock.json").read_text())
    doc["toolchain"] = toolchain
    doc["factory_revision"] = factory_revision  # tests control it; the real lock now pins one
    p = tmp / "recipe.lock.json"
    p.write_text(json.dumps(doc))
    return p


def _provision(tmp: Path, *args: str, **env: str) -> subprocess.CompletedProcess:
    base = {"PATH": "/usr/bin:/bin", "HOME": str(tmp), "LC_ALL": "C"}
    return subprocess.run(["bash", str(PROVISION), *args], cwd=tmp, capture_output=True, text=True, timeout=60,
                          env={**base, **env}, check=False)


def _all_pins(tmp: Path) -> dict[str, str]:
    env = {f"FORGE_PIN_{n}_SHA256": f"{i + 1:x}" * 64 for i, n in enumerate(("UV", "LLVM", "GNU_ARM", "FABRO", "FORMAL"))}
    env |= {"FORGE_PIN_FABRO_URL": "https://example.invalid/fabro-0.362.0.tar.gz",
            "FORGE_PIN_FORMAL_URL": "http://127.0.0.1:18490/formal-frama-c-33.0-opam-switch.tar.gz", "FORGE_REPO_URL": "https://git.example.invalid/forge-c.git",
            "FORGE_REVISION": "a" * 40, "FORGE_LOCK_FILE": str(_lock(tmp))}
    return env


def test_provision_is_valid_bash_with_modes_and_no_gpu_software():
    assert subprocess.run(["bash", "-n", str(PROVISION)], capture_output=True, check=False).returncode == 0
    text = PROVISION.read_text()
    assert text.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in text
    assert "--dry-run" in text and "--container" in text
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    pkgs = re.search(r"APT_PACKAGES=\(([^)]*)\)", code, re.S).group(1).split()
    assert pkgs and not [p for p in pkgs if re.search(r"nvidia|cuda", p, re.I)]
    assert not re.search(r"(apt-get|apt|pip|uv)\s+(install|add)\b[^\n]*(nvidia|cuda)", code, re.I)
    assert "frama-c-base" not in code  # not in the Ubuntu 22.04 archive: Frama-C comes as the pinned `formal` archive
    for comp in ("19.1.7", "10.3-2021.07", "0.362.0", "3.13", "frama-c-33.0", "install_tarball formal", "cbmc", "gcovr", "cppcheck", "nginx"):
        assert comp in text, comp
    assert "sha256sum -c" in code and "enable-linger" in code


def test_provision_dry_run_plans_and_changes_nothing(tmp_path):
    lock = _lock(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    r = _provision(tmp_path, "--dry-run", FORGE_LOCK_FILE=str(lock))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PLAN:" in r.stdout and "RUN:" not in r.stdout and "dry-run complete: nothing was changed" in r.stdout
    assert "PIN MISSING" in r.stdout and "would REFUSE" in r.stdout  # empty lock: reported, not skipped
    assert "loginctl enable-linger forge" in r.stdout
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_provision_container_mode_skips_systemd_and_mount(tmp_path):
    r = _provision(tmp_path, "--dry-run", "--container", **_all_pins(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PIN MISSING" not in r.stdout and "enable-linger" not in r.stdout
    assert "skip (container): lingering" in r.stdout and "skip (container): the data volume" in r.stdout
    assert "LLVM-19.1.7-Linux-X64.tar.xz" in r.stdout and "gcc-arm-none-eabi-10.3-2021.07-x86_64-linux.tar.bz2" in r.stdout


@pytest.mark.parametrize("drop", ["FORGE_PIN_LLVM_SHA256", "FORGE_PIN_GNU_ARM_SHA256", "FORGE_PIN_FABRO_SHA256",
                                  "FORGE_PIN_UV_SHA256", "FORGE_PIN_FORMAL_SHA256", "FORGE_PIN_FORMAL_URL", "FORGE_REVISION"])
def test_provision_refuses_missing_checksum_before_any_change(tmp_path, drop):
    env = _all_pins(tmp_path)
    env.pop(drop)
    r = _provision(tmp_path, FORGE_PROVISION_STOP_AFTER="pins", **env)
    assert r.returncode == 4, r.stdout + r.stderr
    assert "REFUSED" in r.stderr and "nothing was changed" in r.stderr
    assert "RUN:" not in r.stdout and "STOP after pin" not in r.stdout


def test_provision_refuses_placeholder_and_malformed_checksums(tmp_path):
    for bad in ("TODO_PIN", "0" * 64, "ABC", "g" * 64):
        env = _all_pins(tmp_path) | {"FORGE_PIN_LLVM_SHA256": bad}
        r = _provision(tmp_path, FORGE_PROVISION_STOP_AFTER="pins", **env)
        assert r.returncode == 4 and "llvm" in r.stdout, (bad, r.stdout)


def test_provision_reads_pins_from_lock_and_stops_after_verification(tmp_path):
    env = _all_pins(tmp_path)
    shas = {n: env.pop(f"FORGE_PIN_{n.upper()}_SHA256") for n in ("uv", "llvm", "gnu_arm", "fabro", "formal")}
    tc = {n: {"sha256": s} for n, s in shas.items()}
    tc["fabro"]["url"] = env.pop("FORGE_PIN_FABRO_URL")
    tc["formal"]["url"] = env.pop("FORGE_PIN_FORMAL_URL")
    env["FORGE_LOCK_FILE"] = str(_lock(tmp_path, **tc))
    r = _provision(tmp_path, FORGE_PROVISION_STOP_AFTER="pins", **env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "STOP after pin verification" in r.stdout and "RUN:" not in r.stdout
    assert f"sha256={shas['llvm']}" in r.stdout
    tc["llvm"]["version"] = "18.1.0"  # a lock that disagrees with the script's pinned version is refused
    env["FORGE_LOCK_FILE"] = str(_lock(tmp_path, **tc))
    assert _provision(tmp_path, FORGE_PROVISION_STOP_AFTER="pins", **env).returncode == 4


def test_provision_refuses_gpu_packages(tmp_path):
    r = _provision(tmp_path, "--dry-run", FORGE_EXTRA_APT="nvidia-driver-550", FORGE_LOCK_FILE=str(_lock(tmp_path)))
    assert r.returncode == 4 and "GPU package" in r.stderr


# ------------------------------------------------------------------------------------- cloud-init, Dockerfile (T059)
def test_cloud_init_user_data():
    text = (FM / "cloud-init/user-data.yaml").read_text()
    assert text.startswith("#cloud-config\n")
    doc = yaml.safe_load(text)
    assert [u["name"] for u in doc["users"]] == ["forge"] and "sudo" not in doc["users"][0]
    assert doc["ssh_pwauth"] is False and doc["disable_root"] is True
    assert ["LABEL=forge-data", "/srv/forge-c", "ext4", "defaults,nofail", "0", "2"] in doc["mounts"]
    paths = {f["path"] for f in doc["write_files"]}
    assert "/opt/forge-c/recipe/factory-machine/provision.sh" in paths
    cmds = json.dumps(doc["runcmd"])
    assert "enable-linger" in cmds and "provision.sh" in cmds
    assert not re.search(r"nvidia|cuda", text, re.I)


def test_run_vm_renders_seed_with_provision_script(tmp_path):
    pub = tmp_path / "id.pub"
    pub.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample forge@test\n")
    envf = tmp_path / "provision.env"
    envf.write_text("FORGE_SITE=omniverse2\nFORGE_REVISION=" + "a" * 40 + "\n")
    r = subprocess.run(["bash", str(RUN_VM), "--render-seed", str(tmp_path / "seed")], capture_output=True, text=True, timeout=60,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "FORGE_VM_SSH_PUBKEY_FILE": str(pub),
                            "FORGE_PROVISION_ENV_FILE": str(envf)}, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    ud = (tmp_path / "seed/user-data").read_text()
    assert ud.startswith("#cloud-config\n") and not re.search(r'"@@FORGE_\w+@@"', ud)
    doc = yaml.safe_load(ud)
    files = {f["path"]: base64.b64decode(f["content"]) for f in doc["write_files"]}
    assert files["/opt/forge-c/recipe/factory-machine/provision.sh"] == PROVISION.read_bytes()
    assert b"FORGE_REVISION=" in files["/etc/forge-c/provision.env"]
    assert doc["users"][0]["ssh_authorized_keys"] == [pub.read_text().strip()]
    assert yaml.safe_load((tmp_path / "seed/meta-data").read_text())["local-hostname"] == "forge-factory"
    envf.write_text("SOME_API_KEY=abc\n")
    r = subprocess.run(["bash", str(RUN_VM), "--render-seed", str(tmp_path / "seed2")], capture_output=True, text=True, timeout=60,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "FORGE_PROVISION_ENV_FILE": str(envf)}, check=False)
    assert r.returncode != 0 and "credential" in r.stderr


def test_dockerfile_standin():
    df = (FM / "container/Dockerfile").read_text()
    code = "\n".join(ln for ln in df.splitlines() if not ln.lstrip().startswith("#"))
    assert re.search(r"^ARG BASE_DIGEST\s*$", code, re.M)
    assert re.search(r"^FROM ubuntu:22\.04@\$\{BASE_DIGEST\}\s*$", code, re.M)
    assert "BASE_DIGEST unset or malformed" in code  # the build fails without a real digest
    assert "provision.sh --container" in code
    assert re.search(r"^USER forge\s*$", code, re.M)
    assert not re.search(r"nvidia|cuda", code, re.I)


# ------------------------------------------------------------------------------------------------- compose (T060)
def test_factory_compose_has_no_gpu_and_only_internal_networks():
    doc = yaml.safe_load((FM / "compose.yaml").read_text())
    assert list(doc["services"]) == ["factory"]
    svc = doc["services"]["factory"]
    for k in ("devices", "device_requests", "runtime", "network_mode", "ports", "extra_hosts", "privileged", "gpus"):
        assert k not in svc, k
    assert "deploy" not in svc  # no resources.reservations.devices (GPU) either
    assert svc["networks"] == ["factory-boundary"]
    assert all(n.get("internal") is True for n in doc["networks"].values())
    vols = svc["volumes"]
    assert len(vols) == 1 and vols[0]["source"] == "/mnt/data/forge-c/model-service/factory-data" and vols[0]["target"] == "/srv/forge-c"
    assert not any(m in json.dumps(svc) for m in ("/models", "ollama", "/dev/shm", "/dev/"))
    assert svc["environment"]["FORGE_MODEL_CHANNEL_URL"] == CHANNEL
    assert "UNIX-CONNECT:/srv/forge-c/.channel/model.sock" in " ".join(svc["command"])
    assert svc["cap_drop"] == ["ALL"] and svc["user"] == "forge"


@pytest.mark.skipif(shutil.which("docker") is None, reason="NOT_RUN: docker absent on this machine")
def test_factory_compose_config_is_valid():
    r = subprocess.run(["docker", "compose", "-f", str(FM / "compose.yaml"), "config", "--quiet"], capture_output=True, text=True,
                       timeout=60, check=False, env={**os.environ, "FORGE_FACTORY_BASE_DIGEST": "sha256:" + "1" * 64})
    assert r.returncode == 0, r.stderr


# ----------------------------------------------------------------------------------------------------- VM (T062)
def test_run_vm_is_valid_bash_and_never_uses_docker_for_kvm():
    assert subprocess.run(["bash", "-n", str(RUN_VM)], capture_output=True, check=False).returncode == 0
    code = "\n".join(ln for ln in RUN_VM.read_text().splitlines() if not ln.lstrip().startswith("#"))
    assert "docker" not in code  # research R9: /dev/kvm is never passed through Docker
    assert '[ -r "$FORGE_KVM_DEVICE" ] && [ -w "$FORGE_KVM_DEVICE" ]' in code
    assert "genisoimage" in code and "restrict=$RESTRICT" in code


@pytest.mark.parametrize("make", ["absent", "mode000"])
def test_run_vm_blocked_without_kvm(tmp_path, make):
    kvm = tmp_path / "kvm"
    if make == "mode000":
        kvm.write_text("")
        kvm.chmod(0)
        if os.access(kvm, os.R_OK):
            pytest.skip("NOT_RUN: running as root, a mode-000 file stays accessible")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "FORGE_KVM_DEVICE": str(kvm), "FORGE_VM_DIR": str(tmp_path / "vm")}
    r = subprocess.run(["bash", str(RUN_VM)], capture_output=True, text=True, timeout=60, env=env, check=False)
    assert r.returncode == 3 and r.stdout.strip() == "BLOCKED: /dev/kvm not accessible (needs kvm group, owner 2026-11-08)"
    assert not (tmp_path / "vm").exists()
    r = subprocess.run(["bash", str(RUN_VM), "--dry-run"], capture_output=True, text=True, timeout=60, env=env, check=False)
    assert r.returncode == 3 and "BLOCKED: /dev/kvm not accessible" in r.stdout
    q = next(ln for ln in r.stdout.splitlines() if "qemu-system-x86_64" in ln)
    assert "-smp 16" in q and "-m 64G" in q and "restrict=on" in q and "accel=kvm" in q
    assert "hostfwd=tcp:127.0.0.1:2222-:22" in q and "guestfwd=tcp:10.0.2.100:18480-cmd:socat" in q
    assert q.count("hostfwd=") == 1 and q.count("guestfwd=") == 1
    assert "genisoimage" in r.stdout and not (tmp_path / "vm").exists()
