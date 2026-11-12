"""Prepare or launch one delivery-first native job. No background scheduler."""
from pathlib import Path
import argparse, json, os, secrets, subprocess, sys, time
import httpx

P = Path('/mnt/data/forge-c/production-local-014')
OLD = Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1')
ROOT = Path('/mnt/data/forge-c/delivery-first-014-20261030-v1')
Q = ROOT / 'source'
REV = '2f60aa9a83f8cee8111d5ad837849182ce828474'
PROFILE = 'local-rtx-v2-omniverse2-q38-delivery-first'
parser = argparse.ArgumentParser()
parser.add_argument('--start', action='store_true')
parser.add_argument('--fixture', action='store_true')
args = parser.parse_args()
N = ROOT / 'fixture-only' if args.fixture else ROOT
WO = 'WO-F014-DF-FIXTURE-20261030-01' if args.fixture else 'WO-F014-QWEN-CRC-IDR-DELIVERY-20261030-01'
for key in list(os.environ):
    if key.startswith('FORGE_'):
        os.environ.pop(key)
fab = None
for line in (P / 'state/afo/conductor.env').read_text().splitlines():
    if line.startswith('FORGE_FABRO_BIN='):
        fab = line.split('=', 1)[1]
assert fab and Path(fab).is_file()
os.environ.update(FORGE_REPO_ROOT=str(Q), FORGE_LRTX_ROOT=str(N), FORGE_FABRO_BIN=fab)
sys.path.insert(0, str(Q / 'factory/python'))
from forge_factory import workorder as W
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now, sha256_file, pretty_json
from forge_factory.lrtx import profile, stack
from forge_factory.lrtx.request_measurement import policy as measurement_policy
from forge_factory.workflow.builder import build, binding_for, scale_timeouts
from forge_factory.fabro.runconfig import write_run
from forge_factory.fabro.client import FabroClient, load_token, run_status

