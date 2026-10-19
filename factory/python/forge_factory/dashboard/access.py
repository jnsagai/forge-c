"""Dashboard sign-in mode (owner decision OD-2026-10-19-09): `token` (viewer/auditor tokens, the default in code)
or `disabled` (no sign-in until deployment). FORGE_DASHBOARD_AUTH overrides the file; an unreadable or invalid file
fails closed to `token`.

`disabled` applies to requests from this machine (loopback clients get `anonymous_role`) and, by owner decision
OD-2026-10-19-10, to the owner's trusted devices: a device listed under `trusted_devices` by its Tailscale address
(100.64.0.0/10), and only when the connection arrives on a Tailscale listen address of this machine. Tailscale
authenticates each device, so its address identifies it; a Wi-Fi/LAN address does not (the router hands it to any
device), so LAN clients always need a viewer/auditor token. The AFO operator token is not affected by this switch."""
from __future__ import annotations

import ipaddress
import os

import yaml

from ..common import REPO_ROOT

CONFIG = REPO_ROOT / "config/factory/dashboard-access.yaml"
MODES = ("token", "disabled")
ROLES = ("viewer", "auditor")
LOOPBACK = ("127.0.0.1", "localhost", "::1")
TAILNET = ipaddress.ip_network("100.64.0.0/10")


def _tailnet(host: str | None) -> bool:
    try:
        return host is not None and ipaddress.ip_address(host) in TAILNET
    except ValueError:
        return False


def load() -> dict:
    try:
        doc = yaml.safe_load(CONFIG.read_text()) or {}
    except (OSError, yaml.YAMLError):
        doc = {}
    mode = os.environ.get("FORGE_DASHBOARD_AUTH") or doc.get("auth") or "token"
    role = doc.get("anonymous_role") or "viewer"
    devices = doc.get("trusted_devices") or []
    bad = [d for d in devices if not isinstance(d, dict) or not d.get("name") or not _tailnet(d.get("address"))]
    if mode not in MODES or role not in ROLES or not isinstance(devices, list) or bad:
        return {"auth": "token", "anonymous_role": "viewer", "decision": None, "trusted": {},
                "error": f"invalid dashboard access setting (auth={mode!r}, anonymous_role={role!r}, "
                         f"trusted_devices={devices!r}); using token"}
    return {"auth": mode, "anonymous_role": role, "decision": doc.get("decision"),
            "trusted": {d["address"]: d["name"] for d in devices}, "error": None}


def anonymous_role(access: dict, client_host: str | None, server_host: str | None = None) -> str | None:
    """The role granted without a token: only when sign-in is disabled AND the client is this machine, or a trusted
    device connecting over Tailscale (client and listen address both in the tailnet)."""
    if access["auth"] != "disabled":
        return None
    if client_host in LOOPBACK:
        return access["anonymous_role"]
    if client_host in access.get("trusted", {}) and _tailnet(server_host):
        return access["anonymous_role"]
    return None
