"""CRE backfill for the owner-lane fixes V17-V19 (owner 2026-11-07: "are we using CRE and CAPA?").

One CAPA per call: freeze its reproducer in the oracle manifest (append-only), open + triage, causal contrast
baseline vs candidate, register the fix, promotion gate, prevention. Never deploys anything.
Usage: capa-run.py <key>   (keys in SPECS)
"""
import json
import sys
from pathlib import Path

import yaml
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.reliability import promotion, reproduce as RR
from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OUT = B / 'ops/scratch/cre-backfill-v17-v19-20261107'
assert REPO_ROOT == B / 'repos/forge-c-014-cre-oracle-v19', REPO_ROOT
MAN = REPO_ROOT / 'tests/reliability/reproducers/manifest.yaml'

SPECS = {
    '177': dict(
        capa='CAPA-177', rpr='RPR-177', script='rpr177_think_author_byte_bound.py',
        baseline='b7d1013bd4d21ef00a108f2a4b7a26e437591e24', candidate='5cba4795f46c0a813b83fccb1e9a8bbd81d14ec2',
        incident='OWNER-LANE-L90-CAPABILITY-LIMIT-BYTE-COUNT-20261107',
        fingerprint='CAPABILITY_LIMIT:utf8_byte_upper_bound:ornith-think-afo-author',
        symptom='the pinned think-AFO profile measures the Ornith author by byte count instead of native tokens',
        observed_in='Omniverse2 owner lane 2026-11-06/07: L90 SWE.6 author and recovery planner requests of 115-123 k bytes refused as CAPABILITY_LIMIT',
        error_codes=['CAPABILITY_LIMIT'], operations=['lrtx.llm_gateway.durable_admitted', 'lrtx.request_measurement.policy'],
        root_cause='The mission-bound think-AFO profile file could not be edited (its sha is history scope), so its Ornith route kept utf8_byte_upper_bound, which counts bytes as tokens.',
        remedy='Name the pinned profile route in code (PINNED_PROFILE_ROUTES) so the gateway measures it natively with llama-server /apply-template and /tokenize; profile bytes unchanged.'),
    '178': dict(
        capa='CAPA-178', rpr='RPR-178', script='rpr178_retry_starts_empty.py',
        baseline='5cba4795f46c0a813b83fccb1e9a8bbd81d14ec2', candidate='a32c7c31b03d297eab41442c46d565f67e7a6beb',
        incident='OWNER-LANE-L90-RETRY-LOSES-TESTS-20261107',
        fingerprint='RETRY_RESEEDS_FROM_L34G:swe6-tests-lost',
        symptom="a SWE.6 retry of the owner series starts with none of the earlier attempt's tests",
        observed_in='Omniverse2 owner lane 2026-11-07: L90W reached 15/24 tests; L90X re-seeded from L34G and started from 0/24',
        error_codes=['MISSING_REQUIRED_OUTPUT'], operations=['workorder.resume', 'SWE.6/author'],
        root_cause='Every owner-lane retry resumes from the frozen L34G SWE.5 baseline; nothing carried the robot suite and scenario files of the earlier attempt.',
        remedy='attempt_carry installs the earlier attempt tests uncommitted for owner-series SWE.6 retries, records attempt_carry in the manifest and adds a prompt note.'),
    '179': dict(
        capa='CAPA-179', rpr='RPR-179', script='rpr179_carry_restores_last_not_best.py',
        baseline='a32c7c31b03d297eab41442c46d565f67e7a6beb', candidate='b13eeaf3',
        incident='OWNER-LANE-L90Z-CARRY-LAST-NOT-BEST-20261107',
        fingerprint='ATTEMPT_CARRY_LAST_FILES:broken-after-best-run',
        symptom="a SWE.6 retry restores the attempt's last broken tests instead of its best robot run",
        observed_in='Omniverse2 owner lane 2026-11-07: L90Z reached 24/24 tests, 22/24 requirements at 09:56:59, then invented register names broke the build',
        error_codes=['ROBOT_BUILD_FAILED'], operations=['attempt_carry.install', 'SWE.6/author'],
        root_cause='The V18 carry copied the attempt workspace files as they ended, not the files of its best robot run.',
        remedy='Pair each run_robot result with its test-integrity row and restore that run snapshot by SHA-256; most passed, then most verified, later wins a tie.'),
    '180': dict(
        capa='CAPA-180', rpr='RPR-180', script='rpr180_swe6_author_35_calls.py',
        baseline='a32c7c31b03d297eab41442c46d565f67e7a6beb', candidate='b13eeaf3',
        incident='OWNER-LANE-L90X-TURN-BUDGET-20261107',
        fingerprint='TURN_BUDGET_EXHAUSTED:swe6-author:35',
        symptom="the SWE.6 author's per-visit tool budget is still the 35-call limit L90X exhausted",
        observed_in='Omniverse2 owner lane 2026-11-07: L90X (V17) spent about 30 of 35 author calls on glob/read, TURN_BUDGET_EXHAUSTED, 0/24',
        error_codes=['TURN_BUDGET_EXHAUSTED'], operations=['policy.governor.turn_limit', 'SWE.6/author'],
        root_cause='The author max_turns of 35 dates from 2026-10-15 (qwen3:8b); the Ornith author needs more calls to read the HAL before writing.',
        remedy='Owner 2026-11-07: authors 4096 calls per visit (the structured-visit ceiling), other roles 200, inspectors keep 4 reserved; node timeouts still bound a visit.'),
}


