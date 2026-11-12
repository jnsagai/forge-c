import ast,subprocess,pathlib
W=pathlib.Path("/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028"); A=pathlib.Path("/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/overnight-audit-20261028")
source=subprocess.check_output(['git','-C',str(W),'show','81a2c26:factory/python/forge_factory/brownfield/resume.py'],text=True)
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='contract')
body='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])
(A/'resume_baseline_contract_plugin.py').write_text("from forge_factory.brownfield import resume as R\nPINNED_CONTRACT_SOURCE_REVISION='81a2c26329fa392658cd4289665a264ca8e5d576'\nnamespace=dict(vars(R))\nexec("+repr(body)+",namespace)\nR.contract=namespace['contract']\n")
