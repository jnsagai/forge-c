"""Read-only verification of CRE decision rows, raw reproducer logs and benchmarks."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('prefix')
    args = parser.parse_args()
    assert args.prefix.replace('-', '').isalnum()
    prefix = B / 'ops/scratch' / args.prefix
    path = Path(str(prefix) + '-decision.json')
    decision = json.loads(path.read_text())
    with sqlite3.connect(f'file:{B}/state/supervisor/incidents.sqlite3?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        stored = dict(db.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?',
                                 (decision['decision_id'],)).fetchone())
        assert json.loads(stored['record']) == {
            k: v for k, v in decision.items() if k not in ('candidate_revision', 'baseline_revision')}
        assert stored['candidate'] == decision['candidate_revision']
        assert stored['baseline'] == decision['baseline_revision']
        assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
        gates = decision['hard_gates']
        assert len(gates) == 7 and all(g['result'] == 'PASS' for g in gates)
        refs = {r for g in gates for r in g['evidence_refs']}
        runs, benchmarks = [], []
        for ref in sorted(refs):
            ident = ref.split(':', 1)[-1]
            if ref.startswith('reproducer-run:'):
                row = dict(db.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?', (ident,)).fetchone())
                assert sha(B / 'state/reliability/reproducers' / f'{ident}.log') == row['log_sha256']
                expected = ((decision['baseline_revision'], 1, 'SYMPTOM_PRESENT') if row['role'] == 'BASELINE'
                            else (decision['candidate_revision'], 0, 'SYMPTOM_ABSENT'))
                assert (row['revision'], row['exit_code'], row['verdict']) == expected
                runs.append(row)
            elif ref.startswith('benchmark-run:'):
                row = dict(db.execute('SELECT * FROM cre_benchmark_runs WHERE run_id=?', (ident,)).fetchone())
                record = json.loads(row['record'])
                assert record['revision'] == row['revision'] in (decision['baseline_revision'], decision['candidate_revision'])
                assert record['run_id'] == ident and record['suite_sha256'] == row['suite_sha256']
                assert record['n'] == record['passed'] == len(record['results'])
                assert all(result['status'] == 'PASS' for result in record['results'])
                benchmarks.append(row)
        assert len(runs) == 177 and len(benchmarks) == 4
        prevention = [row for row in runs if row['role'] == 'PREVENTION']
        assert len(prevention) == len({row['reproducer_id'] for row in prevention}) == 175
        assert {row['role'] for row in runs} == {'BASELINE', 'CANDIDATE', 'PREVENTION'}
        output = dict(schema='forge-c/independent-CRE-raw-verification/1', status='PASS',
                      decision_id=decision['decision_id'], source=decision['candidate_revision'],
                      baseline=decision['baseline_revision'], decision_sha256=sha(path),
                      gates={g['name']: g['result'] for g in gates}, RR_records_and_rawlogs_verified=177,
                      prevention=175, benchmarks_verified=4, reproducer_rows=runs, benchmark_rows=benchmarks,
                      verification_script_sha256=sha(Path(__file__)), runtime_deployment=False)
    destination = Path(str(prefix) + '-raw-verification.json')
    with destination.open('x') as stream:
        json.dump(output, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(path=str(destination), sha256=sha(destination), decision_id=decision['decision_id'])))


if __name__ == '__main__':
    main()
