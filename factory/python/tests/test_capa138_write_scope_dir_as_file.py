"""CAPA-138 (WO-F014-SWE1-WWDGHAL-20261103-L32B): the write scope admitted a role's directory prefix path itself
("workproducts/SWE.1", "traceability"), so Fabro's write_file created empty regular files there and every later
write below them failed. A directory prefix now admits only paths strictly inside it; a directory path (a prefix of
the role or an existing directory) is refused with PATH_IS_DIRECTORY and an actionable reason."""
import json
from pathlib import Path

import pytest
from forge_factory.policy.authz import ROLE_WRITE_PREFIXES, Authorizer, Binding


@pytest.fixture
def auth(tmp_path):
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"purpose": "QM"}))
    nodes = {f"swe{n}_author": {"role": f"swe{n}-author", "phase": f"SWE.{n}"} for n in range(1, 7)}
    return ws, Authorizer(Binding("t138", str(ws), nodes))


def _w(ws: Path, a: Authorizer, node: str, rel: str, tool: str = "write_file"):
    tin = {"file_path": str(ws / rel), "content": "x"} if tool == "write_file" else \
        {"file_path": str(ws / rel), "old_string": "a", "new_string": "b"}
    return a.decide(node, tool, tin)


@pytest.mark.parametrize("n", range(1, 7))
def test_every_directory_prefix_of_every_author_is_refused_as_a_file(auth, n):
    ws, a = auth
    for p in ROLE_WRITE_PREFIXES[f"swe{n}-author"]:
        if p.endswith("/"):
            for tool in ("write_file", "edit_file"):
                d = _w(ws, a, f"swe{n}_author", p.rstrip("/"), tool)
                assert not d.allow and d.code == "PATH_IS_DIRECTORY", (p, tool, d)
                assert "write the file inside it" in d.reason and "parent directories" in d.reason


def test_an_existing_directory_inside_the_scope_is_refused(auth):
    ws, a = auth
    (ws / "workproducts/SWE.1/sub").mkdir(parents=True)
    d = _w(ws, a, "swe1_author", "workproducts/SWE.1/sub")
    assert not d.allow and d.code == "PATH_IS_DIRECTORY"
    assert json.loads(d.hook_json())["reason"].startswith("FORGE_POLICY:PATH_IS_DIRECTORY:workproducts/SWE.1/sub")


def test_files_inside_the_scope_and_file_prefixes_stay_allowed(auth):
    ws, a = auth
    for rel in ("workproducts/SWE.1/software_requirements.md", "traceability/requirements_to_tests.csv",
                "safety/software_safety_requirements.md", "workproducts/SWE.1/deep/new/file.md"):
        assert _w(ws, a, "swe1_author", rel).allow, rel


def test_outside_the_scope_is_still_write_scope_denied(auth):
    ws, a = auth
    for rel in ("software/src/x.c", "safety/other.md", "workproducts/SWE.2/a.md", "workproducts/SWE.1x/a.md"):
        d = _w(ws, a, "swe1_author", rel)
        assert not d.allow and d.code == "WRITE_SCOPE_DENIED", (rel, d)
    d = _w(ws, a, "swe1_author", "safety")  # not a prefix of the role: scope, as before
    assert not d.allow and d.code == "WRITE_SCOPE_DENIED"
