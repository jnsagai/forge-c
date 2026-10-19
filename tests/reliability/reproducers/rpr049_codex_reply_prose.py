"""RPR-049 (r143-r154, r153 SWE.1): Codex authors added prose to most final replies and twice replied without the
JSON contract; the ACP path put the reply rule only in the middle of a long prompt (TOOL_NOTE first, task text, the
task's own 'Finish with ONLY this JSON' far from the end) and ran Codex at its default verbosity."""
import sys

SIG = "Codex ACP prompt has no trailing reply rule and default verbosity"


def main() -> int:
    from forge_factory.acp import codex_home, proxy

    cfg = codex_home.config_text()
    p = proxy.Proxy.__new__(proxy.Proxy)  # from_client only rewrites the message; no agent process is needed
    p._log = lambda rec: None
    msg = {"jsonrpc": "2.0", "id": 3, "method": "session/prompt",
           "params": {"sessionId": "S", "prompt": [{"type": "text", "text": "do the task"}]}}
    last = p.from_client(msg)["params"]["prompt"][-1]["text"]
    if 'model_verbosity = "low"' not in cfg or "final message must be exactly the JSON" not in last:
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
