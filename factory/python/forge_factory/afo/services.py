"""AFO-T009 (AFO-FR-009, AT-001/004/005/007) - render, verify, install, status and stop the AFO user units.

  python -m forge_factory.afo.services render  [--out DIR]     # dry run: rendered units to DIR (default: stdout)
  python -m forge_factory.afo.services verify                  # systemd-analyze --user verify on the rendered units
  python -m forge_factory.afo.services install [--enable U..]  # OPERATOR action: write ~/.config/systemd/user units
  python -m forge_factory.afo.services status | stop U..

Install writes the units and reloads systemd; it enables/starts only the units named with --enable (never all by
default) and never touches services of other projects. Stop uses systemctl on the named Forge-C units, never a
process-name pattern (other projects run their own Fabro/Ollama on this host). `scripts/forge_services.sh` keeps
working unchanged; once units are installed it can be replaced by `systemctl --user ... forge-*.service`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ..common import REPO_ROOT, data_root, state_dir

TEMPLATES = REPO_ROOT / "deploy/systemd/afo"
UNIT_DIR = Path.home() / ".config/systemd/user"
UNITS = (
    "forge-ollama.service",
    "forge-llm-gateway.service",
    "forge-llm-gateway-cloud.service",
    "forge-fabro.service",
    "forge-fabro-cloud.service",
    "forge-dashboard.service",
    "forge-conductor.service",
    "forge-afo-watchdog.service",
    "forge-afo-watchdog.timer",
)


def values() -> dict[str, str]:
    venv = os.environ.get("FORGE_VENV") or str(data_root() / "venv")
    fabro = os.environ.get("FORGE_FABRO_BIN") or str(Path.home() / ".fabro/bin/fabro")
    return {
        "@REPO@": str(REPO_ROOT),
        "@DATA@": str(data_root()),
        "@VENV@": venv,
        "@FABRO@": fabro,
        "@STATE@": str(state_dir()),
        "@PATH@": f"{venv}/bin:/usr/local/bin:/usr/bin:/bin",
        "@CLOUD_CAP@": os.environ.get("FORGE_CLOUD_COST_CAP_USD", "2.00"),
    }


def render() -> dict[str, str]:
    vals, out = values(), {}
    for u in UNITS:
        t = (TEMPLATES / f"{u}.in").read_text()
        for k, v in vals.items():
            t = t.replace(k, v)
        if "@" in "".join(x for x in t.splitlines() if not x.startswith("#")).replace("@.", ""):
            leftover = sorted({w for w in t.split() if w.startswith("@") and w.endswith("@")})
            if leftover:
                raise ValueError(f"UNRENDERED_PLACEHOLDER:{u}:{leftover}")
        out[u] = t
    intent = os.environ.get("FORGE_OPERATIONS_INTENT")
    if intent:
        # Explicit deployment render only; running this renderer does not install/enable any unit.
        profile = os.environ.get("FORGE_CONDUCTOR_FABRO_UNIT", "forge-fabro.service")
        if profile not in ("forge-fabro.service", "forge-fabro-cloud.service", "external-local-profile"):
            raise ValueError("INVALID_CONDUCTOR_DEPENDENCY_UNIT")
        for unit in ("forge-conductor.service", "forge-afo-watchdog.service"):
            text = out[unit]
            text = text.replace(
                "After=forge-fabro-cloud.service ", "After=" + (profile + " " if profile != "external-local-profile" else "")
            )
            text = text.replace("Restart=on-failure", "Restart=always")
            text = text.replace("[Service]", "[Service]\nEnvironment=FORGE_OPERATIONS_INTENT=" + intent)
            if unit == "forge-conductor.service":
                text = text.replace(
                    "ExecStartPre=",
                    "ExecCondition=" + vals["@VENV@"] + "/bin/python -m forge_factory.afo.operations boot-check\nExecStartPre=",
                    1,
                )
                text = text.replace(
                    "UMask=0077",
                    "UMask=0077\nRestartPreventExitStatus=77\nCPUWeight=1000\nIOWeight=1000\nMemoryLow=256M\nTasksMax=128",
                )
            selected = os.environ.get("FORGE_OPERATIONS_PROFILE")
            if selected:
                from ..lrtx.profile import load

                load(selected)  # pinned existing profile; renderer performs no service/model action
                text = text.replace(
                    "[Service]",
                    "[Service]\nEnvironment=FORGE_OPERATIONS_PROFILE="
                    + selected
                    + "\nEnvironment=FORGE_LRTX_ROOT="
                    + str(Path(os.environ.get("FORGE_LRTX_ROOT") or load(selected)["deployment"]["default_root"])),
                )
                text = text.replace(
                    "Environment=FORGE_STATE_DIR=" + vals["@STATE@"],
                    "Environment=FORGE_STATE_DIR="
                    + str(Path(os.environ.get("FORGE_LRTX_ROOT") or load(selected)["deployment"]["default_root"]) / "state"),
                )
                if unit == "forge-conductor.service":
                    command = vals["@VENV@"] + "/bin/python -m forge_factory.afo.conductor --interval 15"
                    wrapped = (
                        vals["@VENV@"] + "/bin/python -m forge_factory.lrtx.stack exec --profile " + selected + " -- " + command
                    )
                    text = text.replace("ExecStart=" + command, "ExecStart=" + wrapped)
            out[unit] = text
        conductor = os.environ.get("FORGE_CONDUCTOR_UNIT", "forge-conductor.service")
        if conductor not in ("forge-conductor.service", "forge-conductor-local-omniverse2.service"):
            raise ValueError("UNAPPROVED_CONDUCTOR_UNIT")
        if conductor != "forge-conductor.service":
            out[conductor] = out.pop("forge-conductor.service")
        for unit in (conductor, "forge-afo-watchdog.service"):
            out[unit] = out[unit].replace("[Service]", "[Service]\nEnvironment=FORGE_CONDUCTOR_UNIT=" + conductor)
    return out


def verify(units: dict[str, str] | None = None) -> dict:
    units = units or render()
    with tempfile.TemporaryDirectory() as td:
        for u, t in units.items():
            (Path(td) / u).write_text(t)
        r = subprocess.run(
            ["systemd-analyze", "--user", "verify", *[str(Path(td) / u) for u in units]],
            capture_output=True,
            text=True,
            timeout=60,
        )
    msgs = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()]
    # missing ExecStart binaries on a host that does not run that service are reported, not hidden
    return {"ok": r.returncode == 0, "messages": msgs[:40]}


def install(enable: list[str]) -> dict:
    units = render()
    v = verify(units)
    if not v["ok"]:
        return {"installed": [], "verify": v}
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    for u, t in units.items():
        (UNIT_DIR / u).write_text(t)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    for u in enable:
        if u not in units:
            raise SystemExit(f"NOT_AN_AFO_UNIT:{u}")
        subprocess.run(["systemctl", "--user", "enable", "--now", u], check=True)
    return {"installed": list(units), "enabled": enable, "verify": v}


def status() -> dict:
    out = {}
    for u in render():
        r = subprocess.run(
            ["systemctl", "--user", "show", u, "--property=LoadState,ActiveState,SubState,NRestarts,UnitFileState"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        out[u] = dict(x.split("=", 1) for x in r.stdout.splitlines() if "=" in x)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.afo.services")
    ap.add_argument("cmd", choices=["render", "verify", "install", "status", "stop"])
    ap.add_argument("units", nargs="*")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--enable", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.cmd == "render":
        units = render()
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            for u, t in units.items():
                (a.out / u).write_text(t)
            print(json.dumps(sorted(units)))
        else:
            print("\n".join(f"### {u}\n{t}" for u, t in units.items()))
        return 0
    if a.cmd == "verify":
        r = verify()
        print(json.dumps(r, indent=1))
        return 0 if r["ok"] else 1
    if a.cmd == "install":
        print(json.dumps(install(a.enable), indent=1))
        return 0
    if a.cmd == "status":
        print(json.dumps(status(), indent=1))
        return 0
    bad = [u for u in a.units if u not in render()]
    if bad or not a.units:
        raise SystemExit(f"stop needs Forge-C unit names {UNITS}; refused {bad}")
    subprocess.run(["systemctl", "--user", "stop", *a.units], check=False)
    return 0


if __name__ == "__main__":
    if shutil.which("systemctl") is None:
        sys.exit("systemctl not available")
    sys.exit(main())
