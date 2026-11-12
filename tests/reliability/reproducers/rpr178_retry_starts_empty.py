"""RPR-178 (owner lane, Omniverse2, 2026-11-07, L90X/L90Y): every SWE.6 retry of the owner series re-seeded from the
L34G baseline and wrote its robot suite from nothing; L90W's 15/24 tests were lost and L90X started at 0/24.

Scenario: an earlier attempt with both robot runs on record (exact hashes, snapshots) and its test files in place.
Symptom: the retry's workspace receives none of the earlier attempt's test files."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

SIG = "a SWE.6 retry of the owner series starts with none of the earlier attempt's tests"

# Scenario: one earlier attempt whose first robot run passed 24/24 and whose later edit broke the build (2/24).
TESTS = "software/tests/software"
GOOD = {"scn_crc_init.c": b"/* good scenario */\nint scn(void){return 0;}\n",
        "test_crc_requirements.robot": b"*** Test Cases ***\nGood\n    Log    good\n"}
BROKEN = {"scn_crc_init.c": b"/* broken: invented register ll_crc_regs */\nint scn(void){return ll_crc_regs;}\n",
          "test_crc_requirements.robot": b"*** Test Cases ***\nBroken\n    Log    broken\n"}


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def build(root: Path):
    orders = ["WO-RPR-CARRY-A", "WO-RPR-CARRY-B"]
    ws = root / orders[0] / "workspace"
    (ws / TESTS).mkdir(parents=True)
    (ws / "evidence").mkdir()
    (ws / ".forge-run/test-snapshots").mkdir(parents=True)
    results, integrity = [], []
    for at, files, summary in (("2026-11-07T09:56:59Z", GOOD, "robot: 24/24 tests passed; 22/24 requirements verified"),
                               ("2026-11-07T10:20:00Z", BROKEN, "robot: 2/24 tests passed; 1/24 requirements verified")):
        for data in files.values():
            (ws / ".forge-run/test-snapshots" / _sha(data)).write_bytes(data)
        results.append({"op": "run_robot", "phase": "SWE.6", "ts_utc": at, "result": {"summary": summary}})
        integrity.append({"op": "run_robot", "phase": "SWE.6", "ts_utc": at,
                          "files": {f"{TESTS}/{n}": _sha(d) for n, d in files.items()}})
    for name, data in BROKEN.items():
        (ws / TESTS / name).write_bytes(data)
    (ws / "evidence/tool-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results))
    (ws / "evidence/test-integrity.jsonl").write_text("".join(json.dumps(r) + "\n" for r in integrity))
    target = root / orders[1] / "workspace"
    target.mkdir(parents=True)
    return orders, target


def main() -> int:
    import importlib
    import importlib.util

    if importlib.util.find_spec("forge_factory.attempt_carry") is None:  # no carry mechanism at all
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    attempt_carry = importlib.import_module("forge_factory.attempt_carry")
    with tempfile.TemporaryDirectory() as td:
        orders, target = build(Path(td))
        carried = attempt_carry.install(target, orders[1], orders, Path(td))
        present = sorted(p.name for p in (target / TESTS).glob("*")) if (target / TESTS).is_dir() else []
        if not carried or not present:
            print(f"SYMPTOM_PRESENT:{SIG}")
            return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
