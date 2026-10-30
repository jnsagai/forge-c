"""Feature 016 slice E (OB-T021): the derived peripheral profile - the package's facts in the feature 009 profile
format, so every existing consumer (layer helpers, host device, scaffold, simulator, prompts) works unchanged on a
package-driven work order. Values the owner confirmed in the approval (test-environment assumptions) are applied; a
fact that is not DERIVED leaves the profile incomplete, and the profile is then refused (never filled with a guess)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import REPO_ROOT, sha256_file
from .facts import value

CONTRACT = REPO_ROOT / "specs/009-peripheral-generic-iwdg/contracts/peripheral-profile.schema.json"
SIM_DIR = REPO_ROOT / "factory/sim/stm32n6"


class ProfileIncomplete(ValueError):
    pass


def _need(pkg: dict, name: str):
    v = value(pkg, name)
    if v is None:
        raise ProfileIncomplete(f"PROFILE_FACT_NOT_DERIVED:{name}")
    return v


def derived_profile(pkg: dict, approval: dict | None = None, system_name: str | None = None,
                    model_paths: tuple[Path, Path] | None = None, *, gate_preview: bool = False) -> dict:
    style = _need(pkg, "driver_style")
    inst, prefix = _need(pkg, "instance"), _need(pkg, "register_prefix")
    pid = prefix.lower()
    hdr, fprefix = _need(pkg, "headers"), _need(pkg, "function_prefix")
    ch = _need(pkg, "rm_chapter")
    window = _need(pkg, "window_bytes")
    confirmed = {c["id"]: c["value"] for c in (approval or {}).get("assumption_confirmations") or []}
    ll_header = hdr["header"] if style == "LL" else f"stm32n6xx_ll_{pid}.h"
    prof = {"schema": "forge-c/peripheral-profile/0.1", "id": pid, "name": f"{ch['title']} ({inst})",
            "register_prefix": prefix, "base_address": _need(pkg, "base_address"), "mm_page": _need(pkg, "mm_page"),
            "window_bytes": window, "system_name": system_name or f"{prefix} driver",
            "rm": {"doc": ch["doc"], "chapter": ch["chapter"], "key_sections": _need(pkg, "key_sections")},
            "ll": {"header": ll_header, "compile_unit": re.sub(r"\.h$", ".c", ll_header),
                   "function_prefix": fprefix if style == "LL" else f"LL_{prefix}_",
                   "register_block": f"ll_{pid}_regs", "register_count": window // 4, "void_signatures": False}}
    if style == "LL":
        prof["hal"] = {"header": f"stm32n6xx_hal_{pid}.h", "source": f"stm32n6xx_hal_{pid}.c",
                       "function_prefix": f"HAL_{prefix}_"}
    else:
        prof["hal"] = {"header": hdr["header"], "source": hdr.get("source") or re.sub(r"\.h$", ".c", hdr["header"]),
                       "function_prefix": fprefix}
        tb = value(pkg, "time_base")
        if tb and tb != "NONE":
            prof["hal"]["time_base"] = tb
        host = value(pkg, "host_instance")
        if host and host != "NONE":
            prof["hal"]["host_instance"] = host
        for a in pkg["assumptions"]:
            ext = next((e for e in value(pkg, "undelivered_externals") or [] if e["symbol"] == a["symbol"]), None)
            if ext and ext["prototype"] and a["id"] in confirmed:
                prof["hal"]["clock_stub"] = {"prototype": ext["prototype"], "hz": int(confirmed[a["id"]])}
    if model_paths is None:
        from .authoring import artifact_paths

        model_paths = artifact_paths(pkg)
        if not model_paths and (pkg.get("profile") or {}).get("model_authoring", {}).get("hide_model"):
            raise ProfileIncomplete("PROFILE_HIDDEN_MODEL_NOT_ACCEPTED")
    model, repl = model_paths or (SIM_DIR / f"{pid}_model.py", SIM_DIR / f"stm32n6_{pid}.repl")
    if not (model.is_file() and repl.is_file()):
        raise ProfileIncomplete(f"PROFILE_MODEL_MISSING:{pid}")  # slice J authors one; until then: a gap
    prof["sim"] = {"model": str(model.resolve()) if model_paths else model.name,
                   "platform": str(repl.resolve()) if model_paths else repl.name}
    if pkg.get("texts"):  # OB-T032: generated texts only - a hand profile's prompt keys are never read for it
        from .texts import plain

        prof.update(plain(pkg["texts"]))
    elif style == "HAL_STANDALONE" and not gate_preview:
        raise ProfileIncomplete("PROFILE_TEXTS_MISSING")
    prof["derived_from"] = {"work_order": pkg["work_order"], "package_sha256": pkg["sha256"],
                            "approval_id": (approval or {}).get("approval_id")}
    if model_paths:
        prof["derived_from"].update(model_sha256=sha256_file(model), platform_sha256=sha256_file(repl))
    errs = validate(prof)
    if errs:
        raise ProfileIncomplete("PROFILE_INVALID:" + " | ".join(errs[:4]))
    return prof


def validate(prof: dict) -> list[str]:
    import jsonschema

    schema = json.loads(CONTRACT.read_text())
    return [f"{'/'.join(map(str, e.absolute_path)) or '-'}:{e.message[:140]}"
            for e in jsonschema.Draft202012Validator(schema).iter_errors(prof)]


def write(ws_root: Path, prof: dict) -> Path:
    p = Path(ws_root) / "onboarding/profile.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prof, indent=2, sort_keys=True) + "\n")
    return p
