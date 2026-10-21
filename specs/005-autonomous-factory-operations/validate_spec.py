#!/usr/bin/env python3
"""Read-only consistency/contract validation for proposed Forge-C Feature 005 specs.

Dependencies: PyYAML and jsonschema. This does not test any production runtime.
Run: python3 specs/005-autonomous-factory-operations/validate_spec.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker, ValidationError
except ImportError as exc:
    raise SystemExit(f"MISSING_SPEC_VALIDATOR_DEPENDENCY: {exc}") from exc

ROOT = Path(__file__).resolve().parent
CONTRACTS = ROOT / "contracts"
EXPECTED = {"requirements": 72, "tasks": 75, "tests": 66}
REPO = ROOT.parents[1]


def evidence_ok(line: str) -> bool:
    """A ticked task cites evidence records that exist and PASSED (scripts/mark_task.py writes them)."""
    refs = re.findall(r"`(evidence/v0\.4/runs/[^`]+/latest\.json)`", line)
    if "✅ Evidence:" not in line or not refs:
        return False
    for ref in refs:
        try:
            rec = json.loads((REPO / ref).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if rec.get("status") != "PASS" or rec.get("exit_code") != 0:
            return False
    return True


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    errors: list[str] = []
    req = read_csv(ROOT / "requirements.csv")
    tasks = read_csv(ROOT / "planned-traceability.csv")
    requirement_ids = {r["requirement_id"] for r in req}
    task_ids = {t["task_id"] for t in tasks}
    spec = (ROOT / "spec.md").read_text(encoding="utf-8")
    tasks_md = (ROOT / "tasks.md").read_text(encoding="utf-8")
    at_md = (ROOT / "acceptance-tests.md").read_text(encoding="utf-8")
    test_ids = set(re.findall(r"\bAT-\d{3}\b", at_md))
    for what, count in (("requirements", len(req)), ("tasks", len(tasks)), ("tests", len(test_ids))):
        if count != EXPECTED[what]:
            errors.append(f"COUNT:{what}:{count}!={EXPECTED[what]}")
    if len(requirement_ids) != len(req) or len(task_ids) != len(tasks):
        errors.append("DUPLICATE_REQUIREMENT_OR_TASK")
    if sorted(requirement_ids) != [f"AFO-FR-{i:03d}" for i in range(1, 73)]:
        errors.append("REQUIREMENT_ID_GAP")
    if sorted(task_ids) != [f"AFO-T{i:03d}" for i in range(1, 76)]:
        errors.append("TASK_ID_GAP")
    if test_ids != {f"AT-{i:03d}" for i in range(1, 67)}:
        errors.append("TEST_ID_GAP")
    for r in req:
        if r["requirement_id"] not in spec or r["implementation_status"] != "NOT_IMPLEMENTED":
            errors.append(f"REQUIREMENT_STATUS:{r['requirement_id']}")
        rs = [t for t in r["planned_tasks"].split(";") if t]
        ts = [t for t in r["acceptance_tests"].split(";") if t]
        if not rs or not ts or any(t not in task_ids for t in rs) or any(t not in test_ids for t in ts):
            errors.append(f"MISSING_TRACE:{r['requirement_id']}")
    for t in tasks:
        # Unchecked by default; a box is checked only with PASS evidence (owner 2026-10-21). The CSV
        # implementation_status stays the design-time value; run status comes from forge_factory.afo.status.
        line = re.search(rf"^- \[([ xX])\] \*\*{re.escape(t['task_id'])} .*$", tasks_md, re.M)
        if not line or t["implementation_status"] != "NOT_IMPLEMENTED":
            errors.append(f"TASK_MISSING:{t['task_id']}")
        elif line.group(1) != " " and not evidence_ok(line.group(0)):
            errors.append(f"TASK_MARKED_DONE_WITHOUT_EVIDENCE:{t['task_id']}")
        if any(r not in requirement_ids for r in t["planned_requirement_refs"].split(";")):
            errors.append(f"TASK_BAD_REQUIREMENTS:{t['task_id']}")
        if any(a not in test_ids for a in t["planned_test_refs"].split(";")):
            errors.append(f"TASK_BAD_TESTS:{t['task_id']}")
    for t in test_ids:
        if f"**{t} —" not in at_md:
            errors.append(f"TEST_SCENARIO_MISSING:{t}")
    schemas: dict[str, dict] = {}
    for p in sorted(CONTRACTS.glob("*.schema.json")):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(s)
            schemas[p.name] = s
        except Exception as exc:  # noqa: BLE001 - read-only checker reports invalid spec
            errors.append(f"SCHEMA:{p.name}:{exc}")
    for p in sorted(CONTRACTS.glob("*.yaml")):
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"YAML:{p.name}:{exc}")
    for p in sorted((CONTRACTS / "examples").glob("*.example.json")):
        dest = "operational-readiness.schema.json" if p.name == "readiness.example.json" else p.name.replace(".example.json", ".schema.json")
        if dest not in schemas:
            errors.append(f"SCHEMA_NOT_FOUND_FOR_EXAMPLE:{p.name}:{dest}")
            continue
        try:
            Draft202012Validator(schemas[dest], format_checker=FormatChecker()).validate(json.loads(p.read_text()))
        except (ValidationError, ValueError) as exc:
            errors.append(f"EXAMPLE:{p.name}:{str(exc).splitlines()[0]}")
    if "afo-policy.schema.json" in schemas:
        policy = yaml.safe_load((CONTRACTS / "afo-policy.example.yaml").read_text())
        val = Draft202012Validator(schemas["afo-policy.schema.json"])
        errs = list(val.iter_errors(policy))
        if errs:
            errors.append("EXAMPLE_POLICY_FAIL:" + errs[0].message)
        bad = dict(policy)
        bad["mode"] = "ACTIVE"
        if val.is_valid(bad):
            errors.append("POLICY_ACTIVE_WITHOUT_AUTH_ACCEPTED")
        bad = json.loads(json.dumps(policy))
        bad["maintenance"]["auto_promote_factory_code"] = True
        if val.is_valid(bad):
            errors.append("POLICY_UNSAFE_CODE_DEPLOY_ACCEPTED")
    if errors:
        print(json.dumps({"result": "FAIL", "errors": errors}, indent=2))
        return 1
    print(json.dumps({"result": "PASS", "scope": "SPEC_CONTRACTS_ONLY_NOT_RUNTIME",
                      **EXPECTED, "schemas": len(schemas), "examples": len(list((CONTRACTS / "examples").glob("*.json")))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
