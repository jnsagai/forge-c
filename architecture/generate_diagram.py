from lxml import etree as ET
from pathlib import Path
from datetime import datetime, timezone
from copy import deepcopy

BASE=Path(__file__).resolve().parent/'Forge-C_Fabro_DarkFactory_v0.3.drawio'
DEST=Path(__file__).resolve().parent/'Forge-C_Fabro_DarkFactory_v0.4.drawio'
NAVY='#15253d';NAVY2='#284663';INK='#203149';MUTED='#55677c';BG='#f4f7fb';WHITE='#ffffff';BORDER='#ccd8e7'
BLUE='#2868a8';BLUEB='#eaf4ff';MINT='#18836d';MINTB='#e8f7f1';PURPLE='#6749a7';PURPLEB='#f0eaff';RED='#a33e54';REDB='#fff0f2';AMBER='#a56d13';AMBERB='#fff4db';GRAYB='#f8fafc'

def newpage(name,id,w,h,title,subtitle,status='DESIGN — NOT IMPLEMENTED'):
 d=ET.Element('diagram',name=name,id=id)
 m=ET.SubElement(d,'mxGraphModel',dx='2200',dy='1200',grid='1',gridSize='10',guides='1',tooltips='1',connect='1',arrows='1',fold='1',page='1',pageScale='1',pageWidth=str(w),pageHeight=str(h),math='0',shadow='0')
 r=ET.SubElement(m,'root');ET.SubElement(r,'mxCell',id='0');ET.SubElement(r,'mxCell',id='1',parent='0')
 rect(r,'page_background','',0,0,w,h,BG,BG,rounded=False)
 rect(r,'navy_header','',0,0,w,151,NAVY,NAVY,rounded=False)
 text(r,'heading',title,56,29,w-630,63,35,WHITE,True)
 text(r,'subheading',subtitle,58,94,w-130,34,18,'#d2e2f1')
 rect(r,'state_badge',status,w-470,26,400,51,NAVY2,'#59718d',font=16,font_color=WHITE,bold=True)
 rect(r,'foot_band','',0,h-55,w,55,WHITE,BORDER,rounded=False)
 text(r,'footer','Forge-C v0.4 · Claude implementation plan · Editable draw.io · No automatic ISO 26262 or ASPICE approval',50,h-48,w-100,40,16,MUTED)
 return d,r

def rect(r,id,value,x,y,w,h,fill=WHITE,stroke=BORDER,font=19,font_color=INK,bold=False,rounded=True,align='center',dashed=False,shape=None):
 if shape=='diamond':style='rhombus;perimeter=rhombusPerimeter;'
 elif rounded:style='rounded=1;arcSize=12;'
 else:style='rounded=0;'
 style+=f'whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontColor={font_color};fontSize={font};fontFamily=Arial;align={align};verticalAlign=middle;strokeWidth=2;spacingLeft=14;spacingRight=14;spacingTop=7;spacingBottom=7;fontStyle={1 if bold else 0};shadow=0;'
 if dashed:style+='dashed=1;dashPattern=7 5;'
 c=ET.SubElement(r,'mxCell',id=id,value=value,style=style,vertex='1',parent='1')
 ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
 return c

def text(r,id,value,x,y,w,h,font=19,font_color=INK,bold=False,align='left'):
 return rect(r,id,value,x,y,w,h,fill='none',stroke='none',font=font,font_color=font_color,bold=bold,rounded=False,align=align)

def edge(r,id,start,end,color=BLUE,label='',dashed=False,points=None,srcside=None,dstside=None,width=3):
 style=f'edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeColor={color};strokeWidth={width};endArrow=block;endFill=1;fontColor={color};fontFamily=Arial;fontSize=16;labelBackgroundColor={WHITE};'
 coords={'top':(.5,0),'bottom':(.5,1),'left':(0,.5),'right':(1,.5)}
 if srcside: a,b=coords[srcside];style+=f'exitX={a};exitY={b};exitDx=0;exitDy=0;'
 if dstside: a,b=coords[dstside];style+=f'entryX={a};entryY={b};entryDx=0;entryDy=0;'
 if dashed:style+='dashed=1;dashPattern=8 5;'
 c=ET.SubElement(r,'mxCell',id=id,value=label,style=style,edge='1',source=start,target=end,parent='1')
 g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
 if points:
  ar=ET.SubElement(g,'Array',attrib={'as':'points'})
  for x,y in points:ET.SubElement(ar,'mxPoint',x=str(x),y=str(y))
 return c

