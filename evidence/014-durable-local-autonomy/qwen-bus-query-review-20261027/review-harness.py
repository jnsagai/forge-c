"""One externally authorized read-only engineering obligation; no runtime repair."""
import ast
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from forge_factory.common import utc_now
from forge_factory.knowledge import experience as E
from forge_factory.knowledge.store import LessonStore
from forge_factory.lrtx import structured as S

os.umask(0o077)
Q = Path('/mnt/data/forge-c/inspector-014-b309039')
R = Q / 'host-bus-fbd8bc8/repo'
O = Q / 'runs/qwen-bus-query-review-20261027'
REV = 'fbd8bc89967b68ed4e99e4c63fe12784f135e62f'
assert subprocess.check_output(['git', '-C', str(R), 'rev-parse', 'HEAD'], text=True).strip() == REV
assert not subprocess.check_output(['git', '-C', str(R), 'status', '--porcelain'], text=True).strip()
O.mkdir(exist_ok=True)
ledger = O / 'accounting.json'
state = {'schema': 'forge-c/external-engineering-study/1', 'started_at': utc_now(),
         'source_revision': REV, 'authority': 'owner remote Qwen engineering-work request 2026-10-27',
         'scope': 'READ_ONLY_BUS_QUERY_HELPER_REVIEW_NOT_REPAIR_OR_ROLE_QUALIFICATION',
         'model': 'qwen3.6:35b-a3b', 'max_calls': 1, 'calls_attempted': 0,
         'output_reserve': 1024, 'input_plus_output_bound': 16000,
         'query_wall_bound_seconds': 180, 'product_success': 'NOT_MEASURED',
         'max_upstream_attempts': 3, 'conservative_total_token_bound': 48000,
         'learning_benefit': 'NOT_MEASURED', 'deployment': 'NOT_ACTIVATED'}
if ledger.exists():
    if '--resume' not in sys.argv:
        raise SystemExit('REFUSED_EXISTING_REVIEW_ACCOUNTING_NO_REDISPATCH')
    previous = json.loads(ledger.read_bytes())
    assert previous['calls_attempted'] == 0 and previous['max_calls'] == 1 and previous['source_revision'] == REV
    assert 'ended_at' not in previous
    state = previous
    state.setdefault('harness_events', []).append({'at': utc_now(), 'event': 'RESUME_ZERO_CALL_PREFLIGHT_FAILURE',
                                                   'prior_calls_retained': 0})

def save():
    tmp = ledger.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2) + '\n')
    tmp.replace(ledger)

def ref(path):
    return str(path) + '#sha256=' + hashlib.sha256(path.read_bytes()).hexdigest()

save()
def gateway_health():
    base = S._gateway_url().rstrip('/').removesuffix('/v1')
    u = urlsplit(base)
    assert u.scheme == 'http' and u.hostname == '127.0.0.1' and not u.username and not u.query and not u.fragment
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base + '/health', timeout=3) as response:
        return json.loads(response.read(65536))

before = gateway_health()
(O / 'admission-before.json').write_text(json.dumps(before, indent=2) + '\n')
admission = before.get('admission', {})
assert admission.get('max_inflight') == 1 and admission.get('inflight') == admission.get('waiting') == 0
# Inspect only the gateway's retry setting, never retain its environment or credentials.
services = json.loads((Q / 'lrtx/run/services.json').read_bytes())
gateway = services['processes']['gateway']
from forge_factory.lrtx.stack import process_identity
actual = process_identity(gateway['pid'])
assert actual is not None
mapping = [tuple(map(int, line.split())) for line in Path('/proc/self/uid_map').read_text().splitlines()]
host_uid = [outside + actual['uid'] - inside for inside, outside, count in mapping if inside <= actual['uid'] < inside + count]
assert len(host_uid) == 1
normalized = {**actual, 'uid': host_uid[0]}
assert normalized == gateway['identity']
state['gateway_identity_observation'] = {'namespace': actual, 'host_normalized': normalized,
                                          'uid_map_sha256': hashlib.sha256(Path('/proc/self/uid_map').read_bytes()).hexdigest()}
