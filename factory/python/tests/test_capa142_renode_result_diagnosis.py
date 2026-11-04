"""CAPA-142 (WO-F014-SWE5-WWDGHAL-20261103-L32): the SWE.5 target tests ran in Renode (passed/failed/done written) but
never called FORGE_TEST_BEGIN(), so the mailbox magic was unset and run_renode said only "NO_RESULT:<test>:default".
The author then wrote its own forge_target_test.h, which precedes the factory harness on the include path. The
finding now says why (action first - tool issues are cut at 120 characters), such results are still not counted,
a workspace copy of a factory harness header is refused by the write scope, and a failing run names any copy."""
import json
from pathlib import Path

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import sim
from forge_factory.policy.authz import FACTORY_HARNESS_HEADERS, Authorizer, Binding

GOOD = {"magic_ok": True, "passed": 7, "failed": 0, "done": True, "failed_ids": []}


def _ws(tmp_path: Path, name: str = "ws") -> Path:
    ws = tmp_path / name
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL"}))
    (ws / "software/tests/target").mkdir(parents=True)
    (ws / "software/tests/target/test_x_target.c").write_text("int main(void) { return 0; }\n")
    return ws


@pytest.fixture
def stub(monkeypatch):
    """run_renode without Renode or the Arm toolchain: every image builds and yields the given observation."""
    box = {"res": GOOD}
    monkeypatch.setattr(sim, "renode_bin", lambda: "/usr/bin/true")
    monkeypatch.setattr(sim, "build_image", lambda *a, **k: (True, b"", []))
    monkeypatch.setattr(sim, "run_image", lambda *a, **k: (box["res"], b""))
    monkeypatch.setattr(sim.shutil, "which", lambda n, *a, **k: "/usr/bin/" + n)
    return box


def _run(ws: Path) -> dict:
    return sim.run_renode(sdk.ToolContext("forge-sim-mcp", "run_renode", "swe5-author", "SWE.5", ws, "t142"),
                          sim.SimIn())


def test_checks_that_ran_with_the_magic_unset_say_forge_test_begin_and_do_not_count(tmp_path, stub, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "st"))
    stub["res"] = {"magic_ok": False, "passed": 7, "failed": 1, "done": True, "failed_ids": [8]}
    r = _run(_ws(tmp_path))
    nr = [i for i in r["issues"] if i.startswith("NO_RESULT:test_x_target.c:default")]
    assert r["status"] != "PASS" and nr and "FORGE_TEST_BEGIN()" in nr[0] and "passed 7, failed 1" in nr[0], r
    assert r["metrics"].get("passed", 0) == 0  # the unmagicked results are never counted


@pytest.mark.parametrize("res,text", [
    (None, "no mailbox output"),
    ({"magic_ok": False, "passed": 0, "failed": 0, "done": False, "failed_ids": []}, "never initialised"),
    ({"magic_ok": True, "passed": 3, "failed": 0, "done": False, "failed_ids": []}, "FORGE_TEST_END() not reached")])
def test_every_no_result_keeps_its_code_and_states_its_cause(res, text):
    i = sim.no_result_issue("test_a.c", "default", res)
    assert i.startswith("NO_RESULT:test_a.c:default: ") and text in i and len(i) <= 120, i


def test_a_valid_mailbox_is_unchanged(tmp_path, stub, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "st"))
    r = _run(_ws(tmp_path))
    assert r["status"] == "PASS" and not [i for i in r["issues"] if i.startswith(("NO_RESULT", "HARNESS"))], r


def test_a_failing_run_names_a_local_harness_copy(tmp_path, stub, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "st"))
    ws = _ws(tmp_path)
    (ws / "software/tests/target/forge_target_test.h").write_text("")
    stub["res"] = None
    r = _run(ws)
    assert any(i.startswith("HARNESS_SHADOWED:software/tests/target/forge_target_test.h") for i in r["issues"]), r


def _decide(tmp_path: Path, rel: str):
    ws = tmp_path / "pws"
    (ws / ".forge-run").mkdir(parents=True, exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"purpose": "QM"}))
    a = Authorizer(Binding("t142", str(ws), {"swe5_author": {"role": "swe5-author", "phase": "SWE.5"},
                                             "swe4_author": {"role": "swe4-author", "phase": "SWE.4"}}))
    node = "swe4_author" if "/unit/" in rel else "swe5_author"
    return a.decide(node, "write_file", {"file_path": str(ws / rel), "content": "x\n"})


@pytest.mark.parametrize("name", FACTORY_HARNESS_HEADERS)
def test_a_workspace_copy_of_a_factory_harness_header_is_refused(tmp_path, name):
    d = _decide(tmp_path, f"software/tests/target/{name}")
    assert not d.allow and d.code == "HARNESS_SHADOW_DENIED" and f'#include "{name}"' in d.reason, d


def test_ordinary_target_tests_stay_writable(tmp_path):
    for rel in ("software/tests/target/test_wwdg_target.c", "software/tests/target/expected.h"):
        assert _decide(tmp_path, rel).allow, rel
