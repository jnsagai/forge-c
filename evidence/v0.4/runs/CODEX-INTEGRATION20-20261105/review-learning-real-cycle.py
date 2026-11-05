"""Private CPU integration: TEST-signed review and REAL independent CRE receipts.

No owner key, production state, model, GPU, grants, service or source activation.
The generated review is a CONTROL, not an actual human product acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from forge_factory.common import REPO_ROOT, canonical_json, utc_now
from forge_factory.offline import disposition as D, export as X, feedback as F
from forge_factory.reliability import promotion, reproduce as RR
from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.registered import prevention
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B/'ops/scratch'
OUT = OPS/'review-learning-real-cycle-20261105'
BASE = '18814617abb98491abb5c03adb0802553634f14f'
CANDIDATE = '03da05043307b02439061d3a92b3744d8337b39f'
assert REPO_ROOT == B/'repos/forge-c-014-integration20'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not OUT.exists(), 'PRESERVE_EXISTING_ATTEMPT'
OUT.mkdir()
os.environ['FORGE_STATE_DIR'] = str(OUT/'state')
os.environ['FORGE_EVENTS_DIR'] = str(OUT/'events')

def write(name, value):
    path = OUT/name
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:
        json.dump(value,stream,indent=2)
    return path

with tempfile.TemporaryDirectory(prefix='TEST-review-key-',dir=OUT) as key_directory:
    key = Path(key_directory)/'GENERATED_TEST_KEY'
    subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True)
    signers = OUT/'TEST-allowed-signers'
    signers.write_text('CPUFixtureOwner namespaces="'+D.NAMESPACE+'" '+key.with_suffix('.pub').read_text())
    ws = OUT/'review-source/workspace'
    (ws/'.forge-run/advisory').mkdir(parents=True)
    (ws/'.forge-run/manifest.json').write_text(json.dumps(dict(work_order='WO-REVIEW-CPU-CONTROL',
        scope='NOT_NATIVE_PRODUCT_ACCEPTANCE',factory_revision=dict(commit=BASE,dirty=False,basis='recorded_at_launch'))))
    (ws/'.forge-run/advisory/SWE.1.jsonl').write_text(json.dumps(dict(phase='SWE.1',unresolved_findings=[
        dict(id='REGISTERED-LEARNING-REFUSED',detail='Actual source counterexample established by RPR175 normal CRE.')]))+'\n')
    bundle = OUT/'outgoing/report.zip'
    exported = X.build([ws],bundle)
    assert X.verify(bundle)==[]
    import zipfile
    with zipfile.ZipFile(bundle) as archive:
        run_key = json.loads(archive.read('MANIFEST.json'))['runs'][0]['run_key']
    reviews = OUT/'reviews'
    reviews.mkdir()
    review = dict(schema='forge-c/review-disposition/1',disposition_id='DSP-REAL-CPU-CONTROL',
        export_sha256=exported['sha256'],run_key=run_key,workorder='WO-REVIEW-CPU-CONTROL',
        subject=dict(kind='GAP',phase='SWE.1',ref='REGISTERED-LEARNING-REFUSED'),verdict='CONFIRMED_DEFECT',
        rationale='CONTROL: post-calibration learning registration was excluded. This is not owner product acceptance.',
        approver='CPUFixtureOwner',decided_utc=utc_now(),use='LEARNING_SET_ONLY',signature_ref='DSP-REAL-CPU-CONTROL.sig')
    review_path = reviews/'DSP-REAL-CPU-CONTROL.json'
    review_path.write_text(json.dumps(review))
    D.sign(review_path,key)
    original_review = review_path.read_bytes()
    original_bundle = bundle.read_bytes()
    intake = D.route(reviews,bundle=bundle,out=OUT/'intake.jsonl',allowed_signers=signers)
    assert intake['routed']==1 and not intake['refused'] and len(intake['capa_ids'])==1,intake
    cid = intake['capa_ids'][0]
    reg = CapaRegistry(CREStore(),load())
    assert reg.must(cid)['state']=='OPEN'
    stage = OUT/'staged-reproducer'
    stage.mkdir()
    source_path = 'factory/python/tests/fixtures/review_learning_probe.py'
    script = subprocess.check_output(['git','show',CANDIDATE+':'+source_path],cwd=REPO_ROOT)
    (stage/'reproducer.py').write_bytes(script)
    (stage/'reproducer.py').chmod(0o444)
    rid = 'AFO-REVIEW-CPU-CONTROL'
    descriptor = dict(id=rid,script='reproducer.py',sha256=hashlib.sha256(script).hexdigest(),
        symptom_signature='review intake rejects explicitly registered post-calibration learning baselines as held out',
        source_path=source_path,baseline_revision=BASE,fix_revision=CANDIDATE)
    manifest = stage/'manifest.yaml'
    manifest.write_bytes(canonical_json(dict(reproducers=[descriptor])))
    manifest.chmod(0o444)
    inputs = json.loads((OPS/'review-learning-inputs-before-tests.json').read_text())['files']
    with RR.WorktreePool() as pool:
        import shutil
        prepared=[]
        for revision in (BASE,CANDIDATE):
            tree = pool.get(revision)
            for entry in inputs:
                dst=tree/entry['path'];dst.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(REPO_ROOT/entry['path'],dst)
                assert hashlib.sha256(dst.read_bytes()).hexdigest()==entry['sha256']
            prepared.append(dict(revision=revision,worktree=str(tree),all8_10_before_tests=True,files=inputs))
        write('worktrees-before-tests.json',prepared)
        first = promotion.evaluate(CANDIDATE,BASE,reg.s,reg.p,reproducers=[rid],kind='FIX',pool=pool,
                                   staged_manifest=manifest)
        write('first-real-fix-decision.json',first)
        assert first['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW',first
        assert all(g['result']=='PASS' for g in first['hard_gates'])
        assert len(next(g['evidence_refs'] for g in first['hard_gates'] if g['name']=='prevention'))==174
        description=dict(root_cause='Original set membership omitted protected post-calibration learning transfers.',
            remedy='Respect registered learning transitions while retaining unspent held-out isolation.',
            operations=['offline.disposition.route'],error_codes=['DSP_HELDOUT_REFUSED'])
        qualified = F.qualify(reg,cid,first['decision_id'],staged_manifest=manifest,description=description)
        assert qualified['state']=='EFFECTIVENESS_OBSERVING'
        registered,issues = prevention(reg.s)
        assert not issues and rid in registered
        print(json.dumps(dict(stage='QUALIFIED_REVIEW_CAPA',capa_id=cid,decision=first['decision_id'],
                              registered_test=rid)),flush=True)
        # The complete next real gate must include the durable staged test, without supplying it as a new stage.
        second = promotion.evaluate(CANDIDATE,BASE,reg.s,reg.p,kind='CHANGE',pool=pool)
        write('next-real-fix-decision.json',second)
        assert second['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW',second
        refs = next(g['evidence_refs'] for g in second['hard_gates'] if g['name']=='prevention')
        assert len(refs)==175
        with reg.s.conn() as connection:
            rows = [dict(connection.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?',
                            (ref.split(':',1)[1],)).fetchone()) for ref in refs]
        assert any(r['reproducer_id']==rid and r['verdict']=='SYMPTOM_ABSENT' for r in rows)
        from forge_factory import workorder
        from forge_factory.mcp.sdk import ToolContext
        from forge_factory.mcp.servers.knowledge import FindIn,find_lessons
        future,metadata = workorder.prepare(REPO_ROOT/'examples/0002a-arm_55_rcc_ll',
                                           'WO-REVIEW-FUTURE-CPU-CONTROL',purpose='ASPICE_ONLY')
        published = F.publish(reg,cid,workspace=future,role='swe1-author')
        assert published['state']=='VALIDATED',published
        ctx = ToolContext('forge-knowledge','find_lessons','swe1-author','SWE.1',future,'CPU-FUTURE-CONSUMER')
        delivered = find_lessons(ctx,FindIn(query='registered learning held out calibration'))
        lessons = json.loads(delivered['metrics']['data'])['lessons']
        assert [x['lesson_id'] for x in lessons]==[published['lesson_id']],delivered
        assert metadata['tool_versions']=={'forge-factory':metadata['factory_revision']['commit']}
        assert review_path.read_bytes()==original_review and bundle.read_bytes()==original_bundle
        write('result.json',dict(status='PASS_PRIVATE_CPU_CONTROL',source=CANDIDATE,baseline=BASE,
            actual_TEST_signature=True,actual_independent_FIX_decision=first['decision_id'],
            actual_next_CHANGE_decision=second['decision_id'],
            first_prevention=174,next_prevention=175,registered_staged_test=rid,capa_id=cid,
            capa_state=reg.must(cid)['state'],lesson=published,mcp_delivery='MATCHED_FUTURE_AUTHOR',
            original_review_and_bundle_unchanged=True,native_or_human_product_acceptance=False,model_calls=0,
            owner_key_access=False,source_or_service_activation=False))
        print(json.dumps(dict(stage='PASS_PRIVATE_CPU_REVIEW_TO_FUTURE_PREVENTION_AND_MEMORY',
                              result=str(OUT/'result.json'))),flush=True)
