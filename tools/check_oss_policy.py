"""Fail closed on declared proprietary/cloud dependencies.

This checks a manifest's consistency; it does NOT independently audit
upstream license texts or prove a binary is open source.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

FORBIDDEN = ('coverity', 'parasoft', 'codebeamer', 'enterprise architect', 'paid api', 'deepseek api', 'codex service', 'closed')


def validate(record: dict) -> list[str]:
    policy = record.get('policy', {})
    errors: list[str] = []
    for key, expected in (
        ('allow_paid_api', False),
        ('allow_proprietary_static_analyzer', False),
        ('allow_closed_source_models', False),
        ('local_inference_only', True),
        ('safety_claim_requires_human_approval', True),
    ):
        if policy.get(key) is not expected:
            errors.append(f'policy.{key} not {expected}')
    core = record.get('core', [])
    if not isinstance(core, list) or not core:
        return errors + ['no core tool inventory']
    for item in core:
        if not isinstance(item, dict):
            errors.append('core record is not an object')
            continue
        label = item.get('name', '')
        license_ = item.get('license', '')
        if not isinstance(label, str) or not isinstance(license_, str) or not label or not license_:
            errors.append('core entry missing name/license')
            continue
        if any(blocked in label.lower() for blocked in FORBIDDEN):
            errors.append(f'forbidden service included in core: {label}')
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--config', default=str(Path(__file__).resolve().parents[1] / 'config/oss-tools.json'))
    args = p.parse_args()
    try:
        record = json.loads(Path(args.config).read_text(encoding='utf-8'))
        errors = validate(record)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    for error in errors:
        print('OSS_POLICY_FAIL:', error)
    if not errors:
        print('OSS_POLICY_DECLARATION_PASS (upstream license review still required)')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
