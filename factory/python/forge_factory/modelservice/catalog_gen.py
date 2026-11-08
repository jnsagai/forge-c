# ruff: noqa: E501
"""Generate the model tier's catalog for a site (feature 017, T035; FR-025, FR-032).

Factory side on purpose: the model tier never reads a factory profile. This generator turns the owner lane's
profile into an explicit engine entry for Ornith (the same llama.cpp server and the same full-capacity arguments
as today, produced by `lrtx.stack.llama_server_spec`), adds the production reference model from the recipe lock,
pins both identities in the lock, and writes a catalog that validates against the model-catalog schema.

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

ORNITH_PORT, QWEN_PORT = 18501, 18502
QWEN = "qwen3.6-35b-a3b-fp8"


def _flag(argv: list[str], name: str) -> str | None:
    return argv[argv.index(name) + 1] if name in argv else None


def ornith_entry(prof: dict, root: Path, lock: dict, *, port: int = ORNITH_PORT, spec=None) -> dict:
    """The owner lane's llama.cpp server as a catalog entry: identical arguments except the model path (a
    placeholder the engine fills with the RAM-staged copy) and the internal port."""
    spec = spec or stack.llama_server_spec
    argv, env, _health, models = spec(Path(root), prof, {"llama": port}, {})
    name = models[0]
    binary, args = argv[0], list(argv[1:])
    model_path = args[args.index("--model") + 1]
    args[args.index("--model") + 1] = "{model_path}"
    args[args.index("--port") + 1] = str(port)
    files = ((lock.get("model_files") or {}).get("ornith-1.5-35b-a3b-q8") or {}).get("files") or []
    blob_sha = files[0]["sha256"] if files else Path(model_path).name.removeprefix("sha256-")
    ctx, seqs = int(_flag(args, "-c")), int(_flag(args, "-np") or 1)
    reasoning = "on" if _flag(args, "--reasoning") in ("on", "auto") else "off"
    ident = I.build(name=name, revision_fingerprint=I.fingerprint_entries([(Path(model_path).name, blob_sha)], None, None),
                    precision="other", reasoning_mode=reasoning, context_limit=ctx // seqs,
                    engine={"name": "llama.cpp", "version": "ollama-0.34.0-bundled"}, attested=True,
                    kv_cache_dtype=_flag(args, "--cache-type-k"), max_sequences=seqs)
    return {"model": name, "engine": "llama.cpp", "launch_kind": "process", "engine_url": f"http://127.0.0.1:{port}",
            "full_capacity": {"context_per_sequence": ctx // seqs, "sequences": seqs, "kv_cache_type": _flag(args, "--cache-type-k"),
                              "batch_tokens": int(_flag(args, "-b") or 2048), "microbatch_tokens": int(_flag(args, "-ub") or 2048)},
            "reasoning_mode": reasoning, "identity": ident, "vram_mib": 42000, "load_timeout_s": 300,
            "warm_strategy": "ram_staged_file", "ram_gib": round(Path(model_path).stat().st_size / 2**30 + 0.5, 1)
            if Path(model_path).exists() else 36.0,
            "process": {"binary": binary, "args": args, "env": {k: v for k, v in env.items() if k in ("LD_LIBRARY_PATH", "GGML_BACKEND_PATH")},
                        "model_path": model_path, "model_sha256": blob_sha}}


def qwen_entry(lock: dict, params: dict, *, port: int = QWEN_PORT) -> dict:
    rec = (lock.get("model_files") or {}).get(QWEN)
    if not rec or not rec.get("files"):
        raise RuntimeError(f"NOT_PINNED_YET:{QWEN}")
    v = {k: p["value"] for k, p in params["parameters"].items()}
    ctx, seqs = int(v["reference_context"]), int(v["reference_sequences"])
    ident = I.build(name=QWEN, revision_fingerprint=I.fingerprint_entries([(f["path"], f["sha256"]) for f in rec["files"]], None, None),
                    precision="fp8", reasoning_mode="off", context_limit=ctx,
                    engine={"name": "vllm", "version": "0.32.0", "image_digest": (lock.get("images") or {}).get("vllm-openai")},
                    attested=True, max_sequences=seqs)
    if ident["engine"]["image_digest"] is None:
        ident["engine"].pop("image_digest")
    size = sum(f["bytes"] for f in rec["files"])
    return {"model": QWEN, "engine": "vllm", "launch_kind": "compose", "compose_service": "engine-qwen36",
            "engine_url": f"http://127.0.0.1:{port}",
            "full_capacity": {"context_per_sequence": ctx, "sequences": seqs, "gpu_memory_utilization": 0.90, "prefix_caching": True},
            "reasoning_mode": "off", "identity": ident, "vram_mib": 44500, "load_timeout_s": 900,
            "warm_strategy": "vllm_sleep", "ram_gib": round(size / 2**30 + 1.0, 1)}


def generate(*, prof: dict, root: Path, lock_path: Path, params_path: Path, out: Path, spec=None) -> dict:
    lock = json.loads(Path(lock_path).read_text())
    params = yaml.safe_load(Path(params_path).read_text())
    v = {k: p["value"] for k, p in params["parameters"].items()}
    models = [qwen_entry(lock, params), ornith_entry(prof, root, lock, spec=spec)]  # vLLM first: it needs a free GPU to start
    doc = {"site": params["site"], "gpu_vram_mib": int(v["gpu_vram_mib"]), "compose_file": "compose.yaml",
           "compose_project": "forge-model-tier", "models": models,
           "swap_policy": {"drain_max_s": 600, "min_residency_s": 120, "swap_after_wait_s": 30, "max_wait_s": 600,
                           "max_swaps_per_hour": 30, "ram_budget_gib": float(v["ram_budget_gib"]),
                           "ram_reserve_gib": float(v["ram_reserve_gib"]), "stage_dir": "/dev/shm/forge-model-tier"}}
    lock.setdefault("identities", {}).update({m["model"]: m["identity"] for m in models})
    Path(lock_path).write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    C.parse(doc, lock)  # schema, launch fields and identities must all hold before anything is written
    Path(out).write_text("# Generated by forge_factory.modelservice.catalog_gen (feature 017). Do not edit by hand:\n"
                         "# swap_policy values are first estimates until the first window measures them (T043).\n"
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
