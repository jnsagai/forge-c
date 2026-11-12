from pathlib import Path
import asyncio,json,os,sys
P=Path('/mnt/data/forge-c/production-local-014');sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.mcp.sdk import build_server
from forge_factory.mcp.servers.maintainer import OPERATIONS
s=build_server('forge-maintainer-mcp',OPERATIONS)
for t in asyncio.run(s.list_tools()):
 if t.name=='submit_candidate':print(json.dumps({'tool':t.name,'native_input_schema':t.input_schema,'generation_requests':0}))
