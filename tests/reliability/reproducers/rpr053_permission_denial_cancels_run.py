"""RPR-053 (LL r165): the ACP proxy answered a denied permission request ('Edit files') with outcome 'cancelled';
for ACP that means the prompt turn was cancelled, so Codex ended the turn and Fabro failed the whole run."""
import sys

SIG = "denied permission answered as a cancelled turn"


def main() -> int:
    from forge_factory.acp import proxy

    p = proxy.Proxy.__new__(proxy.Proxy)  # from_agent only routes one message; no agent process is needed
    sent: list[dict] = []
    p._log = lambda rec: None
    p.to_agent = sent.append
    p.to_client = lambda m: None
    p.from_agent({"jsonrpc": "2.0", "id": 7, "method": "session/request_permission", "params": {
        "sessionId": "S", "toolCall": {"kind": "edit", "title": "Edit files"},
        "options": [{"optionId": "allow", "name": "Allow", "kind": "allow_once"},
                    {"optionId": "deny", "name": "Reject", "kind": "reject_once"}]}})
    outcome = sent[0]["result"]["outcome"] if sent and "result" in sent[0] else {}
    if outcome.get("outcome") != "selected" or outcome.get("optionId") != "deny":
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
