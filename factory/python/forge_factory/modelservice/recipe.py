# ruff: noqa: E501
"""The deployment recipe's command line (feature 017, US4; FR-017, FR-018, SC-004, SC-008).

    python -m forge_factory.modelservice.recipe plan   --site omniverse2|production
    python -m forge_factory.modelservice.recipe verify --site omniverse2 [--quick]
    python -m forge_factory.modelservice.recipe drift  --site omniverse2
    python -m forge_factory.modelservice.recipe apply  --site omniverse2 [--execute]

* plan   - every site parameter with its production counterpart and whether it is confirmed; secrets by name only.
* verify - every pinned artefact against the lock: model files by sha256 (or size with --quick), image digests,
           identity fingerprints recomputed from the pinned files. Exits non-zero naming the first mismatch.
* drift  - a running environment against the lock: engine image of each running engine container, the factory
           revision, and the catalog identities.
* apply  - brings up the model tier from the recipe. On Omniverse2 it refuses outside a qualification window
           (FR-019): the window controller exports FORGE_017_WINDOW_ID while it holds the GPU. Without --execute it
           only prints the commands it would run.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml
from model_tier import catalog as C
from model_tier import identity as I

from .artefacts import sha256_file

ROOT = Path(__file__).resolve().parents[4]
RECIPE = ROOT / "deploy/recipe"


class RecipeError(RuntimeError):
    pass


def params(site: str, recipe: Path = RECIPE) -> dict:
    doc = yaml.safe_load((recipe / "params" / f"{site}.yaml").read_text())
    C.validate(doc, "recipe-params.schema.json")
    return doc


def plan(site: str, recipe: Path = RECIPE) -> dict:
    doc = params(site, recipe)
    rows = []
    for name, p in doc["parameters"].items():
        value = f"<secret:{p['value']}>" if p.get("secret_ref") else p["value"]
        rows.append({"name": name, "value": value, "production_value": p.get("production_value"),
                     "confirmed": p.get("confirmed", True), "description": p["description"]})
    return {"site": site, "parameters": rows, "unconfirmed": [r["name"] for r in rows if not r["confirmed"]],
            "not_proven_here": doc.get("not_proven_here") or []}


def _lock(recipe: Path) -> dict:
    return json.loads((recipe / "recipe.lock.json").read_text())


def verify(recipe: Path = RECIPE, *, quick: bool = False, run=subprocess.run) -> list[str]:
    """Problems found (empty = everything matches the lock)."""
    lock, problems = _lock(recipe), []
    for model, rec in (lock.get("model_files") or {}).items():
        root = Path(rec.get("root") or "")
        for f in rec.get("files") or []:
            p = root / f["path"]
            if not p.is_file():
                problems.append(f"MISSING:{model}:{f['path']}")
            elif p.stat().st_size != f["bytes"]:
                problems.append(f"SIZE_MISMATCH:{model}:{f['path']}")
            elif not quick and sha256_file(p) != f["sha256"]:
                problems.append(f"SHA256_MISMATCH:{model}:{f['path']}")
        ident = (lock.get("identities") or {}).get(model)
        if ident and rec.get("files"):
            entries = [(f["path"], f["sha256"]) for f in rec["files"]]
            if I.fingerprint_entries(entries, None, None) != ident["revision_fingerprint"]:
                problems.append(f"IDENTITY_FINGERPRINT_MISMATCH:{model}")
    for name, digest in (lock.get("images") or {}).items():
        if not name.startswith(("vllm", "python")):  # binaries and cloud images are hashed files, not docker images
            continue
        ref = f"vllm/vllm-openai@{digest}" if name.startswith("vllm") else f"python@{digest}"
        r = run(["docker", "image", "inspect", ref, "--format", "{{.Id}}"], capture_output=True, text=True, check=False)
        if r.returncode != 0:
            problems.append(f"IMAGE_MISSING:{name}")
    return problems


def drift(recipe: Path = RECIPE, *, run=subprocess.run) -> list[dict]:
    lock, out = _lock(recipe), []
    want = (lock.get("images") or {}).get("vllm-openai")
    r = run(["docker", "ps", "--filter", "label=com.docker.compose.project=forge-model-tier", "--format", "{{.Names}} {{.Image}}"],
            capture_output=True, text=True, check=False)
    for line in (r.stdout or "").splitlines():
        name, _, image = line.partition(" ")
        if want and not image.endswith(want):
            out.append({"component": name, "expected": want, "actual": image, "severity": "HIGH"})
    rev = run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    if lock.get("factory_revision") and rev and rev != lock["factory_revision"]:
        out.append({"component": "factory_revision", "expected": lock["factory_revision"], "actual": rev, "severity": "MEDIUM"})
    cat_path = recipe / "model-tier/catalog.yaml"
    if cat_path.is_file():
        try:
            C.load(cat_path, recipe / "recipe.lock.json")
        except Exception as exc:  # noqa: BLE001 - reported as drift, not raised
            out.append({"component": "catalog", "expected": "identities as locked", "actual": str(exc)[:200], "severity": "HIGH"})
    return out


def apply_commands(site: str, recipe: Path = RECIPE) -> list[str]:
    tier = recipe / "model-tier"
    return [f"python -m forge_factory.modelservice.recipe verify --site {site} --quick",
            f"systemd-run --user --unit forge-model-tier-gateway --collect -p Restart=no -p UMask=0077 "
            f"--working-directory={ROOT} {sys.executable} -m model_tier.tenant_gateway --config {tier}/tenants.yaml "
            f"--secrets /mnt/data/forge-c/model-service/secrets/model-service.secrets --listen 127.0.0.1:18480 "
            f"--state /mnt/data/forge-c/model-service/tier-state"]


def apply(site: str, recipe: Path = RECIPE, *, execute: bool = False, run=subprocess.run) -> list[str]:
    if site == "omniverse2" and not os.environ.get("FORGE_017_WINDOW_ID"):
        raise RecipeError("APPLY_OUTSIDE_WINDOW: the model tier may use the Omniverse2 GPU only inside a qualification window (FR-019)")
    if not (recipe / "model-tier/tenants.yaml").is_file():
        raise RecipeError("TENANTS_NOT_CONFIGURED: deploy/recipe/model-tier/tenants.yaml (from tenants.example.yaml, hashes only)")
    if not (recipe / "model-tier/catalog.yaml").is_file():
        raise RecipeError("CATALOG_NOT_GENERATED: run forge_factory.modelservice.catalog_gen first")
    cmds = apply_commands(site, recipe)
    if execute:
        problems = verify(recipe, quick=True, run=run)
        if problems:
            raise RecipeError("VERIFY_FAILED:" + ",".join(problems[:5]))
        r = run(cmds[1], shell=True, capture_output=True, text=True, check=False)  # noqa: S604 - fixed command built above
        if r.returncode != 0:
            raise RecipeError(f"APPLY_FAILED:{r.returncode}")
    return cmds


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="recipe")
    ap.add_argument("cmd", choices=["plan", "verify", "drift", "apply"])
    ap.add_argument("--site", required=True, choices=["omniverse2", "production"])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "plan":
            print(json.dumps(plan(a.site), indent=1))
        elif a.cmd == "verify":
            problems = verify(quick=a.quick)
            print(json.dumps({"problems": problems}))
            return 1 if problems else 0
        elif a.cmd == "drift":
            found = drift()
            print(json.dumps({"drift": found}, indent=1))
            return 1 if found else 0
        else:
            print("\n".join(apply(a.site, execute=a.execute)))
    except RecipeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
