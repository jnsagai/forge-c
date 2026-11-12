
from pathlib import Path
import tarfile,json,hashlib
D=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1');Q=D/'source'
want={r['path']:r['sha256'] for r in json.loads((D/'delivery-first-private-input-manifest.json').read_text())}
with tarfile.open(D/'delivery-first-private-inputs-155553dd.tar') as t:
 for item in t:
  assert item.isfile() and item.name in want and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts
  raw=t.extractfile(item).read();assert hashlib.sha256(raw).hexdigest()==want[item.name]
  dest=Q/item.name;assert dest.resolve().is_relative_to(Q.resolve()) and not dest.is_symlink()
  if dest.exists():assert hashlib.sha256(dest.read_bytes()).hexdigest()==want[item.name]
  else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
print(json.dumps({'verified_private_input_files':len(want),'new_model_calls':0}))