def freeze(spec, rev):
    m = yaml.safe_load(MAN.read_text())
    if any(r['id'] == spec['rpr'] for r in m['reproducers']):
        return
    path = MAN.parent / spec['script']
    entry = dict(id=spec['rpr'], script=spec['script'], sha256=sha256_file(path), symptom_signature=spec['symptom'],
                 observed_in=spec['observed_in'], baseline_revision=spec['baseline'], fix_revision=rev,
                 error_codes=spec['error_codes'], operations=spec['operations'], root_cause=spec['root_cause'],
                 remedy=spec['remedy'])
    with MAN.open('a') as f:  # append-only: earlier entries stay byte-identical
        f.write(yaml.safe_dump([entry], sort_keys=False, width=120))


def main(key):
    import subprocess
    spec = SPECS[key]
    cand = subprocess.check_output(['git', '-C', str(REPO_ROOT), 'rev-parse', spec['candidate']], text=True).strip()
    import shutil
    assert shutil.which('clang') and 'LLVM-19' in shutil.which('clang'), 'FACTORY_TOOLCHAIN_NOT_ON_PATH'
    n = 1
    while (OUT / f"{spec['capa'].lower()}-decision-r{n}.json").exists() or (n == 1 and (OUT / f"{spec['capa'].lower()}-decision.json").exists()):
        n += 1
    dest = OUT / f"{spec['capa'].lower()}-decision-r{n}.json"
    freeze(spec, cand)
    manifest, issues = RR.load_manifest()
    assert not issues and spec['rpr'] in manifest, issues
    s, p = CREStore(), load()
    r = CapaRegistry(s, p)
    if r.get(spec['capa']) is None:
        r.open(spec['capa'], [spec['incident']], [spec['fingerprint']], 'owner-lane fix backfilled through CRE (owner 2026-11-07)')
        r.triage(spec['capa'], spec['root_cause'], spec['rpr'], 'AGENT')
    resumed = r.must(spec['capa'])['state'] == 'FIX_CANDIDATE'  # cause already verified; only the gate is repeated
    assert resumed or r.must(spec['capa'])['state'] == 'REPRODUCER_PENDING', r.must(spec['capa'])['state']
    with RR.WorktreePool() as pool:
      if not resumed:
        base = RR.run(s, p, spec['rpr'], spec['baseline'], 'BASELINE', pool, manifest)
        print(json.dumps(dict(phase='BASELINE', verdict=base['verdict'], run=base['run_id'])), flush=True)
        candrun = RR.run(s, p, spec['rpr'], cand, 'CANDIDATE', pool, manifest)
        print(json.dumps(dict(phase='CANDIDATE', verdict=candrun['verdict'], run=candrun['run_id'])), flush=True)
        state = r.verify_cause(spec['capa'], base, candrun)['state']
        print(json.dumps(dict(capa=spec['capa'], state=state)), flush=True)
        if state != 'CAUSE_VERIFIED':
            return 1
        r.register_fix(spec['capa'])
      if True:
        rprs = [x for k, x in SPECS.items() if x['candidate'] == spec['candidate'] and x['rpr'] in manifest]
        decision = promotion.evaluate(cand, spec['baseline'], s, p, reproducers=[x['rpr'] for x in rprs], kind='FIX', pool=pool)
        with dest.open('x') as f:
            json.dump(decision, f, indent=2)
        print(json.dumps(dict(decision=decision['decision'], id=decision['decision_id'],
                              gates={g['name']: g['result'] for g in decision['hard_gates']}, reasons=decision['reasons'][:6])), flush=True)
        if decision['decision'] != 'ELIGIBLE_FOR_OFFLINE_REVIEW':
            return 1
        prevention = next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')
        rows = {v['run_id']: v for v in RR.reproducer_runs(s, spec['rpr'])}
        current = next(rows[ref.split(':', 1)[1]] for ref in prevention if ref.split(':', 1)[1] in rows)
        r.register_prevention(spec['capa'], current)
        r.link(spec['capa'], 'PROMOTION_DECISION', decision['decision_id'])
        print(json.dumps(dict(capa=spec['capa'], state=r.must(spec['capa'])['state'], deployed=False)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
