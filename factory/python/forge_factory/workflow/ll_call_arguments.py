"""Opt-in call-argument history, generated in the private host build only."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import sha256_file
from ..layer import ll_header, register_block
from . import ll_fake, provided_ll_unit
from .provided_input_identity import effective_identity

MARKER = "// FORGE_UNIT_BACKEND: ll-call-arguments-v1"


def selected(ws: Path, test: Path) -> bool:
    text = test.read_text(errors="replace")
    if not text.startswith(MARKER):
        return False
    if (test.suffix != ".cpp" or not text.startswith(MARKER + "\n")
            or text.count("FORGE_UNIT_BACKEND") != 1):
        raise ValueError("LL_CALL_ARGUMENT_MARKER_INVALID:" + test.name)
    headers = provided_ll_unit.headers(ws)
    if ws / ll_header(ws) not in headers:
        raise ValueError("LL_CALL_ARGUMENT_PROVIDED_HEADER_MISSING")
    return True


def generate(ws: Path, output: Path) -> Path:
    headers = provided_ll_unit.headers(ws)
    source = ws / ll_header(ws)
    if source not in headers or ll_fake.modified(ws):
        raise ValueError("LL_CALL_ARGUMENT_INPUT_CHANGED")
    output.mkdir(parents=True, exist_ok=True)
    target = output / source.name
    target.write_text(ll_fake.generate(source.read_text(), register_block(ws), argument_history=True))
    target.chmod(0o444)
    (output / "binding.json").write_text(json.dumps({
        "schema": "forge-c/ll-call-arguments/1", "backend": "ll-call-arguments-v1",
        "provided_header": str(source.relative_to(ws)), "provided_sha256": sha256_file(source),
        "original_fake_sha256": sha256_file(ws / ll_fake.fake_header(ws)),
        "generated_sha256": sha256_file(target), "generator_sha256": sha256_file(Path(ll_fake.__file__)),
        "scope": "RECORDED_SCALAR_CALL_ARGUMENTS_ONLY", "target_or_register_effect_claim": False,
        "provided_effective_identity": [effective_identity(ws, p.relative_to(ws).as_posix()) for p in headers],
        "capacity": ll_fake.LOG_CAPACITY, "scalars_per_call_max": 2}, indent=2) + "\n")
    return output