def panel(r,id,title,x,y,w,h):
 rect(r,id,'',x,y,w,h,WHITE,BORDER,rounded=True)
 text(r,id+'_title',title,x+20,y+9,w-40,42,23,NAVY,True)

# 01 comprehensive factory view
p,r=newpage('01 Dark factory architecture v0.4','forge-c-0.4-p1',3000,1860,'FORGE-C  |  Self-healing dark software factory','Fabro orchestration · Skills + MCP everywhere · model-free health control · offline release review')
panel(r,'flow_panel','A · AUTONOMOUS PRODUCT DEVELOPMENT',45,185,2910,511)
rect(r,'intake','APPROVED INPUTS<br/>HSI / MCU data<br/>ASIL B allocation<br/>memory &amp; timing budgets',84,285,365,153,BLUEB,'#90b6df',18,bold=True)
rect(r,'fabro','FABRO ORCHESTRATOR<br/>Local Ollama/Qwen<br/>checkpoints + bounded retries',531,285,374,153,PURPLEB,'#a99acf',19,bold=True)
rect(r,'swe','SWE.1 → SWE.6<br/>Author + separate inspector<br/>checklist / findings / rework',1005,285,460,153,BLUEB,'#90b6df',20,bold=True)
rect(r,'quality','QUALITY GATES<br/>MISRA subset / C static analysis<br/>unit + integration / MC/DC<br/>Flash · RAM · stack · cycles',1580,270,470,180,GRAYB,BORDER,19,bold=True)
rect(r,'manager','RELEASE MANAGER<br/>Collect software + SWE/ASPICE<br/>safety/QA/inspection/ops evidence',2150,285,430,153,MINTB,'#83c3aa',18,bold=True)
rect(r,'bundle','REVIEW PACKAGE<br/>READY FOR OFFLINE REVIEW<br/>or BLOCKED',2665,285,265,153,AMBERB,'#ddc28b',18,bold=True)
for i,a,b in [(1,'intake','fabro'),(2,'fabro','swe'),(3,'swe','quality'),(4,'quality','manager'),(5,'manager','bundle')]: edge(r,'f'+str(i),a,b,BLUE if i<4 else MINT,srcside='right',dstside='left')
rect(r,'feedback','INSPECTION / VERIFICATION REWORK<br/>Failed checks create tracked findings; return to responsible SWE author; reinspect revised baseline. Max retries → BLOCKED package.',615,492,1490,125,REDB,'#e2aab4',18,bold=True)
edge(r,'feedback1','quality','feedback',RED,'FAIL',srcside='bottom',dstside='top')
edge(r,'feedback2','feedback','swe',RED,'REWORK',srcside='top',dstside='bottom',dashed=True)
rect(r,'offline','OUTSIDE FACTORY: human receives package and performs independent OFFLINE review / disposition (not an in-run approval gate)',1620,615,1320,54,AMBERB,'#ddc28b',17,bold=True)
edge(r,'to_offline','bundle','offline',AMBER,dashed=True,srcside='bottom',dstside='right')

