"""Feature 016 slice H (OB-T033, FR-013): the leftover check. Every SWE.1-SWE.6 instruction of a package-driven work
order is built with the real workflow builder (the full node set) and scanned; an identifier fails when it is not the
work order's own: another registered peripheral's prefix or vocabulary (RCC's oscillators), another driver layer's
names (LL for ST's classic HAL), or a register, field, function, type or macro that neither the package (register
index, API, externals) nor the delivered code and headers declare."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import REPO_ROOT, load_yaml
from .facts import value

# RCC's clock vocabulary; "HSI" also abbreviates the hardware-software interface ("HSI contract")
FOREIGN_WORDS = {"RCC": r"\b(oscillators?|HSE|MSI|LSI|LSE|PLL\d?)\b"}  # not HSI: also "hardware-software interface"


def _registered_prefixes() -> set[str]:
    return {(load_yaml(p) or {}).get("register_prefix") for p in (REPO_ROOT / "config/factory/peripherals").glob("*.yaml")}


def vocabulary(pkg: dict, files: list[Path]) -> set[str]:
    """Every identifier the delivered code, its dependencies and the package declare."""
    voc: set[str] = set()
    for p in files:
        t = p.read_text(errors="replace")
        voc |= set(re.findall(r"#\s*define\s+(\w+)", t))
        voc |= set(re.findall(r"}\s*(\w+)\s*;", t))
        voc |= set(re.findall(r"typedef\s+[^;{]*?\b(\w+)\s*;", t))
        voc |= set(re.findall(r"\b(\w+)\s*\(", t))
        voc |= set(re.findall(r"^\s*(\w+)\s*(?:=\s*[^,\n]+)?,", t, re.M))  # enum members
    P = value(pkg, "register_prefix")
    for reg, d in (value(pkg, "register_index") or {}).items():
        voc.add(reg)
        voc |= {f"{reg}.{f}" for f in d["fields"]}
    for e in value(pkg, "undelivered_externals") or []:
        voc.add(e["symbol"])
    voc |= {P, value(pkg, "instance") or "", f"{P}_HAL", value(pkg, "function_prefix") or ""}  # SWC label, prefix
    return voc


def instructions(key: str) -> dict[str, str]:
    """{node: prompt} of the SWE workflow built for the package-driven work order `key` (preview profile)."""
    from ..workflow import prompts as PR
    from ..workflow.builder import build

    nodes: dict[str, str] = {}
    dot, info = build(key, goal="x", sections={}, layer="HAL", trace=True, isolation=False, brownfield="FROZEN",
                      peripheral=f"onboarding-preview:{key}", delivery_style="cmsis", hal_standalone=True)
    for m in re.finditer(r'(?m)^\s*"?([\w.-]+)"?\s*\[(.*?)\]\s*;?\s*$', dot, re.S):
        p = re.search(r'prompt="((?:[^"\\]|\\.)*)"', m.group(2))
        if p:
            nodes[m.group(1)] = p.group(1).replace('\\"', '"').replace("\\n", "\n")
    nodes["unit_test_author"] = PR.unit_test_author_prompt()
    nodes["target_test_author"] = PR.target_test_author_prompt()
    nodes["robot_test_author"] = PR.robot_test_author_prompt()
    return nodes


TOKEN = re.compile(r"\b(?:HAL|LL)_\w+|\b\w+_(?:Handle|Init)?TypeDef\b|\bll_\w+_regs\b|\bstm32n6xx_ll_\w+|\b[A-Z][A-Z0-9]+_[A-Z0-9_]+\b"
                   r"(?:\.[A-Z][A-Z0-9_]*\b)?")
GENERIC = {"HAL_OK", "HAL_ERROR", "HAL_BUSY", "HAL_TIMEOUT", "HAL_StatusTypeDef", "UT_ID", "SWR_ID", "NOT_IMPLEMENTED",
           "FORGE_MAILBOX_DEFINE", "FORGE_TEST_BEGIN", "FORGE_TEST_END", "TCHECK", "CHECK_EXPR", "USE_FULL_ASSERT",
           "SIMULATOR_MODEL_NOT_COMPARABLE", "DELIVERED_CODE_FROZEN", "INIT_EXAMPLE"}


def check(key: str, pkg: dict, files: list[Path]) -> list[str]:
    P = value(pkg, "register_prefix")
    voc = vocabulary(pkg, files)
    others = {x for x in _registered_prefixes() if x and x != P}
    out = []
    for node, text in sorted(instructions(key).items()):
        for word_rx in [rx for p, rx in FOREIGN_WORDS.items() if p != P]:
            for m in re.finditer(word_rx, text):
                out.append(f"LEFTOVER:{node}:{m.group(0)}")
        for m in TOKEN.finditer(text):
            tok = m.group(0)
            if tok in voc or tok in GENERIC or re.fullmatch(r"(UT|SWR|IT|QT|DEF|SWU|IF|TC)-?\w*", tok):
                continue
            head = tok.split("_", 1)[0]
            foreign = head in others or tok.startswith(("LL_", "ll_", "stm32n6xx_ll_"))
            own_unknown = head == P or tok.startswith("HAL_") or tok.endswith("TypeDef")
            if foreign or own_unknown:
                out.append(f"LEFTOVER:{node}:{tok}")
    return sorted(set(out))


def write_preview(key: str, pkg: dict) -> None:
    """The preview profile (assumptions at a placeholder value) the leftover check and the model smoke build use;
    never used by a run (prepare loads only the approved profile.json)."""
    from . import onboarding_dir
    from .profile import derived_profile

    prof = derived_profile(pkg, {"assumption_confirmations": [{"id": a["id"], "value": 1} for a in pkg["assumptions"]]})
    p = onboarding_dir(key) / "onboarding/profile.preview.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prof, indent=2, sort_keys=True) + "\n")
    from ..peripheral import load

    load.cache_clear()


def run(key: str) -> list[str]:
    """The check for a derived package `key` (state/onboarding/<key>), with a preview of its profile."""
    from . import facts as F
    from . import onboarding_dir
    from .profile import derived_profile

    root = onboarding_dir(key)
    pkg = F.read_package(root)
    write_preview(key, pkg)
    fm = value(pkg, "file_map") or {}
    import os

    files = []
    for d in fm.get("dependencies", []):
        src = Path(os.path.expandvars(d["source"]))
        if (src / d["from"]).is_file():
            files.append(src / d["from"])
    delivered = Path(os.path.expandvars(json.loads((REPO_ROOT / "examples" / key / "workorder.json").read_text())
                                        ["delivery"]["source"]))
    files += [delivered / f["from"] for f in fm.get("files", [])]
    return check(key, pkg, files)
