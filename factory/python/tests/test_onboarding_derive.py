"""Feature 016 OB-T018 (FR-006, FR-022, SC-004): the derivation is repeatable, sensitive to every input byte, and makes
no model call."""
import json
import subprocess
import sys
import time

from forge_factory import onboarding as OB
from forge_factory.common import REPO_ROOT
from onboarding_util import example_copy, need_inputs


def test_same_inputs_same_hash_any_input_change_new_hash(tmp_path, monkeypatch):
    need_inputs()
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    t = time.time()
    a = OB.derive(REPO_ROOT / "examples/0012d-st-cube-usart-hal", "WO-OB-A")
    elapsed = time.time() - t
    b = OB.derive(REPO_ROOT / "examples/0012d-st-cube-usart-hal", "WO-OB-A")
    assert a["sha256"] == b["sha256"] and a["status"] == "READY_FOR_OWNER"
    ex = example_copy(tmp_path, "0012d-st-cube-usart-hal",
                      replace_inputs={"RM0486-rev4-ch65-usart.md": lambda t: t + "\n"})
    c = OB.derive(ex, "WO-OB-A")
    assert c["sha256"] != a["sha256"]
    changed = {i["path"] for i in c["inputs"]} & {i["path"] for i in a["inputs"]}
    assert any(next(x for x in c["inputs"] if x["path"] == p)["sha256"] != next(x for x in a["inputs"]
               if x["path"] == p)["sha256"] for p in changed)
    assert elapsed < 600                                                # SC-004 (recorded: well under 10 minutes)
    print(json.dumps({"derive_seconds": round(elapsed, 1)}))


def test_derivation_loads_no_model_client(tmp_path):
    need_inputs()
    code = ("import sys, json; from forge_factory import onboarding as OB; "
            f"OB.derive({str(REPO_ROOT / 'examples/0014d-st-cube-crc-hal')!r}, 'WO-OB-M'); "
            "print(json.dumps(sorted(m for m in sys.modules if m.startswith('forge_factory.'))))")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600,
                       env={**__import__("os").environ, "FORGE_STATE_DIR": str(tmp_path / "state")})
    assert r.returncode == 0, r.stderr[-800:]
    mods = json.loads(r.stdout.strip().splitlines()[-1])
    assert not [m for m in mods if m.startswith(("forge_factory.acp", "forge_factory.llm_gateway", "forge_factory.lrtx",
                                                 "forge_factory.fabro.client", "forge_factory.afo.planner"))]
