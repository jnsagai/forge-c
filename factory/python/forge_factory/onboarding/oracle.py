"""Feature 016 (OB-T002, OB-T019): the regression oracle - derived facts compared with the values written by hand in
the existing peripheral profiles and examples (FR-020). Differences are allowed only when listed, with an
explanation, in config/factory/onboarding/oracle-exceptions.yaml."""
from __future__ import annotations

from ..common import CONFIG_DIR, load_yaml

EXCEPTIONS = CONFIG_DIR / "onboarding/oracle-exceptions.yaml"
FIELDS = ("example", "fact", "hand_value", "derived_value", "explanation", "reviewed_by")


class OracleError(ValueError):
    pass


def exceptions() -> dict[tuple[str, str], dict]:
    doc = load_yaml(EXCEPTIONS) or {}
    if doc.get("schema") != "forge-c/onboarding-oracle-exceptions/0.1":
        raise OracleError("ORACLE_EXCEPTIONS_SCHEMA")
    out = {}
    for e in doc.get("exceptions") or []:
        missing = [k for k in FIELDS if k not in e or (k == "explanation" and not str(e[k]).strip())]
        if missing:
            raise OracleError(f"ORACLE_EXCEPTION_INCOMPLETE:{e.get('example')}:{e.get('fact')}:{','.join(missing)}")
        out[(e["example"], e["fact"])] = e
    return out
