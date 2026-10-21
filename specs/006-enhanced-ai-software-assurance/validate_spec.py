#!/usr/bin/env python3
"""Design-only validation for Spec Kit feature 006. NEVER treated as product verification."""
from pathlib import Path
import csv, json, re, sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

def evidence_ok(line: str) -> bool:
    """A checked task cites evidence records that exist and PASSED (scripts/mark_task.py writes them)."""
    refs = re.findall(r'`(evidence/v0\.4/runs/[^`]+/latest\.json)`', line)
    if '✅ Evidence:' not in line or not refs:
        return False
    for ref in refs:
        try:
            rec = json.loads((REPO/ref).read_text())
        except (OSError, ValueError):
            return False
        if rec.get('status') != 'PASS' or rec.get('exit_code') != 0:
            return False
    return True

def main() -> int:
    try:
        import yaml
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        print(f"BLOCKED: dependency {exc}", file=sys.stderr)
        return 2
    schemas={p.name[:-12]: json.loads(p.read_text()) for p in (ROOT/'contracts').glob('*.schema.json')}
    for name, doc in schemas.items():
        Draft202012Validator.check_schema(doc)
    for p in (ROOT/'contracts/examples').glob('*.example.json'):
        key=p.name[:-13]
        assert key in schemas, f'Missing schema for {p.name}: {key}'
        Draft202012Validator(schemas[key]).validate(json.loads(p.read_text()))
    pol=yaml.safe_load((ROOT/'contracts/assurance-policy.example.yaml').read_text())
    Draft202012Validator(schemas['assurance-policy']).validate(pol)
    assert pol['mode']=='OBSERVE_ONLY' and not pol['allow_change_asil_from_profile']
    assert not pol['allow_sup_man_workflows'] and not pol['safety_signoff_by_ai']
    catalog=yaml.safe_load((ROOT/'contracts/iso26262-6-2018-methods.working.yaml').read_text())
    methods=catalog['methods'];assert len(methods)==47,len(methods)
    assert len(set(m['method_id'] for m in methods))==47
    assert set(x['table'] for x in catalog['table_inventory'])==set(range(1,16))
    assert sum(x['asil_b_highly_recommended_count'] for x in catalog['table_inventory'])==47
    assert next(x for x in catalog['table_inventory'] if x['table']==12)['asil_b_highly_recommended_count']==0
    assert all(m['asil_recommendations']['B']=='++' and not m['normative_checked'] for m in methods)
    assert all(m['recommendation_source']=='SECONDARY_WORKING_INDEX' for m in methods)
    assert catalog['document_status']=='SECONDARY_WORKING_INDEX_NOT_AUTHORIZED_STANDARD'
    enhanced=yaml.safe_load((ROOT/'contracts/enhanced-techniques.yaml').read_text())
    assert len(enhanced['techniques'])==30
    req=list(csv.DictReader((ROOT/'requirements.csv').open()))
    trace=list(csv.DictReader((ROOT/'planned-traceability.csv').open()))
    assert len(req)==72 and len(trace)==72
    assert len(set(x['id'] for x in req))==72
    assert set(x['id'] for x in req)==set(x['requirement_id'] for x in trace)
    tasks=(ROOT/'tasks.md').read_text(); tests=(ROOT/'acceptance-tests.md').read_text()
    # Unchecked by default; a box is checked only with PASS evidence (owner 2026-10-21).
    tid=set()
    for line,box,t in re.findall(r'^(- \[([ xX])\] \*\*(EASA-T\d{3}).*)$',tasks,re.M):
        assert box==' ' or evidence_ok(line), f'{t} checked without PASS evidence'
        tid.add(t)
    aid=set(re.findall(r'^- \*\*(EASA-AT-\d{3})',tests,re.M))
    assert len(tid)>=70 and len(aid)>=80, (len(tid),len(aid))
    for x in trace:
        assert x['tasks'] and x['tests'] and x['evidence']=='NOT_IMPLEMENTED'
        assert set(x['tasks'].split(';')) <= tid
        assert set(x['tests'].split(';')) <= aid
    required=['spec.md','plan.md','tasks.md','research.md','architecture.md','data-model.md','acceptance-tests.md','assurance-profiles.md','quickstart.md']
    for p in required: assert (ROOT/p).exists(),p
    print(f'PASS DESIGN ONLY: {len(req)} FR, {len(tid)} tasks, {len(aid)} AT, {len(methods)} provisional ASIL-B ++ refs, {len(schemas)} schemas, 30 enhanced techniques')
    print('NOT TESTED: runtime, real tools, HIL, ISO conformance, production release, ASPICE rating.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
