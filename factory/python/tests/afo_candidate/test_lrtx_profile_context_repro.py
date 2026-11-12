"""Candidate reproducer for mnt-7e653513a54375a5 (FACTORY_MAINTENANCE, lrtx structured packets).

Defect reproduced: on the original baseline, a work order with a selected local profile
still admitted serialized packets against the legacy FORGE_LRTX_CONTEXT_TOKENS envelope
(24576) instead of the selected profile's OLLAMA_CONTEXT_LENGTH (262144). The sealed
script imports the code from the current working tree, so it exits 1 printing
SYMPTOM_PRESENT:<suffix> on the baseline and exits 0 printing SYMPTOM_ABSENT
on the fixed candidate (the success marker carries no suffix).

The retained profile-context repair is preserved. The candidate also restores the
pre-request HTTP 429 refusal path of structured.call() (time.monotonic), which the
retained patch had regressed (time.monetic) and which the inherited
test_da014_settled_usage.py::test_structured_refusal_preserves_bounded_typed_reason_
without_body_leak exercises.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "factory" / "python"))
os.environ.pop("FORGE_LRTX_CONTEXT_TOKENS", None)

SUFFIX = "lrtx-profile-context-24576-legacy-despite-selected-262144"
PROFILE_ID = "afo-cand-profile"
PROFILE_CONTEXT = 262144
PROFILE_YAML = (
    "schema: forge-c/local-profile/1\n"
    f"id: {PROFILE_ID}\n"
    "version: 1\n"
    "runtime:\n"
    "  ollama:\n"
    f'    OLLAMA_CONTEXT_LENGTH: "{PROFILE_CONTEXT}"\n'
)

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
}


def _build_workspace(root: Path):
    ws = root / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"local_profile": {"id": PROFILE_ID}}))
    profiles = root / "profiles"
    profiles.mkdir(parents=True)
    (profiles / f"{PROFILE_ID}.yaml").write_text(PROFILE_YAML)
    return ws, profiles


def _packet(structured):
    return structured.packet(
        phase="SWE.1",
        task="profile-context-repro",
        role="swe1-author",
        instructions="Measure the serialized-prompt context envelope of the selected profile.",
        sources=[],
        criteria=[],
        output_schema=OUTPUT_SCHEMA,
        model="fixture",
        with_skill=False,
        with_lessons=False,
    )


def main() -> int:
    from forge_factory.lrtx import profile as lp
    from forge_factory.lrtx import structured

    with tempfile.TemporaryDirectory() as td:
        ws, profiles = _build_workspace(Path(td))
        lp.PROFILE_DIR = profiles
        token = structured.RECOVERY_WORKSPACE.set(ws)
        try:
            try:
                p = _packet(structured)
            except Exception as exc:  # the baseline has no selected-profile envelope at all
                print(f"observed_exception={type(exc).__name__}:{str(exc)[:120]}")
                print(f"SYMPTOM_PRESENT:{SUFFIX}")
                return 1
        finally:
            structured.RECOVERY_WORKSPACE.reset(token)

    acc = p["accounting"]
    observed = (acc.get("context_tokens"), acc.get("context_basis", "<absent>"))
    expected = (PROFILE_CONTEXT, f"profile:{PROFILE_ID}")
    if observed == expected:
        print("SYMPTOM_ABSENT")
        return 0
    print(f"observed={observed[0]} basis={observed[1]} expected={expected[1]}")
    print(f"SYMPTOM_PRESENT:{SUFFIX}")
    return 1


# ---- pytest of the fix (candidate-owned) -------------------------------------------------------------


def test_selected_profile_context_envelope(monkeypatch, tmp_path):
    from forge_factory.lrtx import profile as lp
    from forge_factory.lrtx import structured

    ws, profiles = _build_workspace(tmp_path)
    monkeypatch.setattr(lp, "PROFILE_DIR", profiles)
    token = structured.RECOVERY_WORKSPACE.set(ws)
    try:
        p = _packet(structured)
    finally:
        structured.RECOVERY_WORKSPACE.reset(token)
    assert p["accounting"]["context_tokens"] == PROFILE_CONTEXT
    assert p["accounting"]["context_basis"] == f"profile:{PROFILE_ID}"
    assert p["accounting"]["fits"] is True


def test_legacy_envelope_without_selected_profile(monkeypatch):
    from forge_factory.lrtx import structured

    monkeypatch.setattr(structured, "CONTEXT_TOKENS", 24576)
    structured.RECOVERY_WORKSPACE.set(None)  # no recovery workspace -> the preserved legacy selection
    try:
        p = _packet(structured)
    finally:
        structured.RECOVERY_WORKSPACE.set(None)
    assert p["accounting"]["context_tokens"] == 24576


def test_http429_refusal_preserves_bounded_typed_reason(monkeypatch):
    # Regression mirror of the inherited test_da014_settled_usage refusal check: the
    # pre-request HTTP 429 path must not crash and must not leak the provider body.
    from forge_factory.lrtx import structured

    packet = dict(model="fixture", _messages=[], output_reserve=20, output_schema={})
    body = json.dumps({"error": {"type": "JOB_TOKEN_ENVELOPE_EXHAUSTED", "message": "PRIVATE_BODY"}}).encode()

    def denied(*a, **kw):
        raise urllib.error.HTTPError("http://localhost", 429, "refused", {}, io.BytesIO(body))

    monkeypatch.setattr(structured.urllib.request, "urlopen", denied)
    result = structured.call(packet, url="http://localhost")
    assert result["errors"] == ["CALL_REFUSED:JOB_TOKEN_ENVELOPE_EXHAUSTED"]
    assert "PRIVATE_BODY" not in str(result)


if __name__ == "__main__":
    raise SystemExit(main())
