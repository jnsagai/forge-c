# ruff: noqa: E501
"""Generate the model tier's catalog for a site (feature 017, T035; FR-025, FR-032).

Factory side on purpose: the model tier never reads a factory profile. The Omniverse2 catalog is exactly the models
the owner lane uses today (owner 2026-11-08: "we don't work with qwen 3.6 here"): the profile's llama.cpp model and
its alternates, each with the same full-capacity arguments as today (produced by `lrtx.stack.llama_server_spec`),
with only the model path (the engine fills it) and the internal port changed. Identities are pinned in the lock.

    python -m forge_factory.modelservice.catalog_gen --profile <id> --lock deploy/recipe/recipe.lock.json \
        --params deploy/recipe/params/omniverse2.yaml --out deploy/recipe/model-tier/catalog.yaml
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from model_tier import catalog as C
from model_tier import identity as I

from ..lrtx import stack

BASE_PORT = 18501


def _flag(argv: list[str], name: str) -> str | None:
    return argv[argv.index(name) + 1] if name in argv else None


def lane_models(prof: dict) -> list[str]:
    rt = prof.get("runtime") or {}
    primary = (rt.get("llama_server") or {}).get("model")
    return [m for m in [primary, *(rt.get("llama_server_alternates") or {})] if m]


def entry(prof: dict, root: Path, lock: dict, model: str, *, port: int, spec=None) -> dict:
    """One lane model as a catalog entry: identical llama.cpp arguments except the model path and the port."""
    spec = spec or stack.llama_server_spec
    argv, env, _health, models = spec(Path(root), prof, {"llama": port}, {}, model)
    name = models[0]
    binary, args = argv[0], list(argv[1:])
    model_path = args[args.index("--model") + 1]
    args[args.index("--model") + 1] = "{model_path}"
    args[args.index("--port") + 1] = str(port)
    blob_sha = Path(model_path).name.removeprefix("sha256-")
    pinned = ((lock.get("model_files") or {}).get(name) or {}).get("files") or []
    if pinned and pinned[0]["sha256"] != blob_sha:
        raise RuntimeError(f"LOCK_DISAGREES_WITH_PROFILE:{name}")
    ctx, seqs = int(_flag(args, "-c")), int(_flag(args, "-np") or 1)
    reasoning = "on" if _flag(args, "--reasoning") in ("on", "auto") else "off"
    ls = (prof["runtime"].get("llama_server_alternates") or {}).get(name) or prof["runtime"]["llama_server"]
    size = Path(model_path).stat().st_size if Path(model_path).exists() else int((pinned[0] if pinned else {}).get("bytes") or 0)
    ident = I.build(name=name, revision_fingerprint=I.fingerprint_entries([(Path(model_path).name, blob_sha)], None, None),
                    precision="other", reasoning_mode=reasoning, context_limit=ctx // seqs,
                    engine={"name": "llama.cpp", "version": "ollama-0.34.0-bundled"}, attested=True,
                    kv_cache_dtype=_flag(args, "--cache-type-k"), max_sequences=seqs)
    full = {"context_per_sequence": ctx // seqs, "sequences": seqs, "kv_cache_type": _flag(args, "--cache-type-k"),
            "batch_tokens": int(_flag(args, "-b") or 2048), "microbatch_tokens": int(_flag(args, "-ub") or 2048)}
    if _flag(args, "--spec-draft-n-max"):
        full["mtp_draft"] = int(_flag(args, "--spec-draft-n-max"))
    return {"model": name, "engine": "llama.cpp", "launch_kind": "process", "engine_url": f"http://127.0.0.1:{port}",
            "full_capacity": full, "reasoning_mode": reasoning, "identity": ident,
            "vram_mib": int(ls.get("vram_required_mib") or 46000), "load_timeout_s": 600,
            "warm_strategy": "page_cache", "ram_gib": round(size / 2**30 + 0.5, 1),
            "process": {"binary": binary, "args": args,
                        "env": {k: v for k, v in env.items() if k in ("LD_LIBRARY_PATH", "GGML_BACKEND_PATH")},
                        "model_path": model_path, "model_sha256": blob_sha}}


def generate(*, prof: dict, root: Path, lock_path: Path, params_path: Path, out: Path, spec=None) -> dict:
    lock = json.loads(Path(lock_path).read_text())
    params = yaml.safe_load(Path(params_path).read_text())
    v = {k: p["value"] for k, p in params["parameters"].items()}
    names = lane_models(prof)
    if not names:
        raise RuntimeError("PROFILE_HAS_NO_LLAMA_SERVER_MODELS")
    models = [entry(prof, root, lock, m, port=BASE_PORT + i, spec=spec) for i, m in enumerate(names)]
    doc = {"site": params["site"], "gpu_vram_mib": int(v["gpu_vram_mib"]), "models": models,
           "swap_policy": {"drain_max_s": 600, "min_residency_s": 120, "swap_after_wait_s": 30, "max_wait_s": 900,
                           "max_swaps_per_hour": 30, "ram_budget_gib": float(v["ram_budget_gib"]),
                           "ram_reserve_gib": float(v["ram_reserve_gib"]), "stage_dir": "/dev/shm/forge-model-tier"}}
    lock.setdefault("identities", {}).update({m["model"]: m["identity"] for m in models})
    C.parse(doc, lock)  # schema, launch fields and identities must all hold before anything is written
    Path(lock_path).write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    Path(out).write_text("# Generated by forge_factory.modelservice.catalog_gen (feature 017). Do not edit by hand:\n"
                         "# swap_policy values are first estimates until the first window measures them.\n"
                         + yaml.safe_dump(doc, sort_keys=False, width=140))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="catalog_gen")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--lock", required=True, type=Path)
    ap.add_argument("--params", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    s = stack.settings(a.profile)
    doc = generate(prof=s["profile"], root=s["root"], lock_path=a.lock, params_path=a.params, out=a.out)
    print(json.dumps({"models": [m["model"] for m in doc["models"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
