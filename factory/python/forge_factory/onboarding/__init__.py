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


def derive(example: Path, wo: str | None = None, gate_model: bool = True) -> dict:
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
    if style:
        from .api import api

        facts.append(api(ctx, style))
    profile = {"derived_from": {"work_order": wo, "example": Path(example).name}}
    pkg = F.assemble(wo, inputs, _revision(), style or "LL", facts, [], asm, profile, {}, missing)
    if style and not missing:  # OB-T031: the prompt texts from facts, owner scope and the model description
        from .texts import TextsUnavailable, generate

        try:
            texts = generate(ctx, pkg)
        except TextsUnavailable as e:
            texts, missing = {}, [*missing, (str(e), "the prompt texts cannot be generated")]
        pkg = F.assemble(wo, inputs, _revision(), style, facts, [], asm, profile, texts, missing)
        if gate_model:  # OB-T042: an existing model is re-gated (reused), never re-authored
            item = model_item(wo, pkg)
            if item:
                pkg = F.assemble(wo, inputs, _revision(), style, facts, [item], asm, profile, texts, missing)
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


def model_item(key: str, pkg: dict) -> dict | None:
    """The `model` authored item of a package: the gate result of the model the derived profile names (existing
    models are reused and re-gated; an authored one comes from the onboarding run, slice J). Cached by the hashes of
    the model, its platform and the facts the gate reads, so the re-derivation at every launch is fast."""
    import json

    from ..common import canonical_json, sha256_bytes
    from .facts import value
    from .model_gate import SIM_DIR, check

    pid = (value(pkg, "register_prefix") or "").lower()
    model, repl = SIM_DIR / f"{pid}_model.py", SIM_DIR / f"stm32n6_{pid}.repl"
    if not (pid and model.is_file() and repl.is_file()):
        return None
    subject = {"model": sha256_bytes(model.read_bytes()), "repl": sha256_bytes(repl.read_bytes()),
               "facts": [f for f in pkg["facts"] if f["name"] in ("register_index", "base_address", "file_map", "api",
                                                                  "undelivered_externals", "instance")]}
    cache = onboarding_dir(key) / "onboarding/model_gate.json"
    k = sha256_bytes(canonical_json(subject))
    try:
        rec = json.loads(cache.read_text()) if cache.is_file() else None
    except ValueError:
        rec = None
    if not rec or rec.get("key") != k:
        from .leftovers import write_preview

        write_preview(key, pkg)
        rec = {"key": k, "result": check(key, pkg=pkg)}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    r = rec["result"]
    return {"id": "model", "role": "onboard-model-author", "path": f"factory/sim/stm32n6/{pid}_model.py",
            "attempts": 0, "gate": {"verdict": r["verdict"], "findings": r["findings"], "limits": r.get("limits", []),
                                    "tool": f"forge-onboarding model gate ({r.get('tool')})",
                                    "version": str(r.get("version")), "invocation_id": k[:16],
                                    "stats": r.get("stats", {}), "model": r.get("model", model.name)},
            "inspection": {"verdict": "NOT_RUN", "findings": [], "inspector_role": "onboard-model-inspector",
                           "reason": "reused factory model (feature 015): re-gated against the RM, not re-inspected"},
            "limits": r.get("limits", []) + [_model_limits_note(model)], "reused": True,
            "status": "ACCEPTED" if r["verdict"] == "PASS" else "GAP"}


def _model_limits_note(model: Path) -> str:
    from .texts import model_description

    d = model_description(model.stem.replace("_model", "")) or ""
    m = __import__("re").search(r"([^.]*(?:out of the work orders' scope|not modelled)[^.]*\.)", d)
    return m.group(1).strip() if m else "behaviour not stated in the model description is not modelled"


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
