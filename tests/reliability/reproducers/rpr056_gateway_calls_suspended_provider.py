"""RPR-056 (h001): with DeepSeek suspended (OD-2026-10-20-03), Fabro's server-side run-title generation still reached
the DeepSeek API through the forge gateway once per run; the gateway forwarded every request it received."""
import sys
import tempfile
from pathlib import Path

SIG = "gateway forwards a request to a suspended provider"


def main() -> int:
    import httpx
    from fastapi.testclient import TestClient

    from forge_factory import llm_gateway as gw

    calls = []

    def upstream(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "t"}}]})

    with tempfile.TemporaryDirectory() as d:
        app = gw.create_app("https://api.deepseek.com", Path(d) / "usage.jsonl", transport=httpx.MockTransport(upstream))
        TestClient(app).post("/v1/chat/completions",
                             json={"model": "deepseek-flash", "messages": [{"role": "user", "content": "title"}]})
    if calls:
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
