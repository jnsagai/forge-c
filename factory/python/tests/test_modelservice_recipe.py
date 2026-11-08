"""Feature 017 T039 (and recipe checks): the model tier's deployment files keep the service private and pinned."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from model_tier import catalog as C

ROOT = Path(__file__).resolve().parents[3]
TIER = ROOT / "deploy/recipe/model-tier"


def _compose():
    return yaml.safe_load((TIER / "compose.yaml").read_text())


def test_engines_are_private_pinned_and_log_nothing():
    doc = _compose()
    for name, svc in doc["services"].items():
        assert re.fullmatch(r".+@sha256:[0-9a-f]{64}", svc["image"]), name  # digest-pinned (FR-017)
        for p in svc.get("ports", []):
            assert str(p).startswith("127.0.0.1:"), f"{name} publishes {p} beyond loopback"
        cmd = " ".join(svc.get("command", []))
        assert "--enable-log-requests" not in cmd and "--enable-log-outputs" not in cmd  # request logging off
        assert "--api-key=${FORGE_MODEL_TIER_ENGINE_KEY" in cmd  # engines refuse callers without the internal key
        assert svc.get("restart") == "no"  # only the swap controller starts engines
    q = doc["services"]["engine-qwen36"]
    assert "--enable-sleep-mode" in q["command"] and "--enable-prefix-caching" in q["command"]
    assert q["devices"] == ["nvidia.com/gpu=all"] and q["ulimits"]["memlock"] == -1
    assert all(v.endswith(":ro") for v in q["volumes"] if "/models/" in v)  # weights mounted read-only


def test_only_engine_services_get_the_gpu():
    for name, svc in _compose()["services"].items():
        if svc.get("devices"):
            assert name.startswith("engine-"), name


def test_tenant_example_validates_and_holds_no_secret():
    doc = yaml.safe_load((TIER / "tenants.example.yaml").read_text())
    C.validate(doc, "tenant-config.schema.json")
    assert {t["tenant_id"] for t in doc["tenants"]} == {"forge-qual", "forge-owner", "sim-neighbour"}
    assert next(t for t in doc["tenants"] if t["tenant_id"] == "forge-owner")["enabled"] is False  # until cutover (FR-020)


def test_recipe_tree_holds_no_secret():
    pat = re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}", re.I)
    for p in (ROOT / "deploy/recipe").rglob("*"):
        if p.is_file() and p.suffix in (".yaml", ".yml", ".json", ".sh", ".service", ".md", ".hcl", "") and p.stat().st_size < 2e6:
            for line in p.read_text(errors="replace").splitlines():
                assert not pat.search(line) or "${" in line or "_ref" in line or "sha256" in line, f"{p}: {line}"
    assert "secrets*" in (ROOT / "deploy/recipe/.gitignore").read_text()


def test_gateway_unit_is_not_enabled_by_default_and_keeps_files_private():
    unit = (TIER / "tenant-gateway.service").read_text()
    assert "Restart=no" in unit and "UMask=0077" in unit and "127.0.0.1:18480" in unit
    df = (TIER / "gateway.Dockerfile").read_text()
    assert re.search(r"^FROM .+@sha256:[0-9a-f]{64}$", df, re.M) and "sha256:" + "0" * 64 not in df
    assert "forge_factory" not in df.replace("factory/python/model_tier", "")  # the image holds no factory code


@pytest.mark.skipif(shutil.which("docker") is None, reason="NOT_RUN: docker absent on this machine")
def test_compose_config_is_valid():
    r = subprocess.run(["docker", "compose", "-f", str(TIER / "compose.yaml"), "config", "--quiet"], capture_output=True, text=True,
                       env={**os.environ, "FORGE_MODEL_TIER_ENGINE_KEY": "x"}, timeout=60, check=False)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["docker", "compose", "-f", str(TIER / "compose.yaml"), "config", "--quiet"], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != "FORGE_MODEL_TIER_ENGINE_KEY"}, timeout=60, check=False)
    assert r.returncode != 0  # refuses to start engines without the internal key


def test_params_files_validate():
    for site in ("omniverse2", "production"):
        C.validate(yaml.safe_load((ROOT / f"deploy/recipe/params/{site}.yaml").read_text()), "recipe-params.schema.json")
    assert json.loads((ROOT / "deploy/recipe/recipe.lock.json").read_text())["fabro_version"] == "0.362.0"
