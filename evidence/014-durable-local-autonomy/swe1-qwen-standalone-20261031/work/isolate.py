"""Isolation edits in a SCRATCH copy only: rebind binding.json + workflow.toml workspace paths to the copy and move
durable-binding.json out of the copy. Records every change. Usage: isolate.py <copy_of> <copy> <isolated_dir> <out.json>
<old_path> [<old_path> ...]"""
import hashlib, json, os, shutil, sys

copy_of, copy, iso, out, olds = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
assert os.path.realpath(copy).startswith("/mnt/data/forge-c/operations/swe1-qwen-20261031/"), copy
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
edits = []
for rel in (".forge-run/binding.json", ".forge-run/workflow.toml"):
    p = os.path.join(copy, rel)
    before = sha(p); t = open(p).read(); n = 0
    for o in olds:
        n += t.count(o); t = t.replace(o, copy)
    if n:
        open(p, "w").write(t)
    edits.append({"file": rel, "op": "replace_path", "old": olds, "new": copy, "occurrences": n,
                  "sha256_before": before, "sha256_after": sha(p)})
db = os.path.join(copy, ".forge-run/durable-binding.json")
if os.path.isfile(db):
    os.makedirs(iso, exist_ok=True)
    keys = sorted(json.load(open(db)))
    h = sha(db); dst = os.path.join(iso, "durable-binding.json"); shutil.move(db, dst)
    edits.append({"file": ".forge-run/durable-binding.json", "op": "moved_out_of_copy", "to": dst, "sha256": h,
                  "keys": keys, "reason": "binds the copy to the trial-06 AFO product job; structured.call would send "
                  "it as forge_execution when RECOVERY_WORKSPACE is set, and the gateway would route the call through "
                  "the AFO durable reservation of a job that does not exist in the scratch state"})
else:
    edits.append({"file": ".forge-run/durable-binding.json", "op": "absent_in_copy"})
left = []
for d, _, fs in os.walk(copy):
    for f in fs:
        p = os.path.join(d, f); rel = os.path.relpath(p, copy)
        if rel in (".forge-run/binding.json", ".forge-run/workflow.toml") or os.path.islink(p):
            continue
        try:
            t = open(p, "rb").read().decode("utf-8", "replace")
        except OSError:
            continue
        for o in olds:
            if o in t:
                left.append({"file": rel, "path": o, "count": t.count(o)})
json.dump({"copy_of": copy_of, "copy": copy, "edits": edits, "left_unchanged": left}, open(out, "w"), indent=1)
print(json.dumps({"edits": [(e["file"], e["op"], e.get("occurrences")) for e in edits], "left_unchanged": len(left)}))
