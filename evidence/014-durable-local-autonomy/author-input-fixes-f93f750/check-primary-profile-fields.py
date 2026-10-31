from pathlib import Path
import sys,json,re,hashlib
sys.path.insert(0,str(Path.cwd()/'factory/python'))
from forge_factory import workorder,peripheral
from forge_factory.inspection.regmap import parse_section
path=Path(sys.argv[1]);pid=sys.argv[2];profile=peripheral.load(pid);prefix=profile['register_prefix']
parts,_=workorder.split_sections(path.read_text(),path.stem)
regs={r['name']:r for r in (parse_section(text,prefix) for text in parts.values()) if r}
assert regs
bad=[]
rx=re.compile(r'\b('+re.escape(prefix)+r'_[A-Z0-9]+)\.([A-Z][A-Z0-9_]*)\b')
for key,text in profile['prompt'].items():
 for reg,field in rx.findall(text):
  if reg not in regs or field not in regs[reg]['fields']:
   bad.append({'guidance':key,'reference':reg+'.'+field,'primary_fields':sorted(regs.get(reg,{}).get('fields',{}))})
print(json.dumps({'status':'FAIL' if bad else 'PASS','scope':'PROFILE_REFERENCES_VS_HASH_BOUND_PRIMARY_REGISTER_NAMES_ONLY',
 'profile':pid,'profile_sha256':profile['sha256'],'primary_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
 'registers':len(regs),'findings':bad}))
raise SystemExit(1 if bad else 0)
