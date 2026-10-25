#!/usr/bin/env python3
"""Read-only Feature 014 traceability and contract checks; never a runtime test."""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
COUNT = 44


def main() -> int:
    errors: list[str] = []
    required = ('README.md', 'spec.md', 'plan.md', 'tasks.md', 'research.md',
                'local-model-design.md', 'continuous-learning.md', 'data-model.md', 'quickstart.md',
                'codex-prompt.md', 'evidence-baseline.md', 'acceptance-tests.md',
                'future-worker-promotion.md', 'validation.md', 'traceability.csv')
    for name in required:
        if not (ROOT / name).is_file():
            errors.append(f'MISSING_FILE:{name}')
    if errors:
        print(json.dumps({'result': 'FAIL', 'errors': errors}, indent=2))
        return 1
    spec = (ROOT / 'spec.md').read_text()
    tasks = (ROOT / 'tasks.md').read_text()
    tests = (ROOT / 'acceptance-tests.md').read_text()
    req_defs = re.findall(r'^- \*\*(DA-FR-\d{3}) \[(US\d+)\]\*\*:', spec, re.M)
    task_defs = re.findall(r'^- \[([ xX])\] \*\*(DA-T\d{3}) \[(US\d+)\]\*\* (.*)$', tasks, re.M)
    test_defs = re.findall(r'^## (DA-AT-\d{3}) .+$', tests, re.M)
    expected_r = {f'DA-FR-{n:03d}' for n in range(1, COUNT + 1)}
    expected_t = {f'DA-T{n:03d}' for n in range(1, COUNT + 1)}
    expected_a = {f'DA-AT-{n:03d}' for n in range(1, COUNT + 1)}
    for name, ids, expected in (
        ('requirements', [x[0] for x in req_defs], expected_r),
        ('tasks', [x[1] for x in task_defs], expected_t),
        ('tests', test_defs, expected_a),
    ):
        if len(ids) != COUNT or set(ids) != expected:
            errors.append(f'ID_COVERAGE:{name}')
    with (ROOT / 'traceability.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != COUNT or {r['requirement_id'] for r in rows} != expected_r:
        errors.append('TRACE_REQUIREMENT_COVERAGE')
    if {r['task_id'] for r in rows} != expected_t or {r['acceptance_test_id'] for r in rows} != expected_a:
        errors.append('TRACE_TASK_TEST_COVERAGE')
    story = dict(req_defs)
    task_by_id = {x[1]: x for x in task_defs}
    for row in rows:
        r, t, a = row['requirement_id'], row['task_id'], row['acceptance_test_id']
        if row['implementation_status'] != 'NOT_IMPLEMENTED':
            errors.append(f'DESIGN_TIME_STATUS_CHANGED:{r}')
        if story.get(r) != row['story'] or t not in task_by_id:
            errors.append(f'TRACE_STORY:{r}')
            continue
        checked, _, task_story, body = task_by_id[t]
        if task_story != row['story'] or r not in body or a not in body:
            errors.append(f'TASK_TRACE:{t}')
        block = re.search(rf'^## {re.escape(a)} .*?(?=^## |\Z)', tests, re.M | re.S)
        if not block or f'**Requirement:** {r}' not in block.group(0):
            errors.append(f'TEST_TRACE:{a}')
        elif any(f'**{field}:**' not in block.group(0) for field in ('Level','Status','Given','When','Then','Evidence','Expected')):
            errors.append(f'TEST_FIELDS:{a}')
        if checked != ' ':
            refs = re.findall(r'`(evidence/v0\.4/runs/[^`]+/latest\.json)`', body)
            if not refs:
                errors.append(f'TASK_WITHOUT_EVIDENCE:{t}')
            for ref in refs:
                try:
                    evidence = json.loads((REPO / ref).read_text())
                    if evidence.get('status') != 'PASS' or evidence.get('exit_code') != 0:
                        errors.append(f'TASK_NONPASS_EVIDENCE:{t}')
                except (OSError, ValueError):
                    errors.append(f'TASK_UNREADABLE_EVIDENCE:{t}')
    for p in ROOT.rglob('*.md'):
        content = p.read_text()
        if re.search(r'\[NEEDS CLARIFICATION|\[FEATURE NAME\]|\$ARGUMENTS', content):
            errors.append(f'UNRESOLVED_TEMPLATE:{p.relative_to(ROOT)}')
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if re.match(r'^[a-z][a-z0-9+.-]*:', target) or target.startswith('#'):
                continue
            dest = target.split('#', 1)[0]
            if dest and not (p.parent / dest).exists():
                errors.append(f'BROKEN_LOCAL_LINK:{p.relative_to(ROOT)}:{target}')
    check = subprocess.run([sys.executable, str(ROOT / 'contracts/validate_contracts.py')],
                           text=True, capture_output=True, check=False)
    try:
        contract_result = json.loads(check.stdout)
    except ValueError:
        contract_result = {'output': check.stdout, 'error': check.stderr}
    if check.returncode:
        errors.append('CONTRACT_VALIDATION_FAILED')
    result = {'result': 'FAIL' if errors else 'PASS', 'scope': 'SPEC_CONTRACTS_ONLY_NOT_RUNTIME',
              'requirements': len(req_defs), 'tasks': len(task_defs), 'acceptance_tests': len(test_defs),
              'contracts': contract_result, 'errors': errors}
    print(json.dumps(result, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