panel(r,'tools_panel','B · MANDATORY AGENT INTERFACES',45,739,2910,367)
rect(r,'skill_reg','20 VERSIONED SKILLs<br/>One SKILL.md per AI role<br/>role permissions + budgets',95,839,600,177,PURPLEB,'#b9a3da',20,bold=True)
rect(r,'mcp_gate','ROLE-SCOPED MCP GATEWAY<br/>Every AI-accessible tool via MCP<br/>No generic shell bypass',816,839,645,177,BLUEB,'#8eb9e0',20,bold=True)
rect(r,'tool_adapters','9 OSS MCP DOMAIN SERVERS<br/>Build · Analysis · Test · Sim<br/>Evidence · Git · Observer<br/>Knowledge · Docs',1585,821,688,208,GRAYB,BORDER,19,bold=True)
rect(r,'tool_engine','ENGINEERING BACKENDS<br/>GCC/Clang · Cppcheck · CBMC<br/>Unity · LLVM-Cov · Renode<br/>ELF / Stack / Traceability',2381,839,529,177,MINTB,'#83c3aa',18,bold=True)
edge(r,'t1','skill_reg','mcp_gate',PURPLE,srcside='right',dstside='left');edge(r,'t2','mcp_gate','tool_adapters',BLUE,srcside='right',dstside='left');edge(r,'t3','tool_adapters','tool_engine',MINT,srcside='right',dstside='left')
text(r,'disclosure','Implementation rule: wrapper MCPs are REQUIRED engineering tasks, not currently implemented. Existing upstream Fabro Skills/MCP support must be version-verified.',103,1034,2680,43,16,MUTED)

panel(r,'ops_panel','C · INDEPENDENT CONTROL PLANE — ZERO MODEL TOKENS WHILE HEALTHY',45,1140,2910,430)
rect(r,'supervisor','MODEL-FREE SUPERVISOR<br/>OS-managed · default 60 s poll<br/>Fabro / queue / MCP / storage<br/>GPU-RAM / stage heartbeat',93,1243,551,180,BLUEB,'#8eb9e0',19,bold=True)
rect(r,'ledger','INCIDENT ROUTER<br/>Durable fingerprint + dedupe<br/>cooldown + circuit breaker',767,1243,469,180,AMBERB,'#ddc28b',19,bold=True)
rect(r,'repair','REPAIR AI AGENT<br/>Dedicated SKILL + limited MCP<br/>isolated worktree / sandbox<br/>only allowed infrastructure',1354,1235,500,192,PURPLEB,'#b9a3da',18,bold=True)
rect(r,'verdict','DETERMINISTIC VALIDATION<br/>checks + protected-file diff<br/>atomic promote OR rollback',1977,1243,468,180,REDB,'#e2aab4',18,bold=True)
rect(r,'knowledge','LESSONS LEARNED<br/>Sanitized / evidence linked<br/>validated / retractable<br/>top-K shared across workflows',2555,1243,353,180,MINTB,'#83c3aa',16,bold=True)
edge(r,'c1','supervisor','ledger',BLUE,'FAULT',srcside='right',dstside='left');edge(r,'c2','ledger','repair',AMBER,'ELIGIBLE',srcside='right',dstside='left');edge(r,'c3','repair','verdict',PURPLE,srcside='right',dstside='left');edge(r,'c4','verdict','knowledge',MINT,'IF VALID',srcside='right',dstside='left')
text(r,'healthy','Healthy polls remain fully deterministic; repair worker launches independently when Fabro itself is unavailable.',116,1476,1760,50,18,MUTED)
text(r,'repair_block','Forbidden: bypass verification, edit protected safety/release policies, change approved baselines, or fabricate evidence.',1952,1476,945,49,17,RED)

rect(r,'dash','D · HUMAN OBSERVABILITY DASHBOARD (NO HUMAN EXECUTION GATES)<br/>User selects HUMAN · WORKFLOW · TOOL · AI · SUPERVISOR · REPAIR · SECURITY · AUDIT · METRIC · KNOWLEDGE channels, severities and filters.<br/>Capture policy is separate from display filters. Minimal brief status; full evidence retained by reference; secrets + hidden reasoning never logged.',60,1610,2860,163,WHITE,BORDER,20,bold=True)

