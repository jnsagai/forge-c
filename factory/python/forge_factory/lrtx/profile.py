"""LRTX-T005..T008: explicit, versioned local-profile selection, runtime isolation, local endpoint enforcement and
run provenance (LRTX-FR-002..FR-005, FR-018).

`workorder --profile local-rtx-v1` calls `select()` before anything is prepared. Without `--profile` nothing here runs
and the work order behaves exactly as at the preserved baseline (frozen fixtures, tests/compat/lrtx). Every refusal is
raised before launch as `ProfileRefused` with machine-readable issue codes.
"""
from __future__ import annotations

import json
import os
import socket
import tomllib
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from ..common import REPO_ROOT, sha256_bytes

PROFILE_DIR = REPO_ROOT / "config/factory/profiles"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
# a public address used only to prove the run's network namespace cannot reach it (no data is sent)
EXTERNAL_PROBE = ("1.1.1.1", 443)


class ProfileRefused(RuntimeError):
    def __init__(self, issues: list[str]):
        super().__init__("LOCAL_PROFILE_REFUSED: " + "; ".join(issues))
        self.issues = issues


def load(profile_id: str, directory: Path | None = None) -> dict:
    import yaml

    p = (directory or PROFILE_DIR) / f"{profile_id}.yaml"
    if not p.is_file():
        raise ProfileRefused([f"PROFILE_UNKNOWN:{profile_id}"])
    raw = p.read_bytes()
    data = yaml.safe_load(raw.decode("utf-8"))
    if data.get("schema") != "forge-c/local-profile/1" or data.get("id") != profile_id:
        raise ProfileRefused([f"PROFILE_INVALID:{profile_id}"])
    return {**data, "_path": str(p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p),
            "_sha256": sha256_bytes(raw)}


