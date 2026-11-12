import json
from pathlib import Path
from forge_factory.reliability import reproduce as RR,promotion
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore
from forge_factory.reliability.capa import CapaRegistry
s=CREStore();p=load();r=CapaRegistry(s,p);manifest,issues=RR.load_manifest();assert not issues,issues
r.open('CAPA-171',incident_ids=['CAPA-171'],reason='Independent actual normal SDK/Matrix4 WWDG host-only target timing false credit; source/history/frozen contracts preserved.')
r.triage('CAPA-171','Frozen target-instruction and virtual-time WWDG rows fall through to host-only test annotation because existing per-call target timing producer is CRC-only; require current approved WWDG target proofs even without declaration.','RPR-171','RULE')
B='edff27525b8331af7ce943de0490172c9fc180c5';C='12dbbed2d67484dc0271f0352ae4f01e0a9c372e'
with RR.WorktreePool() as pool:
 base=RR.run(s,p,'RPR-171',B,'BASELINE',pool,manifest);print(json.dumps(base),flush=True)
 cand=RR.run(s,p,'RPR-171',C,'CANDIDATE',pool,manifest);print(json.dumps(cand),flush=True)
 v=r.verify_cause('CAPA-171',base,cand);print(json.dumps(v),flush=True);assert v['state']=='CAUSE_VERIFIED',v
 r.register_fix('CAPA-171')
 d=promotion.evaluate(C,B,s,p,reproducers=['RPR-171'],kind='FIX',pool=pool);print(json.dumps(d),flush=True)
 Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/ops/scratch/capa171-fix-decision.json').write_text(json.dumps(d,indent=2)+'\n')
 assert d['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW' and all(g['result']=='PASS' for g in d['hard_gates']),d
print('CAPA171_FULL_FIX_ELIGIBLE',flush=True)