settings = Path('/proc/' + str(gateway['pid']) + '/environ').read_bytes().split(b'\0')
retry_values = [x.split(b'=', 1)[1] for x in settings if x.startswith(b'FORGE_GATEWAY_DROP_RETRIES=')]
del settings
assert process_identity(gateway['pid']) == actual
retries = int(retry_values[0]) if retry_values else 2
assert len(retry_values) <= 1 and 0 <= retries <= 2
state['observed_gateway_retry_limit'] = retries
save()
meter_path = Q / 'lrtx/state/llm-gateway/usage.jsonl'
meter_before = meter_path.stat()
source_path = R / 'factory/python/forge_factory/afo/bus_audit.py'
raw = source_path.read_bytes()
text = raw.decode()
lines = text.splitlines(keepends=True)
selected = ['environment', '_limits', '_query']
sections = []
for node in ast.parse(text).body:
    if isinstance(node, ast.FunctionDef) and node.name in selected:
        sections.append(''.join(lines[node.lineno-1:node.end_lineno]))
assert len(sections) == len(selected)
projection = '\n\n'.join(sections)
source = {'path': 'factory/python/forge_factory/afo/bus_audit.py#complete-query-helpers',
          'sha256': hashlib.sha256(projection.encode()).hexdigest(), 'text': projection}
coverage = {
    'original_source_sha256': hashlib.sha256(raw).hexdigest(), 'selected_complete_functions': selected,
    'obligation': 'bounded fixed read-only query subprocess and constrained reply parsing',
    'caller_contract': 'source() validates scope via environment(), resolves tool from fixed system PATH, and permits only GetId/GetNameOwner',
    'dependencies': {'BUS': 'org.freedesktop.DBus', 'SYSTEMD': 'org.freedesktop.systemd1',
                     'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'UNIQUE': r':[0-9]{1,20}\.[0-9]{1,20}',
                     'stdlib': 'hashlib/math/os/re/selectors/shutil/socket/subprocess/time/pathlib; Refused is a ValueError'},
    'global_boundaries': {'profile_parser': 'out of this review; deterministic tests already exist',
                          'monitor_lifecycle': 'out of this review; deterministic tests already exist',
                          'authenticated_actor_and_continuous_coverage': 'unimplemented; not claimed by the helper',
                          'host_interventions': 'UNKNOWN'},
}
(O / 'input-coverage.json').write_text(json.dumps(coverage, indent=2) + '\n')
coverage_text = json.dumps(coverage, sort_keys=True)
sources = [source, {'path': 'input-coverage.json', 'sha256': hashlib.sha256(coverage_text.encode()).hexdigest(),
                    'text': coverage_text}]