def role_job_tokens(prof: dict, role: str, registry_default: int) -> int:
    """Prospective per-job capacity, not a capability receipt or mission allowance.

    Profiles without an AFO override keep the role registry unchanged. The
    controller must separately bind the profile and enforce its signed policy
    and cumulative mission. A multi-turn job may spend more than one context:
    every individual request still passes independent context admission.
    Never clamp an invalid configured envelope.
    """
    afo = prof.get("afo", {})
    if not isinstance(afo, dict):
        raise ProfileRefused(["PROFILE_ROLE_ENVELOPE_INVALID"])
    limits = afo.get("role_job_tokens", {})
    try:
        context = int(prof["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProfileRefused(["PROFILE_ROLE_ENVELOPE_INVALID"]) from exc
    if (not isinstance(limits, dict)
            or context < 1
            or not set(limits) <= {"afo-recovery-planner", "afo-factory-maintainer"}
            or any(type(n) is not int or n <= 0 for n in limits.values())):
        raise ProfileRefused(["PROFILE_ROLE_ENVELOPE_INVALID"])
    return limits.get(role, registry_default)


def semantic_configuration(manifest: dict) -> dict:
    """Resolve the existing semantic profile authority and validate new frozen bindings."""
    local = manifest.get("local_profile") or {}
    if not isinstance(local, dict):
        raise ProfileRefused(["PROFILE_BINDING_INVALID"])
    prof = load(local.get("id", "local-rtx-v2"))
    engine = prof["safec"]["engine"]
    if (engine["semantic_profile"] == "register-io-0.2" or "semantic_profile" in local) and (
            local.get("id") != prof["id"]
            or local.get("semantic_profile") != engine["semantic_profile"]
            or type(local.get("version")) is not int or local["version"] != prof["version"]
            or local.get("config") != prof["_path"]
            or local.get("config_sha256") != prof["_sha256"]):
        raise ProfileRefused(["PROFILE_BINDING_CHANGED_OR_MISSING"])
    return prof


def selection_issues(prof: dict, *, model: str, provider: str, code_model: str | None, acp_authors: str | None,
                     acp_inspectors: str | None) -> list[str]:
    """LRTX-FR-002/FR-005: combinations the local-only profile refuses instead of silently changing them."""
    issues = []
    if acp_authors or acp_inspectors:
        issues.append("PROFILE_REJECTS_ACP:" + ",".join(x for x in (acp_authors, acp_inspectors) if x))
    if provider != prof["provider"]:
        issues.append(f"PROFILE_PROVIDER_NOT_LOCAL:{provider}")
    for m in {model, code_model} - {None}:
        if m not in prof["models"]["allowed"]:
            issues.append(f"PROFILE_MODEL_NOT_ALLOWED:{m}")
    return issues


def _overlap(a: Path, b: Path) -> bool:
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def isolation_issues(prof: dict, env: dict[str, str] | None = None) -> list[str]:
    """LRTX-FR-003: every writable runtime location resolves (symlinks followed) under the profile root and outside
    the existing deployment; inherited production settings are refused; the root holds no symlink except the declared
    read-only references."""
    env = dict(os.environ if env is None else env)
    dep = prof["deployment"]
    root_s = env.get(dep["root_env"])
    if not root_s:
        return [f"PROFILE_ROOT_UNSET:{dep['root_env']}"]
    root = Path(root_s).resolve()
    existing = [Path(p).resolve() for p in prof["existing_deployment"]["roots"]]
    issues = [f"PROFILE_ROOT_OVERLAPS_DEPLOYMENT:{root}:{e}" for e in existing if _overlap(root, e)]
    for key in dep["writable_env"]:
        if not env.get(key):
            issues.append(f"PROFILE_ENV_UNSET:{key}")
            continue
        p = Path(env[key]).resolve()
        if not p.is_relative_to(root):
            issues.append(f"PROFILE_PATH_OUTSIDE_ROOT:{key}:{p}")
        issues += [f"PROFILE_PATH_IN_DEPLOYMENT:{key}:{p}" for e in existing if _overlap(p, e)]
    shared = {name: Path(t).resolve() for name, t in dep["shared_readonly"].items()}
    if root.is_dir():
        for child in root.iterdir():
            if child.is_symlink():
                tgt = child.resolve()
                if shared.get(child.name) != tgt:
                    issues.append(f"PROFILE_UNDECLARED_SYMLINK:{child.name}->{tgt}")
            elif any(_overlap(child.resolve(), e) for e in existing):
                issues.append(f"PROFILE_ALIAS_INTO_DEPLOYMENT:{child.name}")
    return issues


def endpoint_issues(prof: dict, env: dict[str, str] | None = None, fabro_config: Path | None = None) -> list[str]:
    """LRTX-FR-005: the Fabro server, its only LLM provider and the Ollama upstream are loopback endpoints on the
    profile's ports; no other provider (cloud fallback) is configured."""
    env = dict(os.environ if env is None else env)
    ports = prof["deployment"]["ports"]
    forbidden = set(prof["deployment"]["forbidden_ports"])
    issues = []

    def check(name: str, url: str | None, port: int) -> None:
        if not url:
            issues.append(f"ENDPOINT_UNSET:{name}")
            return
        u = urlparse(url)
        if u.hostname not in LOOPBACK:
            issues.append(f"ENDPOINT_NOT_LOOPBACK:{name}:{u.hostname}")
        if u.port in forbidden or u.port != port:
            issues.append(f"ENDPOINT_PORT:{name}:{u.port} (profile {port})")
    check("fabro", env.get("FORGE_FABRO_URL"), ports["fabro"])
    check("ollama", env.get("FORGE_OLLAMA_URL"), ports["ollama"])
    cfg = Path(fabro_config or env.get("FORGE_FABRO_CONFIG") or "")
    if not cfg.is_file():
        return issues + [f"FABRO_CONFIG_MISSING:{cfg}"]
    conf = tomllib.loads(cfg.read_text())
    providers = (conf.get("llm") or {}).get("providers") or {}
    enabled = sorted(k for k, v in providers.items() if v.get("enabled", True))
    if enabled != [prof["provider"]]:
        issues.append(f"FABRO_PROVIDERS_NOT_LOCAL_ONLY:{','.join(enabled) or 'none'}")
    if prof["provider"] in providers:
        check("gateway", providers[prof["provider"]].get("base_url"), ports["gateway"])
    run_model = conf.get("run", {}).get("model", {})
    if run_model.get("provider") not in (None, prof["provider"]):
        issues.append(f"FABRO_RUN_PROVIDER_NOT_LOCAL:{run_model.get('provider')}")
    listen = conf.get("server", {}).get("listen", {}).get("address", "")
    if listen.rsplit(":", 1)[0] not in LOOPBACK or not listen.endswith(f":{ports['fabro']}"):
        issues.append(f"FABRO_LISTEN:{listen}")
    return issues


def network_enforcement(probe: tuple[str, int] = EXTERNAL_PROBE, timeout: float = 2.0) -> dict:
    """Observed, not declared: does this process reach an external address at all? Only a refused route (namespace
    without an external interface) counts as DENIED_VERIFIED; a timeout is inconclusive."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(probe)
        status, detail = "NOT_ENFORCED", "external address reachable"
    except OSError as exc:
        unreachable = exc.errno in (101, 113)  # ENETUNREACH / EHOSTUNREACH: no route out of the namespace
        status, detail = ("DENIED_VERIFIED" if unreachable else "INCONCLUSIVE"), f"{type(exc).__name__}: {exc}"
    finally:
        s.close()
    try:
        ifaces = sorted(n for _i, n in socket.if_nameindex())
    except OSError:
        ifaces = []
    return {"status": status, "probe": f"{probe[0]}:{probe[1]}", "detail": detail, "interfaces": ifaces,
            "netns": os.readlink("/proc/self/ns/net") if Path("/proc/self/ns/net").exists() else None}


def model_identity(prof: dict, model: str, ollama_url: str) -> dict:
    """LRTX-FR-018/T007: the served model's digest/quantization must equal the profile's pinned identity."""
    want = prof["models"]["allowed"][model]
    try:
        with urllib.request.urlopen(ollama_url.rstrip("/") + "/api/tags", timeout=10) as r:  # noqa: S310
            tags = json.loads(r.read())
    except (OSError, ValueError) as exc:
        return {"model": model, "status": "UNREACHABLE", "detail": str(exc)}
    got = next((m for m in tags.get("models") or [] if m.get("name") == model), None)
    if got is None:
        return {"model": model, "status": "MISSING"}
    q = (got.get("details") or {}).get("quantization_level")
    ok = got.get("digest") == want["digest"] and q == want["quantization"]
    return {"model": model, "status": "MATCH" if ok else "MISMATCH", "digest": got.get("digest"), "quantization": q,
            "size": got.get("size"), "expected_digest": want["digest"], "role_qualification": want["role_qualification"]}


def runtime_record(env: dict[str, str] | None = None) -> dict:
    """The service launcher's record of the effective local runtime (no secrets), or UNKNOWN."""
    env = dict(os.environ if env is None else env)
    root = env.get("FORGE_LRTX_ROOT")
    p = Path(root) / "run/services.json" if root else None
    if p is None or not p.is_file():
        return {"status": "UNKNOWN", "reason": "no services.json from scripts/forge_lrtx.sh"}
    return {"status": "RECORDED", **json.loads(p.read_text())}


def select(profile_id: str, *, model: str, provider: str, code_model: str | None, acp_authors: str | None,
           acp_inspectors: str | None, env: dict[str, str] | None = None, require_network_denied: bool = True) -> dict:
    """All pre-launch checks; returns the provenance record (T007) or raises ProfileRefused."""
    prof = load(profile_id)
    env = dict(os.environ if env is None else env)
    issues = selection_issues(prof, model=model, provider=provider, code_model=code_model, acp_authors=acp_authors,
                              acp_inspectors=acp_inspectors)
    if issues:  # cheap refusals first, before touching the host
        raise ProfileRefused(issues)
    issues = isolation_issues(prof, env) + endpoint_issues(prof, env)
    net = network_enforcement()
    if require_network_denied and prof.get("network", {}).get("required") == "namespace_denied" \
            and net["status"] != "DENIED_VERIFIED":
        issues.append(f"NETWORK_NOT_DENIED:{net['status']}")
    models = [model_identity(prof, m, env.get("FORGE_OLLAMA_URL", "")) for m in sorted({model, code_model} - {None})]
    issues += [f"MODEL_IDENTITY_{m['status']}:{m['model']}" for m in models if m["status"] != "MATCH"]
    if issues:
        raise ProfileRefused(issues)
    record = {"id": prof["id"], "version": prof["version"], "status": prof["status"], "config": prof["_path"],
            "config_sha256": prof["_sha256"], "local_only": True, "provider": prof["provider"], "models": models,
            "runtime": runtime_record(env), "admission": prof["admission"],
            "timeout_scale": prof["runtime"]["timeout_scale"],
            "enforcement": {"acp": "REJECTED_BEFORE_LAUNCH", "fabro_providers": [prof["provider"]],
                            "endpoints": "LOOPBACK_VERIFIED", "isolation": "VERIFIED", "network": net,
                            "basis": "checked by forge_factory.lrtx.profile.select at launch; a declared provider "
                                     "name alone is not enforcement"},
            "roots": {k: str(Path(env[k]).resolve()) for k in prof["deployment"]["writable_env"]},
            "qualification": "NOT_QUALIFIED (feature 010 acceptance pending)"}
    semantic = ((prof.get("safec") or {}).get("engine") or {}).get("semantic_profile")
    if semantic == "register-io-0.2":
        # The frozen marker makes a later profile downgrade detectable too.
        record["semantic_profile"] = semantic
    return record
