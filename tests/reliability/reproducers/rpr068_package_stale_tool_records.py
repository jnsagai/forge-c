"""RPR-068 (TAA-RCC FND-04, signed TAA v1.1): every package shipped the 2026-10-14 host inventory as
configuration/toolchain_versions.json (qwen3:8b, Renode missing, no Codex/Claude) and listed Renode as a disabled
tool although the run used it."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "package tool records are not this run's tools"


def main() -> int:
    from forge_factory.common import REPO_ROOT
    from forge_factory.release import finalize as F

    with tempfile.TemporaryDirectory() as d:
        ws, stage = Path(d) / "ws", Path(d) / "stage"
        (ws / "evidence").mkdir(parents=True)
        (ws / ".forge-run").mkdir()
        (ws / "evidence/tool-results.jsonl").write_text(json.dumps({
            "server": "forge-sim-mcp", "op": "run_renode", "phase": "SWE.5", "role": "swe5-author", "run_id": "r",
            "ts_utc": "2026-10-20T00:00:00Z", "result": {"status": "PASS", "provenance": {"tool": "renode",
                                                                                          "version": "Renode v1.17.0"}}}) + "\n")
        (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": "deepseek-flash", "provider": "deepseek",
            "acp_authors": {"model": "gpt-6.1-sol", "nodes": ["a"]}, "acp_inspectors": {"model": "claude-opus-5-5", "nodes": ["i"]}}))
        stage.mkdir()
        if hasattr(F, "stage_tool_records"):
            F.stage_tool_records(ws, stage)
        else:  # the baseline behaviour: the shipped host inventory
            inv = REPO_ROOT / "evidence/v0.4/inventory/tool-inventory.json"
            (stage / "configuration").mkdir()
            (stage / "configuration/toolchain_versions.json").write_bytes(inv.read_bytes())
        text = (stage / "configuration/toolchain_versions.json").read_text()
    if "Renode v1.17.0" not in text or "claude-opus-5-5" not in text or "qwen3" in text:
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
