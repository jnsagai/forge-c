#!/usr/bin/env python3
"""Own-server, deterministic-stub transport measurement. No production API/model access."""
import argparse
import hashlib
import json
import os
import secrets
import signal
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, type=Path)
    ap.add_argument('--binary', required=True, type=Path)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--profile', default='local-rtx-v2-omniverse2-ornith-think-author-q38-inspector')
    args = ap.parse_args()
    import sys
    sys.path.insert(0, str(args.source / 'factory/python'))
    from forge_factory.lrtx.profile import load
    from forge_factory.lrtx.stack import fabro_config
    from forge_factory.fabro.client import FabroClient, run_status
    from forge_factory.common import utc_now
    from forge_factory.fabro.runconfig import create_workspace

    root = args.root.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    rows = []
    class Stub(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"object":"list","data":[]}')
        def do_POST(self):
            length = int(self.headers.get('Content-Length', '0'))
            if length > 1024 * 1024 or len(rows) >= 4:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(length))
            rows.append({'path': self.path, 'x_session_id': self.headers.get('x-session-id'),
                         'model': body.get('model'), 'stream': body.get('stream'),
                         'max_tokens': body.get('max_tokens'),
                         'max_completion_tokens': body.get('max_completion_tokens'),
                         'temperature': body.get('temperature'), 'top_p': body.get('top_p'),
                         'seed': body.get('seed'),
                         'tools_present': isinstance(body.get('tools'), list) and bool(body['tools']),
                         'tool_count': len(body['tools']) if isinstance(body.get('tools'), list) else 0,
                         'response_format_type': (body.get('response_format') or {}).get('type')})
            data = {'id': 'transport-fixture', 'object': 'chat.completion', 'created': int(time.time()),
                    'model': body.get('model'),
                    'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'TRANSPORT_FIXTURE_ONLY'},
                                 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
            self.send_response(200)
            if body.get('stream'):
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                for delta, reason in [({'role': 'assistant', 'content': 'TRANSPORT_FIXTURE_ONLY'}, None), ({}, 'stop')]:
                    chunk = {'id': 'transport-fixture', 'object': 'chat.completion.chunk',
                             'created': int(time.time()), 'model': body.get('model'),
                             'choices': [{'index': 0, 'delta': delta, 'finish_reason': reason}]}
                    self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
            else:
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
    stub = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    prof = load(args.profile)
    for rel in ('fabro/storage/objects', 'fabro/home/.fabro', 'home'):
        (root / rel).mkdir(parents=True)
    settings = root / 'fabro/settings.toml'
    settings.write_text(fabro_config({'root': root, 'ports': {'fabro': port, 'gateway': stub.server_port}, 'profile': prof}))
    token = 'fabro_dev_' + secrets.token_hex(32)
    envpath = root / 'fabro/storage/server.env'
    envpath.write_text('SESSION_SECRET=' + secrets.token_hex(32) + '\nFABRO_DEV_TOKEN=' + token + '\n')
    envpath.chmod(0o600)
    auth = root / 'fabro/home/.fabro/auth.json'
    auth.write_text(json.dumps({'servers': {f'http://127.0.0.1:{port}': {'kind': 'dev-token', 'token': token, 'logged_in_at': utc_now()}}}))
    auth.chmod(0o600)
    task_env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(root / 'fabro/home'), 'LANG': 'C.UTF-8',
                'FABRO_NO_UPGRADE_CHECK': '1', 'GIT_SSH_COMMAND': '/usr/bin/false',
                'SESSION_SECRET': next(x.split('=', 1)[1] for x in envpath.read_text().splitlines() if x.startswith('SESSION_SECRET=')),
                'FABRO_DEV_TOKEN': token}
    workspace = root / 'workspace'
    create_workspace(workspace, {'README.md': 'Deterministic HTTP transport fixture. No real model.\n'}, include_default_skills=False)
    models = list(prof['models']['allowed'])
    graph = workspace / 'workflow.fabro'
    graph.write_text('digraph transport {\n graph [goal="Transport fixture only", max_visits="1"]\n start [shape=Mdiamond]\n exit [shape=Msquare]\n'
                     + '\n'.join(f' probe{i} [prompt="Return TRANSPORT_FIXTURE_ONLY", model="{m}", timeout="15s", max_visits=1]' for i, m in enumerate(models))
                     + '\n start -> ' + ' -> '.join(f'probe{i}' for i in range(len(models))) + ' -> exit\n}\n')
    toml = workspace / 'workflow.toml'
    toml.write_text('_version = 1\n[workflow]\ngraph = "workflow.fabro"\n[run]\ngoal = "Transport fixture only"\n[run.model]\nname = ' + json.dumps(prof['models']['default']) + '\nprovider = "ollama"\n[run.environment]\nid = "local"\n')
    report = {'schema': 'forge-c/native-header-transport-measurement/1', 'scope': 'TRANSPORT_ONLY_DETERMINISTIC_STUB_NO_ROLE_QUALIFICATION',
              'started_at': utc_now(), 'binary_sha256': sha(args.binary), 'profile_sha256': prof['_sha256'],
              'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.source, text=True).strip(),
              'settings_sha256': sha(settings), 'graph_sha256': sha(graph), 'requests': rows, 'production_mutations': False}
    report['profile'] = prof['id']
    report['source_tracked_dirty'] = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=args.source, text=True).strip())
    report['harness_sha256'] = sha(__file__)
    adapters = ('llm_gateway.py', 'afo/product_job.py', 'afo/execution_lifecycle.py', 'fabro/client.py', 'lrtx/stack.py')
    report['adapter_sha256'] = {p: sha(args.source / 'factory/python/forge_factory' / p) for p in adapters}
    report['binary_version'] = subprocess.check_output([str(args.binary), '--version'], env=task_env, text=True, timeout=10).strip()
    log = (root / 'fixture-server.log').open('wb')
    proc = subprocess.Popen([str(args.binary), 'server', 'start', '--foreground', '--no-web', '--config', str(settings),
                             '--storage-dir', str(root / 'fabro/storage'), '--no-upgrade-check', '--bind', f'127.0.0.1:{port}', '--max-concurrent-runs', '1'],
                            env=task_env, cwd=workspace, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    client = FabroClient(f'http://127.0.0.1:{port}', token=token, timeout=2)
    rid = None
    terminal = False
    try:
        for _ in range(100):
            try:
                if client.health():
                    break
            except Exception:
                pass
            if proc.poll() is not None:
                raise RuntimeError('FIXTURE_SERVER_EXITED')
            time.sleep(.1)
        nonce = secrets.token_hex(16)
        out = subprocess.run([str(args.binary), 'run', str(toml), '--detach', '--server', f'http://127.0.0.1:{port}/api/v1',
                              '--no-upgrade-check', '--environment', 'local', '--label', 'afo_agent=transport-fixture', '--label', 'afo_nonce=' + nonce],
                             env=task_env, cwd=workspace, capture_output=True, text=True, timeout=25)
        report['launch_returncode'] = out.returncode
        if out.returncode:
            report['launch_error'] = out.stderr[-1200:]
            raise RuntimeError('FIXTURE_LAUNCH_REFUSED')
        rid = out.stdout.strip().splitlines()[-1]
        report['native_run_id'] = rid
        for _ in range(200):
            native = client.get_run(rid)
            if run_status(native) in ('SUCCEEDED', 'FAILED', 'CANCELLED', 'CANCELED'):
                terminal = True
                break
            time.sleep(.2)
        report['terminal_status'] = run_status(native)
        report['labels_match'] = (native.get('labels') or {}).get('afo_agent') == 'transport-fixture' and (native.get('labels') or {}).get('afo_nonce') == nonce
        report['all_headers_equal_actual_run_id'] = bool(rows) and all(r['x_session_id'] == rid for r in rows)
        report['request_count'] = len(rows)
        from forge_factory.afo.queue import Store
        from forge_factory.afo.mission_ledger import MissionLedger
        from forge_factory.afo.execution_lifecycle import Executions
        from forge_factory.afo.product_job import from_native
        from forge_factory.afo.durable import Refused
        controls = {}
        for name, header, expected_nonce, expected_job, accepted in [
            ('actual_header_and_nonce', rows[0]['x_session_id'] if rows else None, nonce, 'transport-fixture', True),
            ('missing_header', None, nonce, 'transport-fixture', False),
            ('unknown_header', '01M00000000000000000000000', nonce, 'transport-fixture', False),
            ('foreign_nonce', rid, '0' * 32, 'transport-fixture', False),
            ('foreign_job', rid, nonce, 'different-fixture-job', False),
        ]:
            store = Store(root / ('identity-' + name + '.sqlite3'))
            ledger = MissionLedger(store)
            limits = {k: 4 for k in ('max_attempts', 'max_jobs', 'max_requests', 'max_tools', 'max_corrections')}
            limits.update(max_tokens=100, deadline=time.time() + 30)
            ledger.register('transport-fixture-mission', 'transport-fixture-lineage', limits, 'fixture-only-not-production-authority', authorize=lambda *_: True)
            ledger.execution('transport-fixture-mission', expected_job, 'PRODUCT', reserved_tokens=10)
            ex = Executions(store)
            ex.reserve(expected_job, 'transport-fixture-mission', expected_nonce)
            ex.dispatch_intent(expected_job)
            try:
                result = from_native(store, header, client=client)
                observed = result == {'job_id': expected_job, 'nonce': expected_nonce}
                reason = 'CONFIRMED' if observed else 'UNEXPECTED_BINDING'
            except Refused as exc:
                observed = False
                reason = str(exc)
            except Exception as exc:
                observed = False
                reason = type(exc).__name__ + ':' + str(getattr(getattr(exc, 'response', None), 'status_code', 'UNKNOWN'))
            controls[name] = {'pass': observed == accepted, 'accepted': observed, 'reason': reason}
        report['identity_controls'] = controls
        report['verdict'] = 'PASS' if terminal and report['terminal_status'] == 'SUCCEEDED' and report['labels_match'] and len(rows) == len(models) and report['all_headers_equal_actual_run_id'] and all(x['pass'] for x in controls.values()) else 'REFUSED_TRANSPORT_NOT_PROVEN'
    except Exception as exc:
        report['error'] = type(exc).__name__ + ':' + str(exc)
        report['verdict'] = 'REFUSED_TRANSPORT_NOT_PROVEN'
    finally:
        if rid and not terminal:
            try:
                client.cancel(rid)
                for _ in range(50):
                    if run_status(client.get_run(rid)) in ('SUCCEEDED', 'FAILED', 'CANCELLED', 'CANCELED'):
                        terminal = True
                        break
                    time.sleep(.1)
            except Exception:
                pass
        safe = terminal or rid is None
        report['fixture_terminal_confirmed'] = terminal
        if safe and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
        report['own_server_stopped'] = proc.poll() is not None
        report['finished_at'] = utc_now()
        client.close()
        stub.shutdown()
        log.close()
        (root / 'measurement.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
