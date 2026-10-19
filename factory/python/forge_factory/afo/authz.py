"""AFO-T006 (AFO-FR-003, AT-063/AT-064) - signed owner authorization for PILOT/ACTIVE.

An authorization is a JSON record (contracts/authorization.schema.json) plus a detached OpenSSH signature
(`ssh-keygen -Y sign -n forge-afo-authorization`) made by the owner with their own key; the factory holds only the
public key in an allowed-signers file. A record grants nothing unless ALL of these hold:
  schema valid; signature valid for the approver principal; issued <= now < expires; not revoked (revoked_utc or the
  revocation list); bound to the exact active AFO policy sha256; the requested mode; the action listed; the scope
  (order ids, driver classes, models, service actions) covering the request when the record restricts it.
The signed message is the canonical JSON of the record without `signature_ref` and `revoked_utc` (a revocation can
be added later without re-signing). An agent never holds the owner's private key: `sign` is an owner CLI.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..common import REPO_ROOT, canonical_json

NAMESPACE = "forge-afo-authorization"
AUTH_DIR = REPO_ROOT / "config/factory/afo-authorizations"
ALLOWED_SIGNERS = REPO_ROOT / "config/factory/afo-allowed-signers"
REVOKED = AUTH_DIR / "revoked.txt"
SCHEMA = REPO_ROOT / "specs/005-autonomous-factory-operations/contracts/authorization.schema.json"
UNSIGNED_FIELDS = ("signature_ref", "revoked_utc")


@dataclass(frozen=True)
class AuthDecision:
    allow: bool
    code: str
    reason: str = ""
    authorization_id: str | None = None


def message(auth: dict) -> bytes:
    return canonical_json({k: v for k, v in auth.items() if k not in UNSIGNED_FIELDS})


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def schema_errors(auth: dict) -> list[str]:
    import jsonschema

    v = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()), format_checker=jsonschema.FormatChecker())
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:160] for e in v.iter_errors(auth)]


def signature_valid(auth: dict, sig: Path, allowed_signers: Path) -> bool:
    if not sig.is_file() or not allowed_signers.is_file():
        return False
    r = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers), "-I", str(auth["approver"]),
                        "-n", NAMESPACE, "-s", str(sig)], input=message(auth), capture_output=True, timeout=30)
    return r.returncode == 0


def revoked_ids(path: Path | None = None) -> set[str]:
    """Revocation list: one authorization id per line, next to the records (<base>/revoked.txt)."""
    path = path or REVOKED
    if not path.is_file():
        return set()
    return {ln.split("#", 1)[0].strip() for ln in path.read_text().splitlines() if ln.split("#", 1)[0].strip()}


def verify(auth: dict, *, policy_sha256: str, mode: str, action: str | None = None, request: dict | None = None,
           now: datetime | None = None, base: Path | None = None, allowed_signers: Path | None = None,
           revoked: set[str] | None = None) -> AuthDecision:
    base, allowed_signers = base or AUTH_DIR, allowed_signers or ALLOWED_SIGNERS  # resolved at call time
    aid = auth.get("authorization_id") if isinstance(auth, dict) else None
    errs = schema_errors(auth) if isinstance(auth, dict) else ["<root>: not an object"]
    if errs:
        return AuthDecision(False, "AUTH_SCHEMA_INVALID", errs[0], aid)
    now = now or datetime.now(UTC)
    if not signature_valid(auth, (base / auth["signature_ref"]).resolve(), allowed_signers):
        return AuthDecision(False, "AUTH_SIGNATURE_INVALID", f"no valid {NAMESPACE} signature by {auth['approver']}", aid)
    if auth.get("revoked_utc") or aid in (revoked if revoked is not None else revoked_ids(base / "revoked.txt")):
        return AuthDecision(False, "AUTH_REVOKED", str(auth.get("revoked_utc") or "revocation list"), aid)
    if not _ts(auth["issued_utc"]) <= now < _ts(auth["expires_utc"]):
        return AuthDecision(False, "AUTH_NOT_CURRENT", f"valid {auth['issued_utc']} .. {auth['expires_utc']}", aid)
    if auth["policy_sha256"] != policy_sha256:
        return AuthDecision(False, "AUTH_POLICY_MISMATCH", "authorization is bound to another AFO policy", aid)
    if auth["mode"] != mode:
        return AuthDecision(False, "AUTH_MODE_MISMATCH", f"authorizes {auth['mode']}, requested {mode}", aid)
    if action is not None and action not in auth["allowed_actions"]:
        return AuthDecision(False, "AUTH_ACTION_NOT_ALLOWED", action, aid)
    scope, req = auth.get("scope") or {}, request or {}
    for key, field in (("order_ids", "order_id"), ("driver_classes", "driver_class"), ("models", "model"),
                       ("service_actions", "service_action")):
        if scope.get(key) and field in req and req[field] not in scope[key]:
            return AuthDecision(False, "AUTH_OUT_OF_SCOPE", f"{field}={req[field]}", aid)
    return AuthDecision(True, "AUTH_OK", "", aid)


def find(mode: str, policy_sha256: str, base: Path | None = None, ref: str | None = None, **kw) -> AuthDecision:
    """Verify the authorization record the policy names (`ref`, required for PILOT/ACTIVE by the policy schema);
    the decision carries the exact reason a record does not authorize."""
    base = base or AUTH_DIR
    if not ref:
        return AuthDecision(False, "AUTH_NOT_REFERENCED", "the policy names no authorization_ref")
    p = base / f"{ref}.json"
    if not p.is_file():
        return AuthDecision(False, "AUTH_RECORD_MISSING", p.name, ref)
    try:
        auth = json.loads(p.read_text())
    except ValueError:
        return AuthDecision(False, "AUTH_NOT_JSON", p.name, ref)
    if auth.get("authorization_id") != ref:
        return AuthDecision(False, "AUTH_ID_MISMATCH", f"{p.name} holds {auth.get('authorization_id')}", ref)
    return verify(auth, policy_sha256=policy_sha256, mode=mode, base=base, **kw)


def sign(auth_path: Path, key: Path) -> Path:
    """Owner CLI: write <auth>.sig with the owner's own private key (never run by an agent)."""
    auth = json.loads(auth_path.read_text())
    with tempfile.TemporaryDirectory() as td:
        m = Path(td) / "msg"
        m.write_bytes(message(auth))
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(m)], check=True,
                       capture_output=True)
        out = auth_path.with_suffix(".sig")
        out.write_bytes((Path(td) / "msg.sig").read_bytes())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.afo.authz")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign", help="owner only: sign an authorization record with your own SSH key")
    s.add_argument("auth", type=Path)
    s.add_argument("--key", type=Path, required=True)
    v = sub.add_parser("verify")
    v.add_argument("auth", type=Path)
    v.add_argument("--mode", required=True)
    v.add_argument("--action")
    a = ap.parse_args(argv)
    if a.cmd == "sign":
        print(sign(a.auth, a.key))
        return 0
    from .policy import load

    d = verify(json.loads(a.auth.read_text()), policy_sha256=load().sha256 or "", mode=a.mode, action=a.action,
               base=a.auth.parent)
    print(json.dumps(d.__dict__))
    return 0 if d.allow else 1


if __name__ == "__main__":
    sys.exit(main())
