"""RPR-144: cumulative newline-free command logs falsely fail a healthy model-swap smoke.

Two real subprocesses emit distinct model replies without final newlines into the same attempt log, as the
Omniverse M2 launcher does for curl. A fresh-file probe is the control. An empty later probe must never reuse an
earlier successful reply. Only scratch files and child processes created here are used; no GPU or network.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

SIG = "the line launcher interprets accumulated command output as the current model probe"


def main():
    from forge_factory.afo import line_launcher as LL

    with tempfile.TemporaryDirectory(prefix="rpr144-") as directory:
        root = Path(directory)
        pkg = root / "modules/forge_factory/lrtx"
        pkg.mkdir(parents=True)
        (pkg.parent / "__init__.py").touch()
        (pkg / "__init__.py").touch()
        (pkg / "stack.py").write_text("import sys\nsys.stdout.write(sys.argv[1])\n")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(root / "modules"),
               "PYTHONDONTWRITEBYTECODE": "1"}
        host = LL.ShellHost(SimpleNamespace(python=Path(sys.executable)))

        def run(text, name):
            return host.stack([text], env=env, cwd=root, log=root / name)

        author = json.dumps({"data": [{"id": "ornith"}]})
        inspector = json.dumps({"data": [{"id": "qwen"}]})
        rc, reply = run(inspector, "control.log")
        if rc != 0 or LL._last_json(reply) != {"data": [{"id": "qwen"}]}:
            print("REPRODUCER_ERROR:CONTROL:single probe did not reach the healthy model reply")
            return 2
        rc, reply = run(author, "models.log")
        if rc != 0 or LL._last_json(reply) != {"data": [{"id": "ornith"}]}:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:first probe failed")
            return 2
        rc, second = run(inspector, "models.log")
        rc_empty, empty = run("", "models.log")
        if rc or rc_empty or (root / "models.log").read_text() != author + inspector:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:subprocess or complete log changed")
            return 2
        if LL._last_json(second) != {"data": [{"id": "qwen"}]} or empty:
            print("SYMPTOM_PRESENT:" + SIG)
            return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        raise SystemExit(2)
