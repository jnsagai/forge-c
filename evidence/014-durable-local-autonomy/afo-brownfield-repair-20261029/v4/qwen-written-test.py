"""SWE3-10 reproducer (PLANTUML_NOT_AVAILABLE for the declared unit diagrams).

Root cause: render_run_toml pins PYTHONPATH/FORGE_STATE_DIR for the generated isolated MCP
servers and the policy hook, but omits FORGE_DATA_ROOT. An isolated MCP child then resolves
the data root to the default instead of the host's declared root, so the installed plantuml
jar (data_root()/toolchains/plantuml/*.jar) is invisible to the SWE.3 inspection and
render_ok reports PLANTUML_NOT_AVAILABLE even though java and the jar are installed on the
host (observed: isolated_mcp_children_observed=9, children_with_data_root=0,
plantuml_jar_installed=true).

Script mode (baseline reproducer check):
    python test_swe3_10_data_root.py
      exit 1 + SYMPTOM_PRESENT:<signature>   while the defect exists
      exit 0 + SYMPTOM_ABSENT                once fixed
pytest mode: the test_* functions below verify the fix.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "factory" / "python"))  # script mode from any cwd

SERVER = "forge-tests-mcp"
KEY = SERVER.replace("-", "_")
SIG = "SWE3-10-PLANTUML_NOT_AVAILABLE-DATA-ROOT-NOT-PROPAGATED"

# Resolves the tool context exactly the way the frozen inspection does
# (forge_factory.inspection.swtrace._plantuml_jar / render_ok), from inside a
# subprocess whose environment is exactly the env block the generated run
# config declares for the isolated MCP server.
CHILD_SCRIPT = (
    "import forge_factory.common as c\n"
    "jar = sorted((c.data_root() / 'toolchains' / 'plantuml').glob('*.jar'))\n"
    "print(c.data_root())\n"
    "print('JAR' if jar else 'NOJAR')\n"
)


def _unq(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
        v = v[1:-1]
    return v.replace('\\"', '"').replace("\\\\", "\\")


def _render(data_root_dir: Path, spec_env: dict[str, str] | None = None) -> str:
    from forge_factory.fabro.runconfig import render_run_toml

    spec: dict = {"module": "forge_factory.mcp.servers.tests"}
    if spec_env:
        spec["env"] = spec_env
    return render_run_toml("workflow.fabro", "goal", data_root_dir / "binding.json", {SERVER: spec})


def _env_table(toml_text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    in_env = False
    for line in toml_text.splitlines():
        if line.startswith(f"[run.agent.mcps.{KEY}.env]"):
            in_env = True
            continue
        if in_env:
            if line.startswith("["):
                break
            if not line.strip() or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = _unq(v)
    return env


def _hook_script(toml_text: str) -> str:
    for line in toml_text.splitlines():
        if line.startswith("script = ") and "fabro_hook" in line:
            return _unq(line.partition("=")[2])
    return ""


def _scenario() -> tuple[Path, str, dict[str, str], str]:
    """Host side: FORGE_DATA_ROOT declared (non-default) with the plantuml jar installed there."""
    tmp = Path(tempfile.mkdtemp(prefix="afo-swe310-"))
    os.environ["FORGE_DATA_ROOT"] = str(tmp)
    (tmp / "toolchains" / "plantuml").mkdir(parents=True)
    (tmp / "toolchains" / "plantuml" / "plantuml.jar").write_bytes(b"fake-plantuml-jar")
    from forge_factory.common import data_root

    toml_text = _render(tmp)
    return tmp, str(data_root()), _env_table(toml_text), _hook_script(toml_text)


def _child_view(env: dict[str, str]) -> tuple[str, str]:
    """Run the child with exactly the env the generated run config declares for the MCP server."""
    r = subprocess.run([sys.executable, "-c", CHILD_SCRIPT], env=dict(env), cwd=str(REPO_ROOT),
                       capture_output=True, text=True, timeout=60)
    lines = r.stdout.splitlines()
    return (lines[0] if len(lines) > 0 else ""), (lines[1] if len(lines) > 1 else "")


def main() -> int:
    _, host_root, env, hook = _scenario()
    problems: list[str] = []
    if env.get("FORGE_DATA_ROOT") != host_root:
        problems.append("generated MCP env block does not pin FORGE_DATA_ROOT")
    if f"FORGE_DATA_ROOT={shlex.quote(host_root)}" not in hook:
        problems.append("generated policy hook does not pin FORGE_DATA_ROOT")
    child_root, jar = _child_view(env)
    if child_root != host_root:
        problems.append(f"isolated MCP child resolves a different data root ({child_root or '<none>'})")
    if jar != "JAR":
        problems.append("plantuml jar invisible to the child -> PLANTUML_NOT_AVAILABLE")
    if problems:
        print(f"SYMPTOM_PRESENT:{SIG}")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


def test_mcp_env_pins_data_root():
    _, host_root, env, _ = _scenario()
    assert env.get("FORGE_DATA_ROOT") == host_root


def test_hook_pins_data_root():
    _, host_root, _, hook = _scenario()
    assert f"FORGE_DATA_ROOT={shlex.quote(host_root)}" in hook
    assert "forge_factory.policy.fabro_hook" in hook


def test_isolated_child_resolves_host_data_root_and_sees_jar():
    _, host_root, env, _ = _scenario()
    child_root, jar = _child_view(env)
    assert child_root == host_root
    assert jar == "JAR"


def test_declared_env_overrides_still_appear_after_defaults():
    tmp = Path(tempfile.mkdtemp(prefix="afo-swe310-ovr-"))
    os.environ["FORGE_DATA_ROOT"] = str(tmp)
    override = str(tmp / "declared-override")
    toml_text = _render(tmp, {"FORGE_DATA_ROOT": override})
    first = toml_text.find("FORGE_DATA_ROOT = ")
    last = toml_text.rfind("FORGE_DATA_ROOT = ")
    assert first != -1 and last > first, "declared override must follow the generated default"
    assert _env_table(toml_text)["FORGE_DATA_ROOT"] == override


def test_script_mode_reports_symptom_absent_once_fixed():
    r = subprocess.run([sys.executable, str(Path(__file__).resolve())], capture_output=True,
                       text=True, timeout=180)
    assert r.returncode == 0, f"script mode exited {r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "SYMPTOM_ABSENT" in r.stdout
    assert "SYMPTOM_PRESENT" not in r.stdout


if __name__ == "__main__":
    raise SystemExit(main())
