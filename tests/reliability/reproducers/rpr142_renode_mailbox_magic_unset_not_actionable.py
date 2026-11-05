"""RPR-142 (local run WO-F014-SWE5-WWDGHAL-20261103-L32, Omniverse2, 2026-11-04): the SWE.5 target tests of the WWDG
HAL ran in Renode - the mailbox read back passed=4/failed=0/done=1 and passed=7/failed=1/done=1 - but the tests never
called FORGE_TEST_BEGIN(), which sets the mailbox magic. forge-sim-mcp run_renode reported only the bare
"NO_RESULT:<test>:default" for every image, so the author never learned what was missing: it wrote its own
software/tests/target/forge_target_test.h (later emptied), which the image build includes BEFORE the factory harness
(-I software/tests/target precedes -I factory/sim/stm32n6), so every image failed to link (undefined TCHECK) and the
author spent its turn budget on debug scripts it could not run. STUCK after 3 cycles.

Scenario (synthetic workspace; no Renode or Arm toolchain needed): run_renode of the revision under test with the
image build and the Renode run stubbed to return a mailbox whose checks ran but whose magic is unset, and the write
scope of the SWE.5 author for a copy of the factory harness header in software/tests/target.
Symptom: the image's issue is the bare NO_RESULT (no word of FORGE_TEST_BEGIN), or the harness copy is writable.
Controls: a valid mailbox gives a PASS without NO_RESULT; a run without mailbox output still reports NO_RESULT; an
ordinary target test file stays writable."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "a target image whose checks ran with the mailbox magic unset reports a bare NO_RESULT, or the factory harness can be shadowed"


def run_case(td: Path, name: str, observation):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import sim

    ws = td / name
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL"}))
    (ws / "software/tests/target").mkdir(parents=True)
    (ws / "software/tests/target/test_wwdg_target.c").write_text("int main(void) { return 0; }\n")
    subprocess_free = {"renode_bin": lambda: "/usr/bin/true",
                       "build_image": lambda *a, **k: (True, b"", []),
                       "run_image": lambda *a, **k: (observation, b"")}
    saved = {k: getattr(sim, k) for k in subprocess_free}
    saved_which = sim.shutil.which
    try:
        for k, v in subprocess_free.items():
            setattr(sim, k, v)
        sim.shutil.which = lambda n, *a, **k: "/usr/bin/" + n
        ctx = sdk.ToolContext("forge-sim-mcp", "run_renode", "swe5-author", "SWE.5", ws, "rpr142")
        return sim.run_renode(ctx, sim.SimIn())
    finally:
        for k, v in saved.items():
            setattr(sim, k, v)
        sim.shutil.which = saved_which


def write_decision(td: Path, rel: str):
    from forge_factory.policy.authz import Authorizer, Binding

    ws = td / "policy-ws"
    (ws / ".forge-run").mkdir(parents=True, exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"purpose": "QM"}))
    a = Authorizer(Binding("rpr142", str(ws), {"swe5_author": {"role": "swe5-author", "phase": "SWE.5"}}))
    return a.decide("swe5_author", "write_file", {"file_path": str(ws / rel), "content": "#define TCHECK(n, c)\n"})


def main() -> int:
    import os

    with tempfile.TemporaryDirectory() as tdn:
        td = Path(tdn)
        os.environ["FORGE_STATE_DIR"], os.environ["FORGE_EVENTS_DIR"] = f"{td}/state", f"{td}/events"
        good = run_case(td, "good", {"magic_ok": True, "passed": 7, "failed": 0, "done": True, "failed_ids": []})
        none = run_case(td, "none", None)
        bad = run_case(td, "bad", {"magic_ok": False, "passed": 7, "failed": 1, "done": True, "failed_ids": [8]})
        test_file = write_decision(td, "software/tests/target/test_wwdg_target.c")
        harness = write_decision(td, "software/tests/target/forge_target_test.h")
    if good["status"] != "PASS" or any(i.startswith("NO_RESULT") for i in good["issues"]):
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:valid mailbox {good['status']} {good['issues'][:3]}")
        return 2
    if not any(i.startswith("NO_RESULT:test_wwdg_target.c:default") for i in none["issues"]):
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no-output run {none['status']} {none['issues'][:3]}")
        return 2
    if not test_file.allow:
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:target test write refused {test_file.code}")
        return 2
    nr = [i for i in bad["issues"] if i.startswith("NO_RESULT:test_wwdg_target.c:default")]
    problems = []
    if bad["status"] == "PASS" or not nr:
        problems.append(f"unmagicked mailbox counted: {bad['status']} {bad['issues'][:3]}")
    elif not any("FORGE_TEST_BEGIN" in i for i in nr):
        problems.append(f"bare finding {nr[0][:120]}")
    if harness.allow:
        problems.append("software/tests/target/forge_target_test.h is writable (shadows the factory harness)")
    if problems:
        print("observed: " + "; ".join(problems))
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
