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


def onboarding_dir(key: str) -> Path:
    """Packages are keyed by the onboarding work order's example name, so every attempt and request of that work
    order (AFO -a1, -a2 ...) uses the same owner-approved package: state/onboarding/<key>/onboarding/..."""
    return state_dir() / "onboarding" / key


def intake_check(repo: Path, launch_manifest: dict) -> str | None:
    """AFO intake (FR-016): None when the launch manifest's work order is not an onboarding one or its package is
    approved; otherwise the refusal code."""
    import json

    from .approval import verify

    ex = Path(repo) / launch_manifest.get("example", "")
    try:
        spec = json.loads((ex / "workorder.json").read_text())
    except (OSError, ValueError):
        return None
    if not (spec.get("delivery") or {}).get("onboarding"):
        return None
    r = verify(onboarding_dir(ex.name))
    return None if r["code"] == "APPROVAL_OK" else f"{r['code']}:{ex.name}"


def _revision() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                              text=True, timeout=20).stdout.strip() or "0000000"
    except (OSError, subprocess.SubprocessError):
        return "0000000"


def derive(example: Path, wo: str | None = None) -> dict:
    """OB-T017: the deterministic part of onboarding - identity and behaviour facts, assumptions, gaps - written as
    `state/workorders/<wo>/onboarding/package.json`. No model is called (FR-022); profile and texts are added by
    the later slices from these facts."""
    from . import behaviour as B
    from . import facts as F
    from . import identity as I

    wo = wo or Path(example).name
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
    root = onboarding_dir(wo)
    old = F.read_package(root)
    if old is not None and old["sha256"] != pkg["sha256"]:  # FR-017: a changed input or fact voids the approval
        from .approval import invalidate

        changed = sorted({i["path"] for i in pkg["inputs"]} ^ {i["path"] for i in old["inputs"]} |
                         {i["path"] for i in pkg["inputs"] for j in old["inputs"]
                          if i["path"] == j["path"] and i["sha256"] != j["sha256"]})
        invalidate(root, f"package {old['sha256']} replaced by {pkg['sha256']}; changed inputs: "
                         f"{', '.join(changed[:20]) or 'none (facts or factory revision)'}")
    F.write_package(root, pkg)
    return pkg


class OnboardingNotApproved(ValueError):
    """SWE work may not start: the work order's onboarding package has no verified owner approval (FR-016)."""


def admit(wo: str, spec: dict) -> tuple[dict, dict, dict]:
    """(package, approval, derived profile) of an approved onboarding work order, the profile written as
    state/workorders/<wo>/onboarding/profile.json; raises OnboardingNotApproved otherwise (code in the message)."""
    from . import facts as F
    from .approval import verify
    from .profile import ProfileIncomplete, derived_profile, write

    root = onboarding_dir(wo)
    pkg = F.read_package(root)
    if pkg is None:
        raise OnboardingNotApproved("ONBOARDING_NOT_APPROVED:no package (run the derivation)")
    r = verify(root)
    if r["code"] != "APPROVAL_OK":
        raise OnboardingNotApproved(f"ONBOARDING_NOT_APPROVED:{r['code']}:{r['reason']}")
    try:
        prof = derived_profile(pkg, r["approval"], (spec.get("system_names") or [None])[0])
    except ProfileIncomplete as e:
        raise OnboardingNotApproved(f"ONBOARDING_NOT_APPROVED:{e}") from e
    write(root, prof)
    return pkg, r["approval"], prof


def delivery_from_package(spec: dict, pkg: dict) -> dict:
    """The work order's delivery block with the approved file map; a hand-written map that differs is refused."""
    from .facts import value

    d = dict(spec["delivery"])
    fm = value(pkg, "file_map")
    files = [{"from": f["from"], "to": f["to"]} for f in fm["files"]]
    deps = [{k: v for k, v in x.items() if k in ("from", "to", "origin", "licence", "source", "configure")}
            for x in fm["dependencies"]]
    for key, got in (("files", files), ("dependencies", deps)):
        if d.get(key) is not None and sorted((x["from"], x["to"]) for x in d[key]) != \
                sorted((x["from"], x["to"]) for x in got):
            raise OnboardingNotApproved(f"ONBOARDING_FILE_MAP_CONFLICT:{key} differs from the approved package")
    d["files"], d["dependencies"] = files, deps
    return d
