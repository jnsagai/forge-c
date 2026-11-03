"""Owner 2026-11-03: the cloud comparison line uses Claude as both author and inspector (Codex credits gone)."""
from forge_factory.lrtx import profile as P


def test_claude_inspector_profile_differs_from_codex_profile_only_in_the_inspector_role():
    claude, codex = P.load("cloud-bridge-claude-author-claude-inspector"), P.load("cloud-bridge-claude-author-codex-inspector")
    assert P.role_models(claude) == {"author": "claude-opus-5-5", "inspector": "claude-opus-5-5"}
    assert P.role_models(codex)["inspector"] == "gpt-6.1-sol"
    strip = lambda p: {k: v for k, v in p.items() if k not in ("id", "description", "structured", "_path", "_sha256")}
    assert strip(claude) == strip(codex)
    sc, sx = dict(claude["structured"]), dict(codex["structured"])
    sc.pop("role_models"), sx.pop("role_models")
    assert sc == sx
