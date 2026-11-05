"""Independent normal public SDK/Matrix4 timing-credit control on frozen approved WWDG engineering inputs."""
from pathlib import Path
import csv,hashlib,json,os,tempfile,zipfile

SIG='WWDG frozen target instruction and virtual-time requirement receives host-only verified credit'
ASSET='reliability-fixtures/rpr171-approved-wwdg-fd754dde3c2c209253fe7a65e61b22e7f242a1e633ceb8f015b0df9e4c75c776.zip'
SHA='fd754dde3c2c209253fe7a65e61b22e7f242a1e633ceb8f015b0df9e4c75c776'
TEST='''// FORGE_UNIT_BACKEND: provided-ll-ram-v1
#include <gtest/gtest.h>
#include <ctime>
extern "C" {
#include "stm32n6xx_hal_wwdg.h"
}
/** @test UT-025
 * @verifies USPEC-HAL-04-05
 * Host CPU clock only; no target instruction/virtual-time or silicon claim.
 */
TEST(SWU_HAL_04, UT_025) {
 const std::clock_t before = std::clock();
 const hal_status_t status = HAL_WWDG_ClearEarlyWakeupFlag();
 const std::clock_t after = std::clock();
 EXPECT_EQ(HAL_OK, status);
 EXPECT_LE(double(after-before)/CLOCKS_PER_SEC, 0.001);
}
'''

def main():
 from forge_factory.common import data_root
 from forge_factory.mcp import sdk
 from forge_factory.mcp.servers import tests as U
 from forge_factory.registry.mcp_registry import fabro_tool_name
 from forge_factory.inspection import swtrace
 from forge_factory.workflow.provided_input_identity import effective_identity
 asset=data_root()/'inputs'/ASSET
 if hashlib.sha256(asset.read_bytes()).hexdigest()!=SHA:raise RuntimeError('FROZEN_APPROVED_FIXTURE_HASH_MISMATCH')
 with tempfile.TemporaryDirectory(prefix='rpr171-') as td:
  root=Path(td);ws=root/'workspace';ws.mkdir()
  with zipfile.ZipFile(asset) as z:
   if len(z.infolist())!=175 or sum(x.file_size for x in z.infolist())!=6423943:raise RuntimeError('FROZEN_FIXTURE_SIZE_MISMATCH')
   for item in z.infolist():
    p=Path(item.filename)
    if p.is_absolute() or '..' in p.parts or item.is_dir() or item.file_size>4000000:raise RuntimeError('UNSAFE_FIXTURE_ENTRY')
    q=ws/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(z.read(item))
  pins=['.forge-run/manifest.json','.forge-run/gates/gate-log.jsonl','workproducts/SWE.4/unit_test_plan.json','workproducts/SWE.3/unit_specifications.md','workproducts/SWE.2/api_calls.json','workproducts/SWE.1/software_requirements.md','software/hal/stm32n6xx_hal_wwdg.c','software/hal/stm32n6xx_hal_wwdg.h','software/ll/stm32n6xx_ll_wwdg.h']
  h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
  before={p:h(ws/p) for p in pins};effective_identity(ws,'software/ll/stm32n6xx_ll_wwdg.h')
  for name in ('target_timing.json','target_observations.json','target_wwdg_timing.json'):
   (ws/'software/tests/unit'/name).unlink(missing_ok=True)
  (ws/'software/tests/unit/test_wwdg.cpp').write_text(TEST)
  os.environ['FORGE_STATE_DIR']=str(root/'private-state');os.environ['FORGE_BINDING_ID']='rpr171-normal-public-control'
  args={'coverage':False};op=next(x for x in U.OPERATIONS if x.name=='run_unit')
  sdk.issue_ticket(os.environ['FORGE_BINDING_ID'],fabro_tool_name('forge-tests-mcp.run_unit'),args,'swe4-author','rpr171-public-control','SWE.4',str(ws))
  result=sdk.invoke('forge-tests-mcp',op,args)
  swtrace.build_all(ws,render=False,doxygen=False,upto='SWE.4',write={4},export=False)
  rows=list(csv.DictReader((ws/'workproducts/SWE.4/traceability/matrix_4_unittest_to_unitspec.csv').open()))
  chosen=[r for r in rows if r['test']=='UT-025' and r['uspec']=='USPEC-HAL-04-05']
  if before!={p:h(ws/p) for p in pins}:raise RuntimeError('ENGINEERING_INPUTS_CHANGED')
  if not chosen:raise RuntimeError('NORMAL_PUBLIC_TIMING_ROW_NOT_REACHED')
  metrics=result.get('metrics',{})
  if metrics.get('executables')!=1 or metrics.get('passed',0)<1:raise RuntimeError('HOST_POSITIVE_EXECUTION_CONTROL_NOT_REACHED')
  bad=any(r['status']=='VERIFIED' for r in chosen)
  print(json.dumps({'public_unit_status':result['status'],'host_passed':metrics['passed'],'target_evidence':metrics.get('target_evidence'),'matrix4_timing_statuses':[r['status'] for r in chosen],'provided_approval_valid':True,'engineering_inputs_unchanged':True},sort_keys=True))
  if bad:
   print('SYMPTOM_PRESENT:'+SIG);return 1
  if result['status']!='FAIL':raise RuntimeError('HOST_ONLY_TIMING_NOT_EXPLICITLY_REFUSED')
  print('SYMPTOM_ABSENT');return 0

if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:
  print('REPRODUCER_ERROR:'+type(e).__name__+':'+str(e)[:180]);raise SystemExit(2)
