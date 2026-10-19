"""Dashboard sign-in mode (owner decision OD-2026-10-19-09): `token` (viewer/auditor tokens, the default in code)
or `disabled` (no sign-in until deployment). FORGE_DASHBOARD_AUTH overrides the file; an unreadable or invalid file
fails closed to `token`.

`disabled` applies to requests from this machine only (loopback clients get `anonymous_role`). Requests from any
other address - the phone over Tailscale or Wi-Fi - always need a viewer/auditor token, so listening on a network
address never exposes the factory without sign-in. The AFO operator token is not affected by this switch."""
from __future__ import annotations

import os

import yaml

from ..common import REPO_ROOT

CONFIG = REPO_ROOT / "config/factory/dashboard-access.yaml"
MODES = ("token", "disabled")
ROLES = ("viewer", "auditor")
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def load() -> dict:
    try:
        doc = yaml.safe_load(CONFIG.read_text()) or {}
    except (OSError, yaml.YAMLError):
        doc = {}
    mode = os.environ.get("FORGE_DASHBOARD_AUTH") or doc.get("auth") or "token"
    role = doc.get("anonymous_role") or "viewer"
    if mode not in MODES or role not in ROLES:
        return {"auth": "token", "anonymous_role": "viewer", "decision": None,
                "error": f"invalid dashboard access setting (auth={mode!r}, anonymous_role={role!r}); using token"}
    return {"auth": mode, "anonymous_role": role, "decision": doc.get("decision"), "error": None}


def anonymous_role(access: dict, client_host: str | None) -> str | None:
    """The role granted without a token: only when sign-in is disabled AND the client is this machine."""
    return access["anonymous_role"] if access["auth"] == "disabled" and client_host in LOOPBACK else None
