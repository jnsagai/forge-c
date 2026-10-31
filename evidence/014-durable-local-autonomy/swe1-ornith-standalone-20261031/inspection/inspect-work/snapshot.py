"""Read-only snapshot: path, type, size, mtime_ns, mode and sha256 of every entry under each root."""
import hashlib, json, os, sys
out, roots = sys.argv[1], sys.argv[2:]
snap = {}
for root in roots:
    rows = {}
    for d, dirs, files in os.walk(root, followlinks=False):
        for n in sorted(dirs) + sorted(files):
            p = os.path.join(d, n); st = os.lstat(p); rel = os.path.relpath(p, root)
            if os.path.islink(p):
                rows[rel] = {"type": "link", "target": os.readlink(p), "mtime_ns": st.st_mtime_ns}
            elif os.path.isdir(p):
                rows[rel] = {"type": "dir", "mtime_ns": st.st_mtime_ns, "mode": st.st_mode}
            else:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for b in iter(lambda: f.read(1 << 20), b""):
                        h.update(b)
                rows[rel] = {"type": "file", "size": st.st_size, "mtime_ns": st.st_mtime_ns, "mode": st.st_mode,
                             "sha256": h.hexdigest()}
    rst = os.lstat(root)
    snap[root] = {"root_mtime_ns": rst.st_mtime_ns, "entries": rows}
json.dump(snap, open(out, "w"), sort_keys=True)
print({r: len(v["entries"]) for r, v in snap.items()})
