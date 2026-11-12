from pathlib import Path
import json,xml.etree.ElementTree as ET,hashlib
root=Path(__file__).resolve().parent
for filename,count,skip in [('feature013-0960e6b-regression.xml',297,3),('feature013-c008ba1-targeted.xml',41,0),('feature013-a477a6d-regression.xml',78,0),('feature013-typed-plan-final.xml',82,0),('feature013-scoped-skills.xml',52,1),('feature013-workspace-compat.xml',27,2)]:
 s=list(ET.parse(root/filename).getroot().iter('testsuite'));assert sum(int(x.get('tests')) for x in s)==count
 assert all(int(x.get('failures'))==0 and int(x.get('errors'))==0 for x in s)
 assert sum(int(x.get('skipped')) for x in s)==skip
for filename in ['independent-cre-c008ba1.json','feature013-live-handoff-cre.json','feature013-typed-plan-cre.json','feature013-scoped-skills-cre.json']:
 d=json.loads((root/filename).read_text());assert d['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW' and d['allowed_auto_deployment'] is False
 assert all(g['result'] in ['PASS','NOT_RUN'] for g in d['hard_gates'])
for a in json.loads((root/'artifact-hashes.json').read_text()):assert hashlib.sha256((root/a['path']).read_bytes()).hexdigest()==a['sha256']
print('PASS: revision-bound regression, independent CRE and artifact-integrity evidence verified; operational autonomy remains a separate incomplete task')
