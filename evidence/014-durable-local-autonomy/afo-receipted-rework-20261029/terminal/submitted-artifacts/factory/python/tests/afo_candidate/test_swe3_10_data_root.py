"""SWE3-10 reproducer: PLANTUML_NOT_AVAILABLE for the declared unit diagrams.

Root cause: render_run_toml pinned PYTHONPATH/FORGE_STATE_DIR for the generated isolated
MCP servers but omitted FORGE_DATA_ROOT from the env table. An isolated MCP child gets
exactly that env table (it does not inherit the host process environment), so it resolved
the data root to the default instead of the host's declared root and the installed
plantuml jar (data_root()/toolchains/plantuml/*.jar) was invisible to the SWE.3 inspection:
render_ok reported PLANTUML_NOT_AVAILABLE although java and the jar are installed on the
host (observed: isolated_mcp_children_observed=9, children_with_data_root=0,
plantuml_jar_installed=true). Removing the generated default instead of fixing the key
collision is not a repair: a per-server declared FORGE_DATA_ROOT then produced a duplicate
TOML key that strict tomllib rejects ('Cannot overwrite a value').

Second defect in the same generated tool context: the generated policy hook emitted the
declared hook_env overrides before the generated defaults, so the later default
FORGE_DATA_ROOT assignment shadowed the declared override (a shell applies prefix
assignments in order, the last one wins) and the hook resolved the default factory data
root. The default and the declared override must both work: the host's declared root is
the default and a declared value wins over it, with no duplicate key on either path.

Fix under test: the generated MCP env table pins FORGE_DATA_ROOT to the host's declared
root (a declared server value overrides it, each key emitted exactly once, strict
tomllib always parses); the generated hook emits each default only when not declared and
declared overrides after, so the declared override is never shadowed by a later default.

Script mode (baseline reproducer check):
    python test_swe3_10_data_root.py
      exit 1, stdout's last nonblank line exactly SYMPTOM_PRESENT:<signature> while the defect exists
      exit 0, stdout's last nonblank line exactly SYMPTOM_ABSENT once fixed
    (diagnostics, if any, go to stderr, never after the signature on stdout)
pytest mode: the test_* functions below verify the fix.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "factory" / "python"))  # script mode from any cwd

SERVER = "forge-tests-mcp"
KEY = SERVER.replace("-", "_")
SIG = "SWE3-10-PLANTUML_NOT_AVAILABLE-DATA-ROOT-NOT-PROPAGATED"

# Resolves the tool context exactly the way the frozen inspection does
# (forge_factory.inspection.swtrace._plantuml_jar / render_ok), from a subprocess whose
# environment is exactly the env table the generated run config declares for the isolated
# MCP server.
CHILD_SCRIPT = (
    "import forge_factory.common as c\n"
    "jar = sorted((c.data_root() / 'toolchains' / 'plantuml').glob('*.jar'))\n"
    "print(c.data_root())\n"
    "print('JAR' if jar else 'NOJAR')\n"
)

# Probe for the hook env prefix: the same python executable as the generated hook, only
# the FORGE_DATA_ROOT variable is reported; the policy module is not executed.
HOOK_PROBE = "import os; print(os.environ.get('FORGE_DATA_ROOT', ''))"


def _new_host() -> Path:
    # a space in the path: data/state/binding paths with spaces must keep working
    return Path(tempfile.mkdtemp(prefix="afo-swe310 "))


def _host(tmp: Path) -> None:
    """Host side: FORGE_DATA_ROOT declared (non-default, with a space in the path) and the
    plantuml jar installed under it."""
    os.environ["FORGE_DATA_ROOT"] = str(tmp)
    os.environ.pop("FORGE_STATE_DIR", None)  # state dir derives from the data root
    (tmp / "toolchains" / "plantuml").mkdir(parents=True)
    (tmp / "toolchains" / "plantuml" / "plantuml.jar").write_bytes(b"fake-plantuml-jar")


def _render(tmp: Path, spec_env: dict[str, str] | None, hook_env: dict[str, str] | None = None) -> str:
    from forge_factory.fabro.runconfig import render_run_toml

    spec: dict = {"module": "forge_factory.mcp.servers.tests"}
    if spec_env is not None:
        spec["env"] = spec_env
    return render_run_toml("workflow.fabro", "goal", tmp / "run" / "binding.json", {SERVER: spec},
                           hook_env=hook_env)


def _doc(toml_text: str) -> dict | None:
    """Strict parse, exactly like the independent oracle; duplicate keys are a TOML error."""
    try:
        return tomllib.loads(toml_text)
    except tomllib.TOMLDecodeError:
        return None


def _mcp_env(toml_text: str) -> dict[str, str] | None:
    doc = _doc(toml_text)
    if doc is None:
        return None
    return doc["run"]["agent"]["mcps"][KEY]["env"]


def _hook_script(toml_text: str) -> str:
    doc = _doc(toml_text)
    if doc is None:
        return ""
    return doc["run"]["hooks"][0]["script"]


def _child_view(env: dict[str, str]) -> tuple[str, str]:
    """Run the child with exactly the env the generated run config declares for the MCP server."""
    r = subprocess.run([sys.executable, "-c", CHILD_SCRIPT], env=dict(env), cwd=str(REPO_ROOT),
                       capture_output=True, text=True, timeout=60)
    lines = r.stdout.splitlines()
    return (lines[0] if len(lines) > 0 else ""), (lines[1] if len(lines) > 1 else "")


def _hook_view(script: str) -> tuple[str, int]:
    """Apply exactly the generated hook's env prefix (the K=V assignments before the
    python executable, in script order, a later assignment for the same variable wins -
    POSIX shell semantics; shlex.split has already unquoted the values) to the host
    environment and report the effective FORGE_DATA_ROOT as seen by the hook process;
    the policy module is not executed."""
    prefix: dict[str, str] = {}
    for tok in shlex.split(script):
        if "=" in tok and tok.split("=", 1)[0].isidentifier():
            k, v = tok.split("=", 1)
            prefix[k] = v
    env = {**os.environ, **prefix}
    r = subprocess.run([sys.executable, "-c", HOOK_PROBE], env=env, cwd=str(REPO_ROOT),
                       capture_output=True, text=True, timeout=60)
    lines = r.stdout.splitlines()
    return (lines[-1].strip() if lines else ""), r.returncode


def main() -> int:
    problems: list[str] = []

    host = _new_host()
    _host(host)
    from forge_factory.common import data_root

    host_root = str(data_root())
    toml_text = _render(host, None)
    env = _mcp_env(toml_text)
    if env is None:
        problems.append("generated run config fails the strict tomllib parse")
    if env is not None and env.get("FORGE_DATA_ROOT") != host_root:
        problems.append("generated MCP env block does not pin the host FORGE_DATA_ROOT")
    hook = _hook_script(toml_text)
    if f"FORGE_DATA_ROOT={shlex.quote(host_root)}" not in hook:
        problems.append("generated policy hook does not pin the host FORGE_DATA_ROOT")
    if env is not None:
        child_root, jar = _child_view(env)
        if child_root != host_root:
            problems.append(f"isolated MCP child resolves a different data root ({child_root or '<none>'})")
        if jar != "JAR":
            problems.append("plantuml jar invisible to the child -> PLANTUML_NOT_AVAILABLE")

    override = str(host / "declared-override")
    oenv = _mcp_env(_render(host, {"FORGE_DATA_ROOT": override}))
    if oenv is None:
        problems.append("explicit declared FORGE_DATA_ROOT override breaks the strict tomllib parse")
    elif oenv.get("FORGE_DATA_ROOT") != override:
        problems.append("declared FORGE_DATA_ROOT override does not win over the generated default")
    else:
        oroot, _ = _child_view(oenv)
        if oroot != override:
            problems.append(f"isolated child ignores the declared override ({oroot or '<none>'})")

    hoverride = str(host / "hook-override")
    henv = {"FORGE_DATA_ROOT": hoverride, "FORGE_EXTRA": "x"}
    htext = _render(host, None, henv)
    if _doc(htext) is None:
        problems.append("hook_env override breaks the strict tomllib parse")
    else:
        hroot, rc = _hook_view(_hook_script(htext))
        if hroot != hoverride:
            problems.append(f"generated policy hook resolves {hroot or '<none>'}, not the declared "
                            f"hook_env override (default shadows the declared override)")
        if rc != 0:
            problems.append(f"generated policy hook script fails to execute (rc={rc})")

    if problems:
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


def test_default_env_pins_host_data_root_and_parses():
    host = _new_host()
    _host(host)
    from forge_factory.common import data_root

    env = _mcp_env(_render(host, None))
    assert env is not None, "strict tomllib parse of the generated run config failed"
    assert env["FORGE_DATA_ROOT"] == str(data_root())


def test_hook_pins_host_data_root():
    host = _new_host()
    _host(host)
    from forge_factory.common import data_root

    hook = _hook_script(_render(host, None))
    assert f"FORGE_DATA_ROOT={shlex.quote(str(data_root()))}" in hook
    assert "forge_factory.policy.fabro_hook" in hook


def test_isolated_child_resolves_host_data_root_and_sees_jar():
    host = _new_host()
    _host(host)
    from forge_factory.common import data_root

    env = _mcp_env(_render(host, None))
    assert env is not None
    child_root, jar = _child_view(env)
    assert child_root == str(data_root())
    assert jar == "JAR"


def test_declared_override_wins_and_config_still_parses():
    host = _new_host()
    _host(host)
    override = str(host / "declared-override")
    toml_text = _render(host, {"FORGE_DATA_ROOT": override})
    assert _doc(toml_text) is not None, "duplicate TOML key: strict parse failed"
    env = _mcp_env(toml_text)
    assert env is not None
    assert env["FORGE_DATA_ROOT"] == override
    child_root, _ = _child_view(env)
    assert child_root == override


def test_hook_env_override_not_shadowed_by_generated_default():
    host = _new_host()
    _host(host)
    override = str(host / "hook-override")
    toml_text = _render(host, None, {"FORGE_DATA_ROOT": override, "FORGE_EXTRA": "x"})
    assert _doc(toml_text) is not None, "strict parse failed with hook_env overrides"
    hroot, rc = _hook_view(_hook_script(toml_text))
    assert rc == 0, "generated hook script does not execute"
    assert hroot == override, f"hook resolves {hroot!r}, the declared override must win"


def test_script_mode_reports_symptom_absent_once_fixed():
    r = subprocess.run([sys.executable, str(Path(__file__).resolve())], capture_output=True,
                       text=True, timeout=180)
    assert r.returncode == 0, f"script mode exited {r.returncode}\n{r.stdout}\n{r.stderr}"
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert lines and lines[-1] == "SYMPTOM_ABSENT"
    assert "SYMPTOM_PRESENT" not in r.stdout


if __name__ == "__main__":
    raise SystemExit(main())
