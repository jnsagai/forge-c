"""Frozen black-box MCP registration check from planner 01M5QVAH97WCR7E9W0VPTSMK8Q."""
import sys,json
SIG='planner receives opaque JSON text instead of its authoritative plan schema'
def main():
 from forge_factory.mcp import sdk
 from forge_factory.mcp.servers import afo
 from forge_factory.afo.contracts import CONTRACTS
 app=sdk.build_server('forge-afo-mcp',afo.OPERATIONS)
 wire=next(t.parameters for t in app._tool_manager.list_tools() if t.name=='submit_recovery_plan')
 schema=json.loads((CONTRACTS/'recovery-plan.schema.json').read_text())
 prop=wire.get('properties',{}).get('plan',{})
 ref=next((x.get('$ref','') for x in prop.get('anyOf',[]) if '$ref' in x),'')
 actual=wire.get('$defs',{}).get(ref.rsplit('/',1)[-1])
 if actual!=schema:
  print('SYMPTOM_PRESENT:'+SIG);return 1
 print('SYMPTOM_ABSENT');return 0
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as e:print('REPRODUCER_ERROR:'+type(e).__name__+':'+str(e)[:160]);sys.exit(2)
