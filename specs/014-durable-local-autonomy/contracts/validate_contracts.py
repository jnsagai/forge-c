#!/usr/bin/env python3
"""Read-only Feature 014 schema/fixture validation; never tests production runtime."""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    raise SystemExit(f"MISSING_SPEC_VALIDATOR_DEPENDENCY: {exc}") from exc

ROOT = Path(__file__).resolve().parent
SCHEMAS = {
    "semantic-proposal.schema.json",
    "completion-receipt.schema.json",
    "execution-lifecycle.schema.json",
    "offline-export-manifest.schema.json",
    "review-disposition.schema.json",
    "patch-bundle.schema.json",
}
CHECKER = FormatChecker()


@CHECKER.checks("date-time")
def is_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return True  # type validation owns non-string values
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
        return False
    # RFC 3339 permits leap seconds; validate the calendar at second 59.
    normalized = re.sub(r":60(?=[.Zz+-])", ":59", value).upper().replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(normalized).tzinfo is not None
    except ValueError:
        return False


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"NONFINITE_JSON:{value}")))


def main() -> int:
    errors: list[str] = []
    validators = {}
    actual = {p.name for p in ROOT.glob("*.schema.json")}
    if actual != SCHEMAS:
        errors.append(f"SCHEMA_INVENTORY:{sorted(actual)}")
    for name in sorted(SCHEMAS):
        try:
            schema = read(ROOT / name)
            Draft202012Validator.check_schema(schema)
            validators[name] = Draft202012Validator(schema, format_checker=CHECKER)
        except Exception as exc:  # noqa: BLE001 - checker reports malformed design artifacts
            errors.append(f"SCHEMA:{name}:{type(exc).__name__}:{exc}")
    count = positives = negatives = 0
    try:
        manifest = read(ROOT / "examples/manifest.json")
        if manifest.get("scope") != "SPEC_CONTRACTS_ONLY_NOT_RUNTIME":
            raise ValueError("INVALID_FIXTURE_SCOPE")
        fixtures = manifest["fixtures"]
        seen = set()
        for fixture in fixtures:
            name = fixture["file"]
            if Path(name).name != name or name in seen or name == "manifest.json":
                errors.append(f"INVALID_OR_DUPLICATE_FIXTURE:{name}")
                continue
            seen.add(name)
            validator = validators.get(fixture["schema"])
            if validator is None:
                errors.append(f"UNKNOWN_FIXTURE_SCHEMA:{name}:{fixture['schema']}")
                continue
            expected = fixture["expected_valid"]
            if not isinstance(expected, bool) or not fixture.get("purpose"):
                errors.append(f"INVALID_FIXTURE_EXPECTATION:{name}")
                continue
            issues = list(validator.iter_errors(read(ROOT / "examples" / name)))
            count += 1
            positives += int(expected)
            negatives += int(not expected)
            if (not issues) != expected:
                detail = issues[0].message if issues else "negative fixture accepted"
                errors.append(f"UNEXPECTED_FIXTURE_RESULT:{name}:{detail}")
        actual_examples = {p.name for p in (ROOT / "examples").glob("*.json")} - {"manifest.json"}
        if actual_examples != seen:
            errors.append(f"FIXTURE_INVENTORY:unlisted={sorted(actual_examples-seen)}:missing={sorted(seen-actual_examples)}")
        if positives == 0 or negatives == 0:
            errors.append("POSITIVE_AND_NEGATIVE_FIXTURES_REQUIRED")
    except Exception as exc:  # noqa: BLE001 - checker reports broken fixtures and manifest
        errors.append(f"FIXTURES:{type(exc).__name__}:{exc}")
    print(json.dumps({"result": "FAIL" if errors else "PASS", "scope":"SPEC_CONTRACTS_ONLY_NOT_RUNTIME",
                      "schemas":len(validators), "fixtures":count, "positive":positives,
                      "negative":negatives, "errors":errors}, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