# 08 deterministic and healing flows
p8,r=newpage('08 Supervisor & autonomous repair','forge-c-0.4-p8',2840,1770,'CONTROL PLANE  |  Deterministic supervisor and autonomous repair','Independent of Fabro · health checks never invoke AI · agent repair starts only for eligible incidents')
panel(r,'core','PERIODIC MODEL-FREE HEALTH LOOP',48,192,2740,335)
rect(r,'poll','systemd supervisor<br/>every 60 s (15–300 s)<br/>NO MODEL',98,292,447,154,BLUEB,'#90b6df',21,bold=True)
rect(r,'probes','Readiness / heartbeat / queue<br/>MCP handshake / storage<br/>CPU-RAM-GPU / dashboard',679,292,572,154,GRAYB,BORDER,20,bold=True)
rect(r,'health','HEALTHY?',1376,286,300,169,AMBERB,'#dfbf7d',20,bold=True,shape='diamond')
rect(r,'log','Health event + metrics<br/>NO tokens · next scheduled poll',1825,292,631,154,MINTB,'#86baa9',20,bold=True)
edge(r,'s1','poll','probes',BLUE,srcside='right',dstside='left');edge(r,'s2','probes','health',BLUE,srcside='right',dstside='left');edge(r,'s3','health','log',MINT,'YES',srcside='right',dstside='left')
edge(r,'s4','log','poll',MINT,'NEXT TICK',dashed=True,srcside='bottom',dstside='bottom',points=[(2220,493),(270,493)])

panel(r,'incident','FAULT HANDLING / SELF-HEALING',48,575,2740,738)
rect(r,'open','Persist INC-ID<br/>fingerprint · severity<br/>correlation / provenance',102,687,427,148,REDB,'#e1a3b1',20,bold=True)
rect(r,'policy','Deterministic eligibility<br/>dedupe · protected paths<br/>retry, cooldown, breaker',627,687,492,148,AMBERB,'#dfbf7d',18,bold=True)
rect(r,'dispatch','Dispatch FABRIC-REPAIR<br/>Fabro child-run if alive<br/>external local worker if down',1211,687,532,148,PURPLEB,'#b7a0d6',19,bold=True)
rect(r,'sandbox','Isolated worktree<br/>minimal incident context<br/>restricted tools / token cap',1840,687,454,148,PURPLEB,'#b7a0d6',19,bold=True)
rect(r,'test','Independent tests<br/>regression / health probes<br/>hashes / policy integrity',2376,678,377,167,BLUEB,'#90b6df',17,bold=True)
for i,a,b in [(1,'open','policy'),(2,'policy','dispatch'),(3,'dispatch','sandbox'),(4,'sandbox','test')]:edge(r,'i'+str(i),a,b,RED if i==1 else BLUE,srcside='right',dstside='left')
edge(r,'hbad','health','open',RED,'NO',srcside='bottom',dstside='top',points=[(1526,558),(320,558)])
rect(r,'pass','PASS<br/>atomic promote + monitor<br/>verified lesson proposal',1150,1018,690,166,MINTB,'#86baa9',21,bold=True)
rect(r,'fail','FAIL / EXHAUSTED<br/>rollback; incident remains open<br/>offline attention + BLOCKED evidence',2037,1018,710,166,REDB,'#e1a3b1',19,bold=True)
edge(r,'testpass','test','pass',MINT,'TESTS PASS',srcside='bottom',dstside='top',points=[(2540,957),(1490,957)])
edge(r,'testfail','test','fail',RED,'FAIL',srcside='bottom',dstside='top')
rect(r,'noneligible','Not eligible / protected mutation attempted:<br/>do not dispatch AI; capture forensic evidence<br/>mark REQUIRES_OFFLINE_ATTENTION',110,1018,842,166,AMBERB,'#dfbf7d',18,bold=True)
edge(r,'ineligible','policy','noneligible',AMBER,'DENIED',srcside='bottom',dstside='top')
text(r,'independent','The Repair Agent proposes patches only. A deterministic controller decides promotion and rollback; never an LLM self-approval.',69,1243,2650,55,19,MUTED)
panel(r,'evidence','HEALTH, AUDIT AND KNOWLEDGE RECORDS',48,1363,2740,291)
rect(r,'incident_ledg','Incident ledger<br/>statuses / attempts / failure cause',108,1452,775,120,GRAYB,BORDER,19,bold=True)
rect(r,'ops_pack','Offline evidence index<br/>repair logs / hashes / unresolved gaps',1028,1452,775,120,GRAYB,BORDER,19,bold=True)
rect(r,'lesson_idx','Approved lesson library<br/>versioned / retractable / shared',1943,1452,780,120,MINTB,'#86baa9',19,bold=True)
edge(r,'l1','pass','lesson_idx',MINT,dashed=True,srcside='bottom',dstside='top');edge(r,'l2','fail','ops_pack',RED,dashed=True,srcside='bottom',dstside='top')

