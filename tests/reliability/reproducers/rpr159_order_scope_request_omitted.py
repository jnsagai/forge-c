"""Real isolated TEST-key signatures and actual local/cloud request builders.

No owner key/grant, model request, launcher, state database or production action.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import pwd
import sys
from types import SimpleNamespace
from unittest.mock import patch

import yaml


ALLOWED = 'WO-F014-SWE6-AFOQUAL-20261104-L90'
UNLISTED = 'WO-F014-SWE6-AFOQUAL-20261104-L90B'


class NextValidationReached(Exception):
    pass


def adoption_checks(folder, profile, policy, grant, now):
    from forge_factory.afo import line_campaign as LC, line_orders as LO
    from forge_factory.afo.queue import Store

    repo = folder / 'approved-adoption-campaign'
    repo.mkdir()
    document = {'schema': LC.SCHEMA_ID, 'campaign_id': 'CMP-SIGNED-SCOPE-ADOPTION', 'line': 'local',
                'wo_prefix': 'WO-F014', 'lineages': [{'id': 'scope-crc', 'example': '0014m-crc-hal',
                 'tag': 'AFOQUAL', 'series': '20261104-L90', 'driver_class': 'STM32N6_CRC_HAL',
                 'factory_revision': 'a' * 40, 'profile': profile,
                 'run_model': 'hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0', 'purpose': 'ASPICE_ONLY',
                 'phases': ['SWE.6']}]}
    campaign_path = repo / 'campaign.yaml'
    campaign_path.write_text(yaml.safe_dump(document, sort_keys=False))
    for command in [('init', '-q'), ('add', '.'), ('commit', '-qm', 'Explicit isolated approved campaign fixture')]:
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=isolated-test',
                        '-c', 'user.email=isolated@example.invalid', '-c', 'commit.gpgsign=false',
                        '-c', 'core.hooksPath=/dev/null', *command], check=True, capture_output=True)
    campaign = LC.parse(campaign_path, require_approval=True)
    results = {}
    for wo in (ALLOWED, UNLISTED):
        state = folder / ('adoption-' + wo) / 'state'
        with patch.dict(os.environ, {'FORGE_STATE_DIR': str(state)}):
            placer = LO.Placer(SimpleNamespace(), unit='isolated-test-adoption')
            store = Store(placer.queue_path)
            plan = SimpleNamespace(lineage=campaign.lineages[0])
            att = LO.Att(wo, 'SWE.6', 1 if wo == ALLOWED else 2, created=now,
                         rec={'revision': 'a' * 40}, rid='isolated-native-fixture-' + wo, status='RUNNING')
            try:
                placer._sync(store, plan, att, None, policy, grant, [campaign], now)
                outcome = 'RETURNED'
            except Exception as exc:
                outcome = getattr(exc, 'code', type(exc).__name__)
            row = LO._queue_rows(placer.queue_path).get(wo)
            results[wo] = {'admitted': bool(row and row['state'] == 'RUNNING'), 'outcome': outcome,
                           'spec_created': (LO.supervisor_dir() / 'line-orders' / (wo + '.json')).exists()}
    if not results[ALLOWED]['admitted']:
        raise RuntimeError('SIGNED_LISTED_ADOPTION_CONTROL_REFUSED:' + repr(results))
    return results


def scenario(root):
    from forge_factory.common import REPO_ROOT
    from forge_factory.afo import authz, line_campaign, line_orders as LO, line_cloud as C

    key = root / 'isolated-TEST-key'
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True, capture_output=True)
    signers = root / 'allowed-test-signers'
    signers.write_text('isolated-test-reviewer ' + key.with_suffix('.pub').read_text())
    reports = {}
    for line in ('local', 'cloud'):
        folder = root / line
        folder.mkdir()
        profile = C.PROFILE if line == 'cloud' else 'local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104'
        policy = yaml.safe_load((REPO_ROOT / 'config/factory/line-policy.yaml').read_text())
        policy['line'] = line
        policy['authorization_ref'] = 'TEST-ORDER-SCOPE-' + line.upper()
        if line == 'cloud':
            policy['pacing']['max_concurrent_cloud_runs'] = 2
            policy['models'] = C.PROFILE
        path = folder / 'line-policy.yaml'
        path.write_text(yaml.safe_dump(policy, sort_keys=False))
        loaded = LO.load_policy(path)
        if loaded.issues:
            raise RuntimeError('FIXTURE_POLICY_INVALID:' + repr(loaded.issues))
        now = time.time()
        from datetime import datetime, timezone
        grant = {'schema_version': '1.0', 'authorization_id': policy['authorization_ref'],
                 'approver': 'isolated-test-reviewer', 'approval_evidence_ref': 'ISOLATED_TEST_KEY_ONLY_NOT_OWNER_AUTHORITY',
                 'issued_utc': datetime.fromtimestamp(now - 30, timezone.utc).isoformat(),
                 'expires_utc': datetime.fromtimestamp(now + 300, timezone.utc).isoformat(),
                 'policy_sha256': loaded.sha256, 'mode': 'PILOT',
                 'allowed_actions': ['submit_workorder', 'launch_workorder', 'recover_workorder'],
                 'scope': {'order_ids': [ALLOWED], 'driver_classes': ['STM32N6_CRC_HAL'], 'models': [profile],
                           'service_actions': ['line_stack_restart', 'line_orphan_sweep', 'line_run_worktree_cleanup']},
                 'signature_ref': policy['authorization_ref'] + '.sig', 'revoked_utc': None}
        gp = folder / (policy['authorization_ref'] + '.json')
        gp.write_text(json.dumps(grant))
        authz.sign(gp, key)  # freshly generated TEST key only; never an owner signature
        verified = LO.verify_grant(loaded, now=now, base=folder, allowed_signers=signers)
        if not verified.allow:
            raise RuntimeError('REAL_TEST_SIGNATURE_NOT_VERIFIED:' + verified.code)
        primitive = verified.permit('launch_workorder', {'order_id': UNLISTED, 'driver_class': 'STM32N6_CRC_HAL', 'model': profile})
        if primitive.allow or primitive.code != 'AUTH_OUT_OF_SCOPE':
            raise RuntimeError('PRIMITIVE_SCOPE_NEGATIVE_CONTROL_FAILED')
        builder = C.CloudPlacer._requests if line == 'cloud' else LO.Placer._requests
        values = {}
        for wo in (ALLOWED, UNLISTED):
            plan = SimpleNamespace(order={'wo': wo, 'kind': next(iter(LO.RETRY_KINDS))}, action='PLACE', sweep=True,
                                   lineage=SimpleNamespace(driver_class='STM32N6_CRC_HAL', profile=profile))
            requests = builder(None, plan)
            values[wo] = [{'action': action, 'request': request, 'allow': verified.permit(action, request).allow}
                          for action, request in requests]
        if not all(value['allow'] for value in values[ALLOWED]):
            raise RuntimeError('LISTED_ORDER_POSITIVE_CONTROL_REFUSED')
        result = {'real_TEST_signature': verified.code, 'primitive_unlisted_refusal': primitive.code,
                  'listed_all_allowed': True, 'unlisted_any_allowed': any(r['allow'] for r in values[UNLISTED]),
                  'requests': values}
        if line == 'local':
            workspaces, worktrees = {}, {}
            rows = {}
            for wo in (ALLOWED, UNLISTED):
                workspace = folder / 'workspaces' / wo
                package = workspace / '.forge-run/package.json'
                package.parent.mkdir(parents=True)
                package.write_text('{}')
                os.utime(package, (now - 4 * 86400, now - 4 * 86400))
                worktree = folder / 'runs' / wo
                worktree.mkdir(parents=True)
                workspaces[wo], worktrees[wo] = workspace, worktree
                rows[wo] = {'state': 'BLOCKED', 'envelope': {'driver_class': 'STM32N6_CRC_HAL', 'model_profile': profile}}
            placer = object.__new__(LO.Placer)
            placer.line = SimpleNamespace(workspace=lambda wo: workspaces[wo], run_worktree=lambda wo: worktrees[wo], pytest_roots=[])
            placer.queue_path = folder / 'unused-no-database'
            with patch.object(LO, '_queue_rows', lambda *_: rows):
                cleanup = placer._cleanup(loaded, verified, now, execute=False)
            planned = [row['wo'] for row in cleanup]
            if ALLOWED not in planned:
                raise RuntimeError('LISTED_ORDER_CLEANUP_CONTROL_REFUSED')
            result['unlisted_cleanup_allowed'] = UNLISTED in planned
            result['live_adoption'] = adoption_checks(folder, profile, loaded, verified, now)
        if line == 'cloud':
            def next_validation(*args, **kwargs):
                raise NextValidationReached()
            child_results = {}
            with ExitStack() as patches:
                patches.enter_context(patch.dict(os.environ, {'FORGE_STATE_DIR': str(folder / 'state'), 'FORGE_LINE_POLICY': str(path)}))
                patches.enter_context(patch.object(authz, 'AUTH_DIR', folder))
                patches.enter_context(patch.object(authz, 'ALLOWED_SIGNERS', signers))
                patches.enter_context(patch.object(line_campaign, 'load_all', next_validation))
                for wo in (ALLOWED, UNLISTED):
                    spec = {'wo': wo, 'driver_class': 'STM32N6_CRC_HAL', 'profile': profile}
                    spec['digest'] = LO._digest(spec)
                    sp = LO.supervisor_dir() / 'line-orders' / (wo + '.json')
                    sp.parent.mkdir(parents=True, exist_ok=True)
                    sp.write_text(json.dumps(spec))
                    try:
                        C._authorized_spec(sp, SimpleNamespace())
                        raise RuntimeError('CHILD_VALIDATION_CONTROL_NOT_REACHED')
                    except NextValidationReached:
                        child_results[wo] = 'AUTHORIZATION_STAGE_ACCEPTED'
                    except ValueError as exc:
                        child_results[wo] = str(exc)
            if child_results[ALLOWED] != 'AUTHORIZATION_STAGE_ACCEPTED':
                raise RuntimeError('CLOUD_CHILD_LISTED_CONTROL_REFUSED')
            result['child_authorization_stage'] = child_results
            result['unlisted_child_allowed'] = child_results[UNLISTED] == 'AUTHORIZATION_STAGE_ACCEPTED'
        reports[line] = result
    return reports


def test_real_signed_scope_is_enforced_by_local_cloud_and_child(tmp_path):
    reports = scenario(tmp_path)
    assert all(not value['unlisted_any_allowed'] for value in reports.values()), reports
    assert reports['local']['unlisted_cleanup_allowed'] is False, reports
    assert reports['local']['live_adoption'][UNLISTED]['admitted'] is False, reports
    assert reports['local']['live_adoption'][UNLISTED]['spec_created'] is False, reports
    assert reports['cloud']['unlisted_child_allowed'] is False, reports


def main():
    try:
        pwd.getpwuid(os.getuid())
    except KeyError:
        # CRE's verifier UID intentionally has no host login. OpenSSH refuses
        # even explicit TEST-key operations without NSS. Supply only a private
        # read-only passwd fixture in another scoped kernel namespace; never
        # modify host /etc, role UID, owner keys or authorization verification.
        from forge_factory.common import REPO_ROOT, data_root
        from forge_factory.reliability import isolation
        with tempfile.TemporaryDirectory(prefix='rpr159-private-nss-') as temporary:
            root = Path(temporary)
            passwd = root / 'passwd'
            passwd.write_text(Path('/etc/passwd').read_text() +
                              f'isolated-test-verifier:x:{os.getuid()}:{os.getgid()}:isolated TEST fixture:/tmp:/bin/sh\n')
            env = {'PATH': '/usr/bin:/bin', 'FORGE_REPO_ROOT': str(REPO_ROOT),
                   'FORGE_DATA_ROOT': str(data_root()), 'PYTHONPATH': str(REPO_ROOT / 'factory/python')}
            args = isolation.bubblewrap_argv('verifier', [sys.executable, str(Path(__file__).resolve()), '--private-nss-fixture'],
                                              cwd=REPO_ROOT, env=env, writable=[root], readable=[Path(__file__).resolve()])
            at = args.index('--chdir')
            args[at:at] = ['--ro-bind', str(passwd), '/etc/passwd']
            ran = subprocess.run(args, capture_output=True, text=True, timeout=30)
            sys.stdout.write(ran.stdout)
            if ran.returncode == 2 or not ran.stdout:
                print('REPRODUCER_ERROR:PRIVATE_NSS_FIXTURE:' + ran.stderr[-300:])
                return 2
            return ran.returncode
    with tempfile.TemporaryDirectory(prefix='rpr159-real-test-signature-') as temporary:
        reports = scenario(Path(temporary))
        print(json.dumps({'scope': 'ISOLATED_TEST_KEYS_AUTHORIZATION_STAGE_ONLY', 'model_calls': 0, 'reports': reports}))
        if (any(value['unlisted_any_allowed'] for value in reports.values()) or reports['cloud']['unlisted_child_allowed']
                or reports['local']['unlisted_cleanup_allowed']):
            print('SYMPTOM_PRESENT:order-scoped line grants authorize unlisted work orders')
            return 1
        if (reports['local']['live_adoption'][UNLISTED]['admitted']
                or reports['local']['live_adoption'][UNLISTED]['spec_created']):
            print('SYMPTOM_PRESENT:order-scoped line grants authorize unlisted work orders')
            return 1
    print('SYMPTOM_ABSENT')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('REPRODUCER_ERROR:' + type(exc).__name__ + ':' + str(exc)[:400])
        raise SystemExit(2)
