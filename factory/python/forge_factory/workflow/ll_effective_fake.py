"""Private v1 fake of an independently approved correction; the protected original stays immutable."""
import json
from pathlib import Path

from ..common import sha256_file
from ..layer import ll_header, register_block
from . import ll_fake, provided_ll_unit


def generate(ws: Path, output: Path) -> Path:
    approved = provided_ll_unit.headers(ws)
    source = ws / ll_header(ws)
    identity = ll_fake.reviewed_change(ws)
    if source not in approved or identity is None or ll_fake.modified(ws):
        raise ValueError("PROVIDED_EFFECTIVE_FAKE_INPUT_CHANGED")
    output.mkdir(parents=True, exist_ok=True)
    target = output / source.name
    target.write_text(ll_fake.generate(source.read_text(errors="replace"), register_block(ws)))
    target.chmod(0o444)
    (output / "binding.json").write_text(json.dumps({
        "schema": "forge-c/reviewed-ll-fake/1", "backend": "reviewed-ll-fake-v1",
        "provided_effective_identity": identity,
        "original_fake_sha256": sha256_file(ws / ll_fake.fake_header(ws)),
        "generated_sha256": sha256_file(target), "generator_sha256": sha256_file(Path(ll_fake.__file__)),
        "scope": "RECORDED_LL_CALLS_ONLY", "target_or_register_effect_claim": False}, indent=2) + "\n")
    return output
