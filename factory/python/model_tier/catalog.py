"""Model catalog of the model service (feature 017, FR-025, data-model ModelCatalogEntry/SwapPolicy).

The catalog is the only description of the models: engine, launch arguments, full-capacity settings, warm
strategy and pinned identity. It is validated against its schema and, when a recipe lock is given, every model's
identity must equal the pinned one, or the service refuses to start.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import identity as I

SCHEMAS = Path(__file__).resolve().parent / "schemas"


class CatalogError(RuntimeError):
    pass


@dataclass(frozen=True)
class Model:
    model: str
    engine: str
    launch_kind: str
    engine_url: str
    full_capacity: dict
    reasoning_mode: str
    identity: dict
    vram_mib: int
    load_timeout_s: int
    warm_strategy: str = "none"
    ram_gib: float = 0.0
    compose_service: str | None = None
    process: dict | None = None
    served_name: str | None = None

    @property
    def sequences(self) -> int:
        return int(self.full_capacity["sequences"])

    @property
    def context(self) -> int:
        return int(self.full_capacity["context_per_sequence"])

    @property
    def name_on_engine(self) -> str:
        return self.served_name or self.model


@dataclass(frozen=True)
class SwapPolicy:
    drain_max_s: int
    min_residency_s: int
    swap_after_wait_s: int
    max_wait_s: int
    max_swaps_per_hour: int
    idle_unload_s: int | None = None
    ram_budget_gib: float = 0.0
    ram_reserve_gib: float = 0.0
    stage_dir: str | None = None


@dataclass
class Catalog:
    site: str
    gpu_vram_mib: int
    models: dict[str, Model]
    policy: SwapPolicy
    compose_file: str | None = None
    compose_project: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def min_sequences(self) -> int:
        return min(m.sequences for m in self.models.values())

    @property
    def max_sequences(self) -> int:
        return max(m.sequences for m in self.models.values())


def _validator(name: str):
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    schemas = {p.name: json.loads(p.read_text()) for p in SCHEMAS.glob("*.schema.json")}
    reg = Registry().with_resources([(n, Resource.from_contents(s)) for n, s in schemas.items()] +
                                    [(s["$id"], Resource.from_contents(s)) for s in schemas.values() if "$id" in s])
    return Draft202012Validator(schemas[name], registry=reg)


def validate(doc: dict, schema: str) -> None:
    errors = sorted(_validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        raise CatalogError("SCHEMA_INVALID:" + "; ".join(f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors[:5]))


def parse(doc: dict, lock: dict | None = None) -> Catalog:
    validate(doc, "model-catalog.schema.json")
    models = {}
    for m in doc["models"]:
        if m["model"] in models:
            raise CatalogError(f"DUPLICATE_MODEL:{m['model']}")
        if m["launch_kind"] == "process" and not m.get("process"):
            raise CatalogError(f"PROCESS_LAUNCH_WITHOUT_PROCESS:{m['model']}")
        if m["launch_kind"] == "compose" and not (m.get("compose_service") and doc.get("compose_file")):
            raise CatalogError(f"COMPOSE_LAUNCH_WITHOUT_SERVICE:{m['model']}")
        if m.get("warm_strategy") == "vllm_sleep" and m["engine"] != "vllm":
            raise CatalogError(f"VLLM_SLEEP_ON_{m['engine'].upper()}:{m['model']}")
        if m["identity"]["name"] != m["model"]:
            raise CatalogError(f"IDENTITY_NAME_MISMATCH:{m['model']}")
        if lock is not None:
            I.require_match(I.from_lock(lock, m["model"]), m["identity"])
        models[m["model"]] = Model(**{k: m[k] for k in Model.__dataclass_fields__ if k in m})
    co = [m for m in doc["models"] if m.get("co_resident")]
    if sum(m["vram_mib"] for m in co) > doc["gpu_vram_mib"]:
        raise CatalogError("CO_RESIDENT_MODELS_EXCEED_GPU")
    for m in models.values():
        if m.vram_mib > doc["gpu_vram_mib"]:
            raise CatalogError(f"MODEL_EXCEEDS_GPU:{m.model}")
    return Catalog(site=doc["site"], gpu_vram_mib=doc["gpu_vram_mib"], models=models, policy=SwapPolicy(**doc["swap_policy"]),
                   compose_file=doc.get("compose_file"), compose_project=doc.get("compose_project"), raw=doc)


def load(path: Path, lock_path: Path | None = None) -> Catalog:
    lock = json.loads(Path(lock_path).read_text()) if lock_path else None
    return parse(yaml.safe_load(Path(path).read_text()), lock)
