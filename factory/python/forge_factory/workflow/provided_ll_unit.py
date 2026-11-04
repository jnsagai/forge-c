"""Explicit host RAM tests of a HAL against its immutable provided CMSIS LL.

The default LL mock remains the call-contract backend. A separate GoogleTest
file can select real vendor register effects; those remain host observations,
never target execution or peripheral emulation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from ..brownfield import cmsis, manifest_of
from .provided_input_identity import effective_identity

MARKER = "// FORGE_UNIT_BACKEND: provided-ll-ram-v1"


def supported(manifest: dict) -> bool:
    return (manifest.get("layer") == "HAL"
            and manifest.get("hal_unit_isolation") == "ll-fake-v1"
            and manifest.get("unit_verification") == "uspec-gtest-v1"
            and (manifest.get("provided_build") or {}).get("style") == "cmsis"
            and bool(manifest.get("provided")))


def headers(ws: Path) -> list[Path]:
    """Verify every provided LL input before allowing an alternate unit backend."""
    manifest = manifest_of(ws)
    if not supported(manifest):
        raise ValueError("PROVIDED_LL_UNIT_BACKEND_UNSUPPORTED")
    result = []
    for item in manifest["provided"]:
        rel = item.get("path", "")
        path = PurePosixPath(rel)
        if (item.get("role") != "provided_ll_driver" or not rel.startswith("software/ll/")
                or path.suffix != ".h" or ".." in path.parts or path.is_absolute()
                or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", ""))):
            raise ValueError("PROVIDED_LL_UNIT_INPUT_INVALID")
        source = ws / rel
        if (any(p.is_symlink() for p in [source, *source.parents] if p != ws.parent) or not source.is_file()):
            raise ValueError("PROVIDED_LL_UNIT_INPUT_CHANGED:" + rel)
        try:
            effective_identity(ws, rel)
        except ValueError as exc:
            raise ValueError("PROVIDED_LL_UNIT_INPUT_CHANGED:" + rel + ":" + str(exc)) from exc
        result.append(source)
    if len({p.name for p in result}) != len(result):
        raise ValueError("PROVIDED_LL_UNIT_HEADER_COLLISION")
    cmsis._verify_provided(ws, manifest["provided_build"])
    return result


def selected(ws: Path, test: Path) -> bool:
    text = test.read_text(errors="replace")
    if "FORGE_UNIT_BACKEND" not in text:
        return False
    if (test.suffix != ".cpp" or not text.startswith(MARKER + "\n")
            or text.count("FORGE_UNIT_BACKEND") != 1):
        raise ValueError("PROVIDED_LL_UNIT_MARKER_INVALID:" + test.name)
    headers(ws)
    return True


def generate(ws: Path, output: Path):
    """C++ needs declarations only; HAL C units execute the original LL bodies.

    No LL forwarding symbol is exported: this backend verifies the HAL through
    its API. Calling a provided LL directly from C++ cannot stand in for a HAL
    observation and fails to link.
    """
    from ..brownfield.cmsis_gtest import _generate

    selected = headers(ws)
    result = _generate(ws, output, selected, [], "provided-ll-ram-v1")
    path = result[0] / "binding.json"
    binding = json.loads(path.read_text())
    binding["provided_effective_identity"] = [effective_identity(ws, p.relative_to(ws).as_posix()) for p in selected]
    path.write_text(json.dumps(binding, indent=2) + "\n")
    return result
