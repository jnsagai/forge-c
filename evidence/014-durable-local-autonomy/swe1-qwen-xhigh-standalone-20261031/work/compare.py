import json, sys
a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
diff = {}
for root in a:
    ea, eb = a[root]["entries"], b[root]["entries"]
    d = {"added": sorted(set(eb) - set(ea)), "removed": sorted(set(ea) - set(eb)),
         "changed": {k: {"before": ea[k], "after": eb[k]} for k in sorted(set(ea) & set(eb)) if ea[k] != eb[k]},
         "root_mtime_changed": a[root]["root_mtime_ns"] != b[root]["root_mtime_ns"], "entries": len(ea)}
    d["identical"] = not (d["added"] or d["removed"] or d["changed"] or d["root_mtime_changed"])
    diff[root] = d
json.dump(diff, open(sys.argv[3], "w"), indent=1, sort_keys=True)
print(json.dumps({r: {"identical": v["identical"], "entries": v["entries"], "added": len(v["added"]), "removed": len(v["removed"]), "changed": list(v["changed"])[:10]} for r, v in diff.items()}, indent=1))