schema = {'type': 'object', 'additionalProperties': False, 'required': ['status', 'findings', 'limits'],
          'properties': {
              'status': {'type': 'string', 'enum': ['FINDINGS', 'NO_SUPPORTED_FINDING', 'INSUFFICIENT_EVIDENCE']},
              'findings': {'type': 'array', 'maxItems': 2, 'items': {'type': 'object', 'additionalProperties': False,
                  'required': ['function', 'source_quote', 'trigger', 'expected', 'deterministic_test'],
                  'properties': {k: {'type': 'string', 'maxLength': 450} for k in
                                 ['function', 'source_quote', 'trigger', 'expected', 'deterministic_test']}}},
              'limits': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string', 'maxLength': 200}}}}
packet = S.packet(phase='EXTERNAL_ENGINEERING_REVIEW', task='BUS-QUERY-HELPERS-fbd8bc8', role='fabric-repair',
                  instructions=('Read-only external implementation-engineer assistance, no repair incident or patch. '
                  'Review only the complete query helper functions and their explicit caller contract. '
                  'Find at most two concrete reproducible faults in subprocess bounds, privacy or native reply parsing. '
                  'Cite an exact function name and literal source quote, with a deterministic trigger/test. '
                  'Do not report documented UNKNOWN actor/continuous coverage or out-of-scope code as a bug. '
                  'No tools, code changes, deployments, policy edits, lessons or correctness claims. '
                  'Empty findings are valid when no concrete fault is supported.'),
                  sources=sources, criteria=['Treat model findings as unverified proposals',
                  'Respect the stated caller preconditions and scope', 'Preserve uncertainty and finite limits'],
                  output_schema=schema, model=state['model'], output_reserve=1024, sampling={'temperature': 0},
                  with_lessons=False)
meta = {k: v for k, v in packet.items() if k != '_messages'}
(O / 'packet.json').write_text(json.dumps(meta, indent=2) + '\n')
measure = packet['accounting']['complete_serialized_request']
state['accounting'] = packet['accounting']
save()
if measure['input_tokens'] + 1024 > min(S.CONTEXT_TOKENS, 16000):
    state.update(ended_at=utc_now(), status='BLOCKED_COMPLETE_CONTEXT', new_model_calls=0)
    save()
    result = None
else:
    state['calls_attempted'] = 1
    save()  # charge before uncertain dispatch; existing accounting always refuses redispatch
    start = time.monotonic()
    result = S.call(packet, timeout=180)
    (O / 'proposal.json').write_text(json.dumps(result, indent=2) + '\n')
    doc = result.get('doc') or {}
    grounded = not result.get('errors') and bool(doc) and all(
        f.get('function') in selected and bool(f.get('source_quote')) and f['source_quote'] in projection
        for f in doc.get('findings', []))
    grounded = grounded and ((doc.get('status') == 'FINDINGS') == bool(doc.get('findings')))
    state.update(ended_at=utc_now(), status='PROPOSAL_ONLY' if grounded else 'INVALID_OR_BLOCKED_PROPOSAL',
                 reference_check='PASS' if grounded else 'FAIL', usage=result.get('usage'),
                 wall_ms=result['wall_ms'], elapsed_seconds=round(time.monotonic()-start, 3),
                 errors=result.get('errors'), correctness='INDEPENDENT_CHECK_REQUIRED')
    save()

after = gateway_health()
(O / 'admission-after.json').write_text(json.dumps(after, indent=2) + '\n')
meter_after = meter_path.stat()
assert (meter_before.st_dev, meter_before.st_ino) == (meter_after.st_dev, meter_after.st_ino)
assert 0 <= meter_after.st_size - meter_before.st_size <= 16 * 1024**2
with meter_path.open('rb') as f:
    f.seek(meter_before.st_size)
    delta = f.read(meter_after.st_size - meter_before.st_size)
assert not delta or delta.endswith(b'\n')
meter_rows = [json.loads(line) for line in delta.splitlines()]
# Native meter emits content-free timing/resource/usage fields; select facts only.
allowed = ['ts_utc', 'model', 'tokens_input', 'tokens_output', 'tokens_cache_hit', 'basis', 'latency_ms', 'attempt',
           'refused', 'upstream_called', 'finish_reason', 'content_chars']
meter_facts = [{k: row[k] for k in allowed if k in row} for row in meter_rows if 'model' in row]
requests = [row for row in meter_facts if 'tokens_input' in row]
assert len(requests) <= retries + 1
observed = {'source': str(meter_path), 'device': meter_after.st_dev, 'inode': meter_after.st_ino,
            'offset': meter_before.st_size, 'length': len(delta), 'sha256': hashlib.sha256(delta).hexdigest(),
            'records': meter_facts, 'upstream_attempts_observed': len(requests),
            'reported_input_tokens': sum(r['tokens_input'] for r in requests) if requests and all(type(r.get('tokens_input')) is int for r in requests) else None,
            'reported_output_tokens': sum(r['tokens_output'] for r in requests) if requests and all(type(r.get('tokens_output')) is int for r in requests) else None,
            'native_liveness': 'UNKNOWN_ON_ANY_CALL_ERROR; no lease or capacity release performed by study'}
(O / 'meter-observation.json').write_text(json.dumps(observed, indent=2) + '\n')

store = LessonStore()
sources = [ref(ledger), ref(O / 'packet.json'), ref(O / 'input-coverage.json')]
if result is not None:
    sources.append(ref(O / 'proposal.json'))
eid = E.capture(store, 'external-study-bus-query-helpers-fbd8bc8-20261027', 'EXTERNAL_ENGINEERING_REVIEW',
                'PARTIAL' if state['status'] == 'PROPOSAL_ONLY' else 'BLOCKED',
                facts={'scope': state['scope'], 'status': state['status'], 'usage': state.get('usage'),
                       'reference_check': state.get('reference_check'), 'correctness': 'UNVERIFIED_PROPOSAL',
                       'client_calls_attempted': state['calls_attempted'], 'upstream_attempts_observed': len(requests)}, source_refs=sources,
                cohort={'study': 'bus-query-helpers-fbd8bc8-20261027', 'evaluation_holdout': True})
E.consolidate(store, limit=32, inference_budget=0)
with store._conn() as c:
    disposition = json.loads(c.execute('SELECT record FROM learning_dispositions WHERE experience_id=?', (eid,)).fetchone()[0])
(O / 'learning-capture.json').write_text(json.dumps({'experience_id': eid, 'disposition': disposition,
    'qualified_lessons_added': 0, 'learning_benefit': 'NOT_MEASURED'}, indent=2) + '\n')
print(json.dumps({k: state.get(k) for k in ('status', 'calls_attempted', 'reference_check', 'usage', 'wall_ms')}), flush=True)
