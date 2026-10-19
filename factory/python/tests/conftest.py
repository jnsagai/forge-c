import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _easa_hermetic(request, monkeypatch, tmp_path_factory):
    """EASA tests run against the authored catalog and the built-in OBSERVE_ONLY policy unless a test sets its own:
    the host's registered ISO copy, reconciled catalog versions and owner policy file are not test inputs."""
    if not request.module.__name__.startswith("test_easa"):
        return
    from forge_factory.assurance import catalog, normative, policy

    d = tmp_path_factory.mktemp("easa-hermetic")
    monkeypatch.delenv(normative.ENV, raising=False)
    monkeypatch.setattr(policy, "POLICY_PATH", d / "assurance-policy.yaml")
    monkeypatch.setattr(catalog, "DERIVED_DIR", d / "derived")


@pytest.fixture(autouse=True)
def _dashboard_sign_in_on(monkeypatch):
    """The committed dashboard-access config may switch sign-in off (OD-2026-10-19-09); tests exercise the token
    mode unless a test sets FORGE_DASHBOARD_AUTH itself."""
    monkeypatch.setenv("FORGE_DASHBOARD_AUTH", "token")
