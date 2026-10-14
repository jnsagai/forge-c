"""Hash demonstration evidence, explicitly segregated from safety release artifacts."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--profile", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    if not args.log.is_file() or not args.profile.is_file():
        raise SystemExit("missing evidence: cannot claim demo passed")
    files = [args.log, args.profile]
    root = args.root.resolve()
    record = {
        "scope": "host-only-educational-demo",
        "safety_status": "NOT_ASIL_B_EVIDENCE",
        "misra_status": "NOT_ASSESSED",
        "target_hardware_test": False,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "compiler": subprocess.run(["clang", "--version"], check=True, capture_output=True, text=True).stdout.splitlines()[0],
        "artifacts": [{"path": str(x.resolve().relative_to(root)), "sha256": sha256(x)} for x in files],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Evidence manifest:", args.output)


if __name__ == "__main__":
    main()
