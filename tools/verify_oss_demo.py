"""Check hashes and explicit NON-safety scope of the educational OSS demo."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED_ARTIFACTS = {"evidence/oss-demo/llvm-host.log", "evidence/oss-demo/test.profdata"}


def validate(manifest: dict, root: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("scope") != "host-only-educational-demo":
        errors.append("demo scope mismatch")
    if manifest.get("safety_status") != "NOT_ASIL_B_EVIDENCE":
        errors.append("demo manifest must explicitly reject ASIL B claims")
    if manifest.get("misra_status") != "NOT_ASSESSED":
        errors.append("demo manifest must not claim MISRA checks")
    if manifest.get("target_hardware_test") is not False:
        errors.append("demo must not claim target hardware test")
    items = manifest.get("artifacts", [])
    if not isinstance(items, list):
        return errors + ["artifacts must be list"]
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append("invalid artifact entry")
            continue
        raw_path = item.get("path")
        if not isinstance(raw_path, str):
            errors.append("missing artifact path")
            continue
        relative = Path(raw_path)
        if relative.is_absolute() or '..' in relative.parts or str(relative).startswith('./'):
            errors.append(f"unsafe artifact path: {raw_path}")
            continue
        absolute = root / relative
        try:
            absolute.resolve().relative_to(root.resolve())
            digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
        except (ValueError, OSError) as exc:
            errors.append(f"cannot read {raw_path}: {exc}")
            continue
        if digest != item.get("sha256"):
            errors.append(f"hash mismatch: {raw_path}")
        seen.add(str(relative))
    for required in sorted(REQUIRED_ARTIFACTS - seen):
        errors.append(f"missing evidence artifact: {required}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', default='evidence/oss-demo/manifest.json')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    try:
        errors = validate(json.loads(Path(args.manifest).read_text(encoding='utf-8')), Path(args.root))
    except (ValueError, OSError) as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print('DEMO_HASH_GATE_FAIL:', error)
        return 1
    print('DEMO_HASHES_PASS, HOST_ONLY, NOT_ASIL_B_EVIDENCE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
