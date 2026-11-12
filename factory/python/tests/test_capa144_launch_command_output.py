"""Keep command replies isolated while preserving every byte in the attempt log."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_launcher as LL


@pytest.fixture
def command(tmp_path):
    package = tmp_path / "modules/forge_factory/lrtx"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").touch()
    (package / "__init__.py").touch()
    (package / "stack.py").write_text(
        "import sys\n"
        "sys.stdout.write(sys.argv[1])\n"
        "sys.stderr.write(sys.argv[2])\n"
        "raise SystemExit(int(sys.argv[3]))\n")
    host = LL.ShellHost(SimpleNamespace(python=Path(sys.executable)))
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(tmp_path / "modules")}

    def run(text, *, stderr="", rc=0, name="models.log"):
        return host.stack([text, stderr, str(rc)], env=env, cwd=tmp_path, log=tmp_path / name)
    return run, tmp_path


def test_second_model_reply_without_a_newline_is_parsed_from_its_own_call(command):
    run, directory = command
    author = json.dumps({"data": [{"id": "ornith"}]})
    inspector = json.dumps({"data": [{"id": "qwen"}]})
    assert run(inspector, name="control.log") == (0, inspector)
    assert run(author) == (0, author)
    rc, reply = run(inspector)
    assert rc == 0 and LL._last_json(reply)["data"] == [{"id": "qwen"}]
    assert (directory / "models.log").read_text() == author + inspector


def test_empty_current_reply_cannot_reuse_an_earlier_success(command):
    run, directory = command
    success = '{"outcome":"OK"}'
    assert run(success) == (0, success)
    rc, reply = run("")
    assert rc == 0 and reply == "" and LL._last_json(reply) is None
    assert (directory / "models.log").read_text() == success


def test_current_failure_keeps_its_return_code_and_stderr_without_old_output(command):
    run, directory = command
    run('{"outcome":"OK"}\n')
    rc, reply = run("", stderr="CURRENT_FAILURE\n", rc=3)
    assert rc == 3 and reply == "CURRENT_FAILURE\n"
    assert (directory / "models.log").read_text() == '{"outcome":"OK"}\nCURRENT_FAILURE\n'
