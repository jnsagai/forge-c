
from pathlib import Path
import json,sys
R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1')
rows=[json.loads(x) for x in (R/'state/llm-gateway/request-measurements.jsonl').read_text().splitlines()]
bad=[{'at':x['ts_utc'],'input_bound_tokens':x['measurement']['input_tokens'],'output_reserve_tokens':x['output_reserve_tokens'],
'context_limit_tokens':x['context_limit_tokens'],'request_sha256':x['measurement']['sha256']} for x in rows if not x['fits']]
print(json.dumps({'context_refusals':bad,'max_observed_input_bound':max(x['measurement']['input_tokens'] for x in rows)}))

