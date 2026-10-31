"""RPR-073 (process-first design review, G3/D10, 2026-10-31): the structured packet input_hash covered the model NAME
and sampling only. A different model file (digest) pinned under the same alias by the work order's selected local
profile produced the same input_hash, so visit/inspector checkpoints keyed on it were reused across model identities
(lrtx/structured.py packet(); lrtx/visit.py run_task base_hash)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "packet input_hash unchanged when the pinned model digest changes under the same alias"
PROFILE_ID = "rpr073-identity"
MODEL = "rpr073-model:q8"
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["a"], "properties": {"a": {"type": "string"}}}


def _profile(digest: str) -> str:
    return (
        "schema: forge-c/local-profile/1\n"
        f"id: {PROFILE_ID}\n"
        "version: 1\n"
        "models:\n"
        f"  default: {MODEL}\n"
        "  allowed:\n"
        f"    {MODEL}:\n"
        f"      digest: {digest}\n"
        "      quantization: Q8_0\n"
        "runtime:\n"
        "  ollama:\n"
        '    OLLAMA_CONTEXT_LENGTH: "32768"\n'
    )


def main() -> int:
    from forge_factory.lrtx import profile as lp
    from forge_factory.lrtx import structured as S

    hashes = []
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        profiles = root / "profiles"
        profiles.mkdir()
        ws = root / "ws"
        (ws / ".forge-run").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"local_profile": {"id": PROFILE_ID}}))
        lp.PROFILE_DIR = profiles
        token = S.RECOVERY_WORKSPACE.set(ws)
        try:
            for digest in ("a" * 64, "b" * 64):
                (profiles / f"{PROFILE_ID}.yaml").write_text(_profile(digest))
                p = S.packet(phase="SWE.1", task="rpr073", role="swe1-author", instructions="Answer.", sources=[],
                             criteria=[], output_schema=SCHEMA, model=MODEL, with_skill=False, with_lessons=False)
                hashes.append(p["input_hash"])
        finally:
            S.RECOVERY_WORKSPACE.reset(token)
    if len(hashes) != 2 or not all(hashes):
        print("REPRODUCER_ERROR:NO_HASH")
        return 2
    if hashes[0] == hashes[1]:
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