assert subprocess.check_output(['git', '-C', str(Q), 'rev-parse', 'HEAD'], text=True).strip() == REV
assert not subprocess.check_output(['git', '-C', str(Q), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()
prof = profile.load(PROFILE)
assert prof['work_order_purpose'] == 'QM' and not any(prof['structured']['phases_by_layer'].values())
for name in ('state', 'archives', 'fabro/storage', 'fabro/home/.fabro', 'logs', 'run', 'home', 'cache/uv',
             'cache/pip', 'cache/xdg'):
    (N / name).mkdir(mode=0o700, parents=True, exist_ok=True)
for name, target in prof['deployment']['shared_readonly'].items():
    link = N / name
    if not link.exists():
        link.symlink_to(target)
    if link.is_symlink():
        assert link.resolve() == Path(target).resolve()
if not (N / 'venv').exists():
    (N / 'venv').symlink_to(P / 'venv')
ports = dict(prof['deployment']['ports'])
if args.fixture:
    ports.update(gateway=11460, fabro=32403)
settings = {'profile': prof, 'root': N, 'ports': ports}
env = stack.envmap(settings)
env.update(FORGE_DURABLE_AUTONOMY='0', FORGE_DURABLE_NATIVE_HEADER='0', PYTHONDONTWRITEBYTECODE='1',
           FORGE_GATEWAY_REASONING=stack.gateway_reasoning(prof),
           FORGE_GATEWAY_REQUEST_TIMEOUT_S=str(stack.gateway_timeout(prof)),
           FORGE_GATEWAY_DROP_RETRIES='0',
           FORGE_GATEWAY_MEASURE_UNBOUND='1',
           FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT=str(prof['runtime']['context_limit_tokens']),
           FORGE_GATEWAY_ROUTES=json.dumps({prof['models']['default']: 'http://127.0.0.1:11461' if args.fixture
                                           else 'http://127.0.0.1:11457'}),
           FORGE_GATEWAY_REQUEST_MEASUREMENT=json.dumps(measurement_policy(prof)))
for key in ('FORGE_GATEWAY_MAX_INFLIGHT', 'FORGE_OPERATIONS_INTENT', 'FORGE_AFO_POLICY',
            'FORGE_AFO_AUTH_DIR', 'FORGE_AFO_ALLOWED_SIGNERS'):
    env.pop(key, None)
os.environ.update(env)
(N / 'fabro/settings.toml').write_text(stack.fabro_config(settings))
base_url = 'http://127.0.0.1:' + str(ports['fabro'])
(N / 'fabro/home/.fabro/settings.toml').write_text('_version = 1\n[cli.target]\ntype = "http"\nurl = "' +
                                                base_url + '/api/v1"\n')
secretfile = N / 'fabro/storage/server.env'
if not secretfile.exists():
    secretfile.write_text('SESSION_SECRET=' + secrets.token_hex(32) + '\nFABRO_DEV_TOKEN=fabro_dev_' +
                          secrets.token_hex(32) + '\n')
    secretfile.chmod(0o600)
serverenv = {**env, 'HOME': str(N / 'fabro/home')}
for line in secretfile.read_text().splitlines():
    if '=' in line:
        key, value = line.split('=', 1)
        serverenv[key] = value
authfile = N / 'fabro/home/.fabro/auth.json'
authfile.write_text(json.dumps({'servers': {base_url: {'kind': 'dev-token', 'token': serverenv['FABRO_DEV_TOKEN'],
                                                     'logged_in_at': utc_now()}}}))
authfile.chmod(0o600)
prepared = N / 'prepared.json'
ws = N / 'state/workorders' / WO / 'workspace'
if not prepared.exists():
    intent = N / 'prepare-intent.json'
    assert not intent.exists() and not ws.exists(), 'PRIOR_PREPARATION_REQUIRES_RECONCILIATION'
    immutable_json(intent, {'at': utc_now(), 'revision': REV, 'work_order': WO, 'fixture': args.fixture})
    ws, manifest = W.prepare(Q / 'examples/0014g-st-crc-idr-qwen-delivery', WO, purpose='QM',
                             execution_policy='qm-pipeline-demonstration-v1')
    manifest['local_profile'] = {'id': PROFILE, 'version': prof['version'], 'config': prof['_path'],
                                'config_sha256': prof['_sha256'], 'status': prof['status']}
    manifest['native_artifact_trial'] = {'standalone': True, 'AFO_intake': False, 'no_production_acceptance': True,
        'inference_mode': 'FIXTURE_ONLY_NO_QWEN_GENERATION' if args.fixture else 'REAL_LOCAL_QWEN',
        'owner_scope': 'RELAXED_DEVELOPMENT_ARTIFACTS; preserve deterministic verification and historical outcomes'}
    (ws / '.forge-run/manifest.json').write_text(pretty_json(manifest))
    structured = W.local_profile_structured(prof, manifest, prof['models']['default'])
    graph, nodes = build(WO, goal='New Qwen C candidate with truthful six-phase development evidence',
                        sections=W.section_map(ws), layer='LL', trace=True, chunk_lines=150, peripheral='crc',
                        operation_scope=manifest['operation_scope'], execution_policy=manifest['development_execution'],
                        assessment_manifest=manifest, structured=structured)
    graph = scale_timeouts(graph, prof['runtime']['timeout_scale'])
    assert 'forge_factory.lrtx.runner' not in graph
    (ws / '.forge-run/model-profile.json').write_text(pretty_json(W.model_profile(prof['models']['default'],
                                                                                'ollama', None, nodes)))
    roles = sorted({v['role'] for v in nodes.values()})
    agents, mcps = W.agent_preflight(roles), W.mcp_preflight(roles, live=True)
    assert agents['status'] == mcps['status'] == 'PASS', (agents['issues'], mcps['issues'])
    write_run(ws, graph, 'FIXTURE_ONLY' if args.fixture else 'Local Qwen authored CRC development trial',
              binding_for(WO, str(ws), nodes), W.fabro_mcp_config(mcps['servers']),
              model=prof['models']['default'], provider='ollama')
    immutable_json(prepared, {'at': utc_now(), 'source_revision': REV, 'profile': PROFILE,
        'profile_sha256': prof['_sha256'], 'work_order': WO, 'workspace': str(ws), 'ports': ports,
        'inference_mode': manifest['native_artifact_trial']['inference_mode'], 'candidate_seeded': False,
        'quality': 'DEMONSTRATION_ONLY_NOT_QUALIFIED', 'agents_preflight': agents['status'],
        'mcp_preflight': mcps['status'], 'workflow_sha256': sha256_file(ws / '.forge-run/workflow.fabro')})
else:
    old = json.loads(prepared.read_text())
    assert old['source_revision'] == REV and old['workspace'] == str(ws)

def healthy(url):
    try:
        return httpx.get(url, timeout=2).status_code == 200
    except httpx.HTTPError:
        return False

services = N / 'run/services.json'
records = json.loads(services.read_text()) if services.exists() else {}

def start(name, argv, penv, url):
    if name in records and healthy(url):
        return
    assert not healthy(url), 'UNEXPECTED_SERVICE:' + name
    log = (N / 'logs' / (name + '.log')).open('ab', buffering=0)
    child = subprocess.Popen(argv, env=penv, cwd=N, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    records[name] = {'pid': child.pid, 'argv': argv, 'health': url, 'started_at': utc_now(), 'source_revision': REV}
    services.write_text(json.dumps(records, indent=2) + '\n')
    services.chmod(0o600)
    for _ in range(45):
        if healthy(url):
            return
        assert child.poll() is None, 'SERVICE_EXITED:' + name
        time.sleep(1)
    raise RuntimeError('SERVICE_START_STILL_PENDING:' + name)

if args.fixture:
    start('fixture_backend', [str(P / 'venv/bin/python'), str(ROOT / 'fixture-backend.py')], env,
          'http://127.0.0.1:11461/health')
start('gateway', [str(P / 'venv/bin/python'), '-m', 'forge_factory.llm_gateway', '--port', str(ports['gateway']),
                  '--upstream', 'http://127.0.0.1:11457', '--meter', str(N / 'state/llm-gateway/usage.jsonl')],
      env, 'http://127.0.0.1:' + str(ports['gateway']) + '/health')
start('fabro', [fab, 'server', 'start', '--foreground', '--no-web', '--no-upgrade-check', '--config',
                str(N / 'fabro/settings.toml'), '--storage-dir', str(N / 'fabro/storage')],
      serverenv, base_url + '/health')
if not args.start:
    print(json.dumps({'status': 'PREPARED_NO_GENERATION', 'source_revision': REV, 'work_order': WO,
                      'fixture': args.fixture, 'root': str(N)}))
    raise SystemExit(0)
launchfile, launchintent = N / 'launch.json', N / 'launch-intent.json'
if launchfile.exists():
    print(launchfile.read_text())
    raise SystemExit(0)
assert not launchintent.exists(), 'UNCERTAIN_LAUNCH_DO_NOT_RETRY'
operator = json.loads(Path('/home/omniverse2/.local/state/forge-c-production-014/operations.json').read_text())
assert operator['mode'] == 'PAUSED' and operator['epoch'] == 111, 'NEWER_OPERATOR_INTENT'
if not args.fixture:
    old_launch = json.loads((OLD / 'launch.json').read_text())
    with FabroClient(base_url='http://127.0.0.1:32401', token=load_token(str(OLD / 'fabro/storage'))) as client:
        prior_status = run_status(client.get_run(old_launch['native_id']))
        assert prior_status in ('SUCCEEDED', 'FAILED', 'CANCELLED', 'CANCELED'), 'OLD_NATIVE_STILL_LIVE'
    slots = httpx.get('http://127.0.0.1:11457/slots', timeout=10).json()
    assert len(slots) == 1 and not slots[0]['is_processing'], 'NATIVE_INFERENCE_STILL_LIVE'
    assert not (ws / 'software/ll/stm32n6xx_ll_crc.h').exists(), 'CANDIDATE_PRESEEDED'
immutable_json(launchintent, {'at': utc_now(), 'work_order': WO, 'fixture': args.fixture,
                              'operator_epoch': operator['epoch'], 'source_revision': REV})
rid = W.launch_run(ws, WO, ws / '.forge-run/workflow.toml', fab,
                   {'trial': 'delivery-first-014', 'inference': 'FIXTURE_ONLY' if args.fixture else 'LOCAL_QWEN'})
(ws / '.forge-run/fabro_server.json').write_text(json.dumps({'url': env['FORGE_FABRO_URL'],
                                                           'storage': env['FORGE_FABRO_STORAGE']}))
record = {'at': utc_now(), 'source_revision': REV, 'work_order': WO, 'native_id': rid,
          'workspace': str(ws), 'root': str(N), 'ports': ports,
          'inference_mode': 'FIXTURE_ONLY_NO_QWEN_GENERATION' if args.fixture else 'REAL_LOCAL_QWEN',
          'candidate_seeded': False, 'AFO_intake': False, 'production_qualification': 'NOT_PROVEN',
          'authorship': 'NATIVE_WRITE_EVENTS_REQUIRED', 'functional_milestone': 'NOT_PROVEN'}
immutable_json(launchfile, record)
print(json.dumps(record))

