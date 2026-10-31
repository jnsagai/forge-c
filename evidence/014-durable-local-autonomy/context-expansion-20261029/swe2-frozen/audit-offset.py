from pathlib import Path
import sys,json,re,hashlib
P=Path('/mnt/data/forge-c/production-local-014')
ws=P/'state/workorders/WO-AFO-774900b297bdde37-a1/workspace'
src=ws/'inputs/RM0486-rev4-ch26-crc.md'
raw=src.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='11cbedc82a26259b3228f2673d3c81dd1140adff7aff195c6cf25ee300de2ea1'
text=raw.decode()
section=re.search(r'^####[^\n]*\(CRC_IDR\)\s*\n(.*?)(?=^####|\Z)',text,re.M|re.S)
assert section
offset=re.search(r'Address offset:\s*(0x[0-9a-fA-F]+)',section[1]);assert offset
expected=int(offset[1],16)
arch=ws/'workproducts/SWE.2/software_architecture.md';doc=arch.read_text()
table=re.search(r'^## Register table\s*\n(.*?)(?=^## |\Z)',doc,re.M|re.S);assert table
rows=[line.split('|')[1:-1] for line in table[1].splitlines() if line.strip().startswith('|')]
matches=[r for r in rows if r and re.match(r'^\s*CRC_IDR(?:\.|\s|$)',r[0])]
assert len(matches)==1
actual=int(matches[0][1].strip(),16);assert actual==expected
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.common import utc_now
print(json.dumps({'schema':'forge-c/scoped-primary-reference-crosscheck/1','at':utc_now(),
 'source':{'path':str(src.relative_to(ws)),'sha256':hashlib.sha256(raw).hexdigest(),'section':'26.4.2 CRC independent data register'},
 'artifact':{'path':str(arch.relative_to(ws)),'sha256':hashlib.sha256(arch.read_bytes()).hexdigest()},
 'register':'CRC_IDR','primary_offset':hex(expected),'architecture_offset':hex(actual),
 'status':'PASS_SCOPED_OFFSET_MATCH','registers_crosschecked':1,
 'scope':'One actual CRC_IDR offset only; not all hardware semantics, base addresses or product acceptance',
 'production_checker_offset_coverage':0,'production_checker_limitation':'No matching dedicated register section file/name in this workspace; existing structure PASS does not prove offset checking',
 'read_only':True,'generation_requests':0},indent=2))
