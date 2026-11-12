"""Read-only size census of workspaces with recorded Codex author provenance."""
from pathlib import Path
from datetime import datetime, timezone
import argparse,hashlib,json,math

def measure(root):
    rows=[];workspaces=[];warnings=[]
    for directory in sorted(Path(root).iterdir()):
        ws=directory/'workspace';profile=ws/'.forge-run/model-profile.json';manifest=ws/'.forge-run/manifest.json'
        if not profile.is_file() or not manifest.is_file():continue
        try:p=json.loads(profile.read_text());m=json.loads(manifest.read_text())
        except (ValueError,OSError):continue
        author=p.get('acp_authors')
        if not isinstance(author,dict) or not author.get('codex'):continue
        inspector=p.get('acp_inspectors') or {}
        delivered={v['to'] for v in (m.get('delivery') or {}).get('files',[]) if isinstance(v,dict) and 'to' in v}
        dependencies={v['to'] for v in (m.get('delivery') or {}).get('dependencies',[]) if isinstance(v,dict) and 'to' in v}
        workspaces.append({'work_order':directory.name,'peripheral':m.get('peripheral'),'code_mode':m.get('code_mode'),
           'authors':author.get('model'),'inspectors':inspector.get('model'),'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()})
        software=ws/'software'
        if not software.is_dir():continue
        for f in sorted(software.rglob('*')):
            if not f.is_file() or f.is_symlink() or f.suffix.lower() not in ('.c','.h','.cc','.cpp','.hpp','.s'):continue
            rel=f.relative_to(ws).as_posix()
            if any(v in f.relative_to(software).parts for v in ('vendor','build','.git','third_party')):continue
            before=f.stat();raw=f.read_bytes();after=f.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                warnings.append({'file':str(f),'reason':'CHANGED_DURING_READ'});continue
            try:text=raw.decode('utf-8')
            except UnicodeDecodeError:
                warnings.append({'file':str(f),'reason':'NOT_UTF8_SOURCE'});continue
            kind='test' if rel.startswith('software/tests/') else 'driver'
            origin='delivered_dependency' if rel in dependencies else 'delivered_driver' if rel in delivered else 'workflow_output'
            rows.append({'work_order':directory.name,'peripheral':m.get('peripheral'),'code_mode':m.get('code_mode'),
               'path':rel,'kind':kind,'origin':origin,'bytes':len(raw),'characters':len(text),'lines':len(text.splitlines()),
               'sha256':hashlib.sha256(raw).hexdigest(),'authors':author.get('model'),'inspectors':inspector.get('model')})
    summaries={}
    for kind,group in [('driver',[r for r in rows if r['kind']=='driver']),('workflow_output_driver',[r for r in rows if r['kind']=='driver' and r['origin']=='workflow_output']),('delivered_driver',[r for r in rows if r['kind']=='driver' and r['origin']=='delivered_driver']),('test',[r for r in rows if r['kind']=='test'])]:
        unique={r['sha256']:r for r in group};values=sorted(r['bytes'] for r in unique.values())
        summaries[kind]={'file_observations':len(group),'distinct_contents':len(unique),
            'max_bytes':max(values) if values else None,'p95_bytes':values[max(0,math.ceil(.95*len(values))-1)] if values else None,
            'largest':sorted(unique.values(),key=lambda r:r['bytes'],reverse=True)[:10]}
    return {'schema':'forge-c/codex-driver-source-sizes/1','at':datetime.now(timezone.utc).isoformat(),
       'root':str(root),'scope':'CURRENT_CODEX_AUTHOR_WORKSPACE_BYTES_NOT_PRODUCT_ACCEPTANCE',
       'excluded':'inputs/vendor, vendor/build/third_party trees, symlinks and non-source files',
       'workspaces':workspaces,'summaries':summaries,'files':rows,'warnings':warnings,'source_modified':False,'model_requests':0}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    report=measure(a.state_root);a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'workspaces':len(report['workspaces']),'files':len(report['files']),'summaries':{k:{n:v for n,v in s.items() if n!='largest'} for k,s in report['summaries'].items()}},indent=2))
