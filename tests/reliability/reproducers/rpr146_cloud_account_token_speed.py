"""A bridge-only account call must supply a measured rate; gateway and stale controls."""
import json,os,tempfile,time
from pathlib import Path
from forge_factory.lrtx.floor_api import recent_speed
SIG = "active cloud account calls have no token speed before Fabro node completion"
def main():
    now=time.time()
    with tempfile.TemporaryDirectory() as td:
        os.environ['FORGE_STATE_DIR']=td
        root=Path(td);g=root/'llm-gateway/usage.jsonl';g.parent.mkdir()
        g.write_text(json.dumps({'ts_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now-20)),'model':'control','tokens_output':100,'latency_ms':5000})+'\n')
        assert recent_speed(now)['tok_s']==20,'gateway control failed'
        g.unlink();p=root/'cloud-bridge/calls.jsonl';p.parent.mkdir()
        p.write_text(json.dumps({'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now-30)),'model':'gpt-6.1-terra','wall_ms':10000,'usage':{'completion_tokens':150,'billing':'account'}})+'\n')
        r=recent_speed(now)
        if r is None: print('SYMPTOM_PRESENT:'+SIG);return 1
        assert r['tok_s']==15 and r['model']=='gpt-6.1-terra','wrong bridge rate'
        assert recent_speed(now+3600) is None,'stale metric presented as current'
    print('SYMPTOM_ABSENT');return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:print('REPRODUCER_ERROR:'+type(e).__name__+':'+str(e)[:160]);raise SystemExit(2)
