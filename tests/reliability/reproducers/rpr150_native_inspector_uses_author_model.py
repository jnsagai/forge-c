"""Native inspector request and model preparation must use the configured inspector model."""
import os,re
from forge_factory.acp import statements,_split_attrs,native_agent_nodes
from forge_factory.workflow.builder import build
from forge_factory.workorder import local_profile_structured
SIG="native HAL inspector inherits the author model instead of its configured inspector model"
def main():
    os.environ['FORGE_LRTX_ROOT']='/fixture/stack'
    a,_=build('WO-CONTROL',layer='HAL',peripheral='crc',stop_after='SWE.1')
    b,_=build('WO-CONTROL',layer='HAL',peripheral='crc',stop_after='SWE.1',structured={'model':'legacy','phases':[],'inspect_phases':[]})
    assert a==b,'legacy control changed'
    cases=[('cloud-bridge-terra-author-sol-inspector','gpt-6.1-terra','gpt-6.1-sol'),('local-rtx-v2-omniverse2-ornith-think-author-q38-inspector','hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0','qwen3.8:27b-q8_0')]
    bad=False
    for profile,author,inspector in cases:
        st=local_profile_structured({'id':profile},{'layer':'HAL'},author)
        dot,roles=build('WO-NATIVE',layer='HAL',peripheral='crc',structured=st,stop_after='SWE.1')
        attrs={n:s for _,_,_,n,s in statements(dot)}
        assert 'swe1_inspector' in native_agent_nodes(dot),'scenario did not reach native inspector'
        model=f'model="{inspector}"' in _split_attrs(attrs['swe1_inspector'])
        served=re.search(r'--model (\S+) --workspace',attrs['swe1_inspector_serve'])[1]
        assert re.search(r'--model (\S+) --workspace',attrs['release_manager_serve'])[1]==author,'inventory control changed'
        bad |= not model or served!=inspector
    print('SYMPTOM_PRESENT:'+SIG if bad else 'SYMPTOM_ABSENT');return 1 if bad else 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:print('REPRODUCER_ERROR:'+type(e).__name__+':'+str(e)[:160]);raise SystemExit(2)