# 09 detailed Skills and MCP
p9,r=newpage('09 SKILL contracts and MCP adapters','forge-c-0.4-p9',2860,1820,'AGENT CONTRACTS  |  One SKILL per AI role, all engineering tools through MCP','Versioned identities · least privilege · missing required adapter blocks the stage, never falls back to unrestricted shell')
panel(r,'roles','20 DECLARED AI SKILLS — ALL WITH SKILL.md',47,186,2760,479)
rect(r,'authors','SWE AUTHORS · 6<br/>swe1-author ... swe6-author<br/>separate stage + token budgets',93,298,590,198,BLUEB,'#99bde5',19,bold=True)
rect(r,'inspectors','INDEPENDENT INSPECTORS · 6<br/>swe1-inspector ... swe6-inspector<br/>read-only baseline, checklist',797,298,590,198,PURPLEB,'#bca4df',19,bold=True)
rect(r,'specialists','ENGINEERING · 4<br/>intake analyst; MISRA auditor<br/>footprint optimizer; safety auditor',1501,298,590,198,GRAYB,BORDER,19,bold=True)
rect(r,'operational','OPERATIONS · 4<br/>release manager; fabric repair<br/>lessons curator; MCP integrator',2203,298,558,198,MINTB,'#8ac4ac',19,bold=True)
rect(r,'contracts','Each skill: mission · authoritative inputs · allowed MCP capabilities · output JSON schema · workproduct evidence · no-go scope · limited tokens/turns.',96,539,2661,68,WHITE,BORDER,18,bold=True)

