"""RPR-080 (Fabro SWE.1 run WO-F014-SWE1-OBL-20261031-01 on Omniverse2, 2026-10-31): the work order was launched right
after `stack start`, before the stack's llama-server was healthy; the gateway refused the first structured calls
(unavailable_error), those calls used the one development repair pass, and SWE.1 ended BLOCKED with zero tokens.

Scenario: profile selection (the launch-time check) with this stack's services.json recording a llama-server whose
health URL does not answer; every other launch check passes. Symptom: selection accepts the launch anyway."""
import copy
import json
import socket
import sys
import tempfile
from pathlib import Path

SIG = "work order launch accepted while the stack's recorded llama-server is not healthy"
PROFILE = "local-rtx-v2-omniverse2-q38-aspice-stepwise-medium"


def main() -> int:
    from forge_factory.lrtx import profile as lp

    prof = copy.deepcopy(lp.load(PROFILE))
    prof["runtime"]["model_ready_wait_s"] = 1
    model = prof["models"]["default"]
    with tempfile.TemporaryDirectory() as td, socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]  # bound but never listening: the health URL does not answer
        root = Path(td) / "lrtx"
        (root / "run").mkdir(parents=True)
        (root / "run/services.json").write_text(json.dumps({"processes": {"llama_server": {
            "pid": 1, "health": f"http://127.0.0.1:{port}/health"}}}))
        env = {"FORGE_LRTX_ROOT": str(root), "FORGE_OLLAMA_URL": "http://127.0.0.1:1"}
        env.update({k: str(Path(td) / k.lower()) for k in prof["deployment"]["writable_env"]})
        lp.load = lambda _pid: prof
        lp.isolation_issues = lambda *_a, **_k: []
        lp.endpoint_issues = lambda *_a, **_k: []
        lp.network_enforcement = lambda: {"status": "DENIED_VERIFIED"}
        lp.model_identity = lambda _p, m, _u: {"model": m, "status": "MATCH"}
        try:
            lp.select(PROFILE, model=model, provider=prof["provider"], code_model=None, acp_authors=None,
                      acp_inspectors=None, env=env)
        except lp.ProfileRefused as exc:
            if "MODEL_SERVER_NOT_READY" in str(exc):
                print("SYMPTOM_ABSENT")
                return 0
            print(f"REPRODUCER_ERROR:REFUSED_FOR_ANOTHER_REASON:{str(exc)[:160]}")
            return 2
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
