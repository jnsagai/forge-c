"""Feature 016: peripheral onboarding as a factory stage before SWE.1.

    python -m forge_factory.onboarding derive <example> <WO> [--no-author]   # deterministic facts -> package
    python -m forge_factory.onboarding summary <WO>                          # owner review page
    python -m forge_factory.onboarding verify <WO>                           # owner-signed approval check
    python -m forge_factory.onboarding prompts <WO> --check                  # generated instructions + leftovers
    python -m forge_factory.onboarding check-model <peripheral>              # simulation model gate

The derivation makes no model call (FR-022); unknowns are NOT_DERIVED, disagreements CONFLICT (FR-005)."""
from __future__ import annotations
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, sha256_bytes, state_dir


def onboarding_dir(wo: str) -> Path:
    return state_dir() / "workorders" / wo


def _revision() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                              text=True, timeout=20).stdout.strip() or "0000000"
    except (OSError, subprocess.SubprocessError):
        return "0000000"


def derive(example: Path, wo: str) -> dict:
    """OB-T017: the deterministic part of onboarding - identity and behaviour facts, assumptions, gaps - written as
    `state/workorders/<wo>/onboarding/package.json`. No model is called (FR-022); profile and texts are added by
    the later slices from these facts."""
    from . import behaviour as B
    from . import facts as F
    from . import identity as I

    ctx = I.context(Path(example))
    facts, ident = I.derive(ctx)
    style_f = next((f for f in facts if f.name == "driver_style"), None)
    style = style_f.value if style_f and style_f.status == "DERIVED" else None
    asm, dmap, missing = [], {}, []
    if style:
        bf, asm, dmap = B.derive(ctx, ident, style)
        facts += bf
        missing = [(n, "the delivered code needs it to build; no package of the work order declares it")
                   for n in dmap.get("missing") or []]
        if not dmap.get("files"):
            missing = missing or [("file_map", "the delivered code does not build from the inputs")]
    inputs = I.input_records(ctx)
    for f in dmap.get("files") or []:
        inputs.append({"path": f["to"], "role": "delivered_code",
                       "sha256": sha256_bytes((ctx.source / f["from"]).read_bytes())})
    for d in dmap.get("dependencies") or []:
        inputs.append({"path": d["to"], "role": "delivered_dependency",
                       "sha256": sha256_bytes((Path(d["package"]) / d["from"]).read_bytes())})
    profile = {"derived_from": {"work_order": wo, "example": Path(example).name}}
    pkg = F.assemble(wo, inputs, _revision(), style or "LL", facts, [], asm, profile, {}, missing)
    F.write_package(onboarding_dir(wo), pkg)
    return pkg