panel(r,'mcp_panel','MCP ADAPTER CATALOGUE — 9 SERVERS / 34 LOGICAL OPERATIONS',47,708,2760,813)
entries=[('forge-build-mcp','CMake/Ninja, GCC/Clang, ELF size, stack, disassembly',BLUEB),('forge-analysis-mcp','Cppcheck MISRA subset, Clang analyzer, Clang-Tidy, CBMC, Frama-C',PURPLEB),('forge-tests-mcp','Unity/CMock, CTest, LLVM-Cov / MC/DC, gcovr',MINTB),('forge-sim-mcp','Renode, HwSim, deterministic fault injection',GRAYB),('forge-evidence-mcp','frozen baselines, trace gates, inspections, packager',BLUEB),('forge-repo-mcp','scoped Git diff / worktree / candidate commit / SHA',PURPLEB),('forge-observer-mcp','status, incidents and normalized event queries',MINTB),('forge-knowledge-mcp','find / propose / retract validated lessons',GRAYB),('forge-docs-mcp','PlantUML/MkDocs and artifact validation',BLUEB)]
for i,(server,body,fill) in enumerate(entries):
 x=83+(i%3)*905;y=826+(i//3)*196
 rect(r,f'mcp_{i}',f'{server}<br/>{body}',x,y,838,147,fill,BORDER,17,bold=True)
rect(r,'mcp_gate_req','MANDATORY MCP GATE<br/>Discovery + tools/list schema + role tool grants + sandbox allowlists + tool version pinning + timeout + hashed evidence.<br/>Required adapter absent → BLOCKED. Optional tool absent → explicit DISABLED capability (no silent bypass).',107,1437,2650,72,AMBERB,'#deb875',17,bold=True)
rect(r,'critical','NO GENERAL-PURPOSE SHELL MCP OR PRIVILEGED WRITE API · Agent builtin commands must be disabled/contained by sandbox and external enforcement.',85,1567,2690,119,REDB,'#e2aab4',18,bold=True)

# 10 traces, dashboard and tokens
p10,r=newpage('10 Human dashboard &amp; typed traces','forge-c-0.4-p10',2760,1740,'OBSERVABILITY  |  Selective traces, minimal tokens','Human-understandable run status plus independently configurable structured engineering and AI trace categories')
panel(r,'trace1','TYPED EVENTS / CAPTURE POLICY',48,189,2660,654)
rect(r,'sources','EVENT SOURCES<br/>Fabro · tool MCP · AI metadata<br/>supervisor · repair · inspections<br/>lessons · release · token governor',95,314,560,181,BLUEB,'#90b6df',19,bold=True)
rect(r,'collector','NORMALIZE + REDACT<br/>trace IDs + correlation<br/>secrets scrubbed; schema validation<br/>sized previews + raw artifact hash',761,314,645,181,GRAYB,BORDER,19,bold=True)
rect(r,'capture','INDEPENDENT CAPTURE POLICY<br/>Level/channel: OFF/ERROR/WARN<br/>INFO/DEBUG/TRACE<br/>Audit cannot be OFF',1532,314,577,181,AMBERB,'#dfbf7d',19,bold=True)
rect(r,'db','EVENT STORE<br/>SQLite WAL / JSONL hashes<br/>retention + replay + export',2220,314,446,181,MINTB,'#87c1aa',19,bold=True)
edge(r,'e1','sources','collector',BLUE,srcside='right',dstside='left');edge(r,'e2','collector','capture',BLUE,srcside='right',dstside='left');edge(r,'e3','capture','db',MINT,srcside='right',dstside='left')
rect(r,'channels','TRACE CHANNELS<br/>HUMAN | WORKFLOW | TOOL | AI | SUPERVISOR | REPAIR | SECURITY | AUDIT | METRICS | KNOWLEDGE<br/>AI trace = metadata, tool-call status, tokens, optional sanitized prompt excerpts; NEVER hidden chain-of-thought.',94,579,2573,179,WHITE,BORDER,18,bold=True)

panel(r,'trace2','HUMAN DASHBOARD — READ-ONLY, LIVE, FILTERABLE',48,886,2660,431)
rect(r,'ui_filters','VIEW FILTERS<br/>select channels / severity<br/>run / phase / agent / time<br/>search; saved view preferences',93,978,616,213,BLUEB,'#90b6df',19,bold=True)
rect(r,'dashview','DASHBOARD<br/>Run states · SWE phases · findings<br/>MCP health · incidents · repair<br/>tokens/turns · memory/CPU/GPU<br/>package status · incident history',820,966,1008,239,GRAYB,BORDER,19,bold=True)
rect(r,'separation','DISPLAY ≠ CAPTURE<br/>Hiding TOOL or AI traces does not<br/>erase stored security/audit logs.<br/>Credentials always redacted.',1954,978,700,213,AMBERB,'#dfbf7d',19,bold=True)
edge(r,'ui1','db','dashview',MINT,srcside='bottom',dstside='top',dashed=True);edge(r,'ui2','ui_filters','dashview',BLUE,srcside='right',dstside='left')

panel(r,'trace3','TOKEN GOVERNOR — AT AGENT SESSION BOUNDARIES',48,1360,2660,270)
rect(r,'budget','PER-ROLE TOKEN/TURN CAPS<br/>one local model on 8 GB GPU<br/>K=3 approved lessons; context diffs',95,1455,754,131,PURPLEB,'#bca4df',18,bold=True)
rect(r,'compact','COMPACT AI RESPONSE<br/>status / artifacts / issues / next_action<br/>brief INFO; all details are file artifacts',1009,1455,754,131,BLUEB,'#90b6df',18,bold=True)
rect(r,'exhaust','BUDGET EXHAUSTION<br/>explicit failed gate / BLOCKED<br/>never drop mandatory QA evidence',1918,1455,735,131,REDB,'#e2aab4',18,bold=True)
edge(r,'tb1','budget','compact',BLUE,srcside='right',dstside='left');edge(r,'tb2','compact','exhaust',RED,srcside='right',dstside='left')

# 11 approved lessons
p11,r=newpage('11 Validated lessons learned','forge-c-0.4-p11',2560,1640,'CROSS-WORKFLOW KNOWLEDGE  |  Repair lessons are data, not authority','Only fixes that pass objective verification enter the shared lesson index; no policies can be relaxed through a lesson')
panel(r,'know','KNOWLEDGE PROMOTION AND REUSE',48,196,2460,966)
rect(r,'repair_success','Successful autonomous repair<br/>verified patch hash + tests<br/>incident fingerprint + versions',102,313,630,150,MINTB,'#83c3aa',19,bold=True)
rect(r,'draft','Lessons Curator Agent<br/>short root cause / reproduction<br/>candidate mitigation by ref',933,313,629,150,PURPLEB,'#bca4df',19,bold=True)
rect(r,'check','DETERMINISTIC VALIDATOR<br/>evidence / provenance / secrets<br/>duplicate &amp; unsafe content<br/>regression references',1750,296,692,183,AMBERB,'#dfbf7d',18,bold=True)
edge(r,'k1','repair_success','draft',MINT,srcside='right',dstside='left');edge(r,'k2','draft','check',BLUE,srcside='right',dstside='left')
rect(r,'approved','VALIDATED LESSON INDEX<br/>versioned, retrievable, revocable<br/>top K=3 · token <=700',433,647,756,161,MINTB,'#83c3aa',20,bold=True)
rect(r,'quarantine','QUARANTINED / REJECTED<br/>never sent to product AI<br/>kept for audit if retention allows',1605,647,757,161,REDB,'#e2aab4',20,bold=True)
edge(r,'k3','check','approved',MINT,'PASS',srcside='bottom',dstside='top',points=[(2080,552),(812,552)])
edge(r,'k4','check','quarantine',RED,'FAIL',srcside='bottom',dstside='top')
rect(r,'reused','NEXT WORKFLOW<br/>Retrieve scoped by tool/error/phase/version<br/>Inject tiny evidence-backed lesson context',438,905,941,142,BLUEB,'#90b6df',20,bold=True)
rect(r,'revoke','REGRESSION / VERSION CHANGE<br/>Automatically retract invalid lesson<br/>Impact linked downstream workflow runs',1533,905,832,142,AMBERB,'#dfbf7d',19,bold=True)
edge(r,'k5','approved','reused',MINT,srcside='bottom',dstside='top');edge(r,'k6','approved','revoke',AMBER,dashed=True,srcside='bottom',dstside='left')
rect(r,'trust','TRUST BOUNDARY<br/>Shared lessons may suggest known repair actions, but do not supersede hardware manuals, baselined requirements, MISRA limitations, ISO 26262 safety plans, QA policies, source approvals or release gates.',93,1244,2343,225,GRAYB,BORDER,21,bold=True)

src=ET.parse(str(BASE)).getroot()
existing=src.findall('diagram')
assert len(existing)==7
out=ET.Element('mxfile',host='app.diagrams.net',modified=datetime.now(timezone.utc).isoformat(timespec='seconds'),agent='Forge-C v0.4 Spec Kit architecture',version='24.7.17',type='device',pages='11')
# Replace page 01 completely with expanded 0.4 design, retain original 02-07 unchanged, append 08-11.
for item in [p]+[deepcopy(x) for x in existing[1:]]+[p8,p9,p10,p11]:out.append(item)
DEST.parent.mkdir(parents=True,exist_ok=True)
DEST.write_bytes(ET.tostring(out,xml_declaration=True,encoding='utf-8',pretty_print=True))
root=ET.parse(str(DEST)).getroot()
assert len(root.findall('diagram'))==11
for diagram in root.findall('diagram'):
 rootcells=diagram.find('mxGraphModel').find('root').findall('mxCell')
 ids=[c.get('id') for c in rootcells]
 assert len(ids)==len(set(ids)),diagram.get('name')
 for cell in rootcells:
  if cell.get('edge')=='1':assert cell.get('source') in ids and cell.get('target') in ids,(diagram.get('name'),cell.get('id'))
 print(diagram.get('name'),'shapes',sum(c.get('vertex')=='1' for c in rootcells),'edges',sum(c.get('edge')=='1' for c in rootcells))
# No external side-effect: regenerate only the repository diagram.
print('OUT',DEST)
