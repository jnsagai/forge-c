"""Frozen external staged real-kernel namespace entry oracle, no candidate tests."""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SIG='provider entry rejects inherited ancestor network or already-current user namespace'
HELPER_SHA='1a12b0b8761511ea219a9dd69c26dbf0bd6cb5d633982a2de6d868cda7082762'


def main():
    from forge_factory.common import REPO_ROOT
    helper=Path(__file__).with_name('kernel_probe.py')
    assert hashlib.sha256(helper.read_bytes()).hexdigest()==HELPER_SHA,'FROZEN_KERNEL_HELPER_CHANGED'
    with tempfile.TemporaryDirectory(prefix='staged-nsentry-') as temp:
        out=Path(temp)/'probe'
        proc=subprocess.run([sys.executable,str(helper),'--source',str(REPO_ROOT),'--output',str(out)],capture_output=True,text=True,timeout=90)
        if not (out/'report.json').is_file():
            print('CHILD_DIAGNOSTIC:'+json.dumps(dict(returncode=proc.returncode,stderr=proc.stderr[-3000:],stdout=proc.stdout[-1000:]),sort_keys=True));print('REPRODUCER_ERROR:KERNEL_REPORT_MISSING');return 2
        report=json.loads((out/'report.json').read_text())
        if report['verdict']=='PROBE_ERROR' or not report.get('own_process_handles_closed') or any(not x.get('quiet') for x in report.get('cleanup',[])):
            print('REPRODUCER_ERROR:'+str(report.get('error_type','KERNEL_PROOF_OR_CLEANUP_UNKNOWN')));return 2
        rows={r['name']:r for r in report['results']}
        expected=['ordered-nested-control','ordered-same-user-skip-control','ordered-same-user-reentry-negative','source-nested-provider','source-same-user-provider','source-normal-outer','source-normal-same-current-user']
        if set(rows)!=set(expected):
            print('REPRODUCER_ERROR:INCOMPLETE_CASES');return 2
        assert rows['ordered-nested-control']['returncode']==rows['ordered-same-user-skip-control']['returncode']==0
        assert rows['ordered-same-user-reentry-negative']['returncode']!=0 and rows['ordered-same-user-reentry-negative']['errno_hint']=='EINVAL'
        assert rows['source-same-user-provider']['returncode']==rows['source-normal-outer']['returncode']==0
        failures=[rows[n] for n in ['source-nested-provider','source-normal-same-current-user'] if rows[n]['returncode']!=0]
        if any(r['errno_hint']!=('EPERM' if r['name']=='source-nested-provider' else 'EINVAL') for r in failures):
            print('REPRODUCER_ERROR:UNRELATED_ENTRY_FAILURE');return 2
        print('KERNEL_IMPORT_PROVENANCE:'+json.dumps(dict(source=report['source'],stack_module=report['stack_module'],stack_sha256=report['stack_sha256'],capture_module=report['capture_module'],capture_sha256=report['capture_sha256']),sort_keys=True))
        for row in rows.values():
            print('KERNEL_CASE:'+json.dumps({k:row[k] for k in ['name','returncode','errno_hint','log_sha256']},sort_keys=True))
            if row['returncode']:
                text=(out/(row['name']+'.log')).read_text(errors='replace')
                print('KERNEL_ERRNO:'+text.strip()[:240])
        print('KERNEL_LIFETIMES:OWN_PROVIDER_INIT_QUIET_AND_ALL_HANDLES_CLOSED_NO_MODELS')
        print('SYMPTOM_PRESENT:'+SIG if failures else 'SYMPTOM_ABSENT')
        return 1 if failures else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('REPRODUCER_ERROR:'+type(exc).__name__);raise SystemExit(2)
