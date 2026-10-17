"""Independent register-map oracle: parse RM0486 markdown (baselined) and compare every
LL_RCC_<REG>_OFFSET / _<FIELD>_POS / _MSK macro in a header. Does not import forge_factory."""
import re, sys, json
rm, hdr = open(sys.argv[1]).read(), open(sys.argv[2]).read()
secs = {}
for m in re.finditer(r"^#### (14\.10\.\d+) .*?\((RCC_\w+)\)\s*$", rm, re.M):
    secs.setdefault(m.group(2), m.start())
starts = sorted(secs.values()) + [len(rm)]
def body(reg):
    s = secs[reg]; e = min(x for x in starts if x > s); return rm[s:e]
res = []
macros = dict(re.findall(r"#define (LL_RCC_\w+) (0x[0-9A-Fa-f]+|\d+)U", hdr))
for name, val in macros.items():
    m = re.match(r"LL_RCC_([A-Z0-9]+)_(OFFSET|([A-Z0-9]+)_(POS|MSK))$", name)
    if not m: continue
    reg = "RCC_" + m.group(1); v = int(val, 0)
    if reg not in secs: res.append((name, "NO_RM_SECTION", v, None)); continue
    b = body(reg)
    if m.group(2) == "OFFSET":
        o = re.search(r"Address offset:\s*(0x[0-9A-Fa-f]+)", b); rv = int(o.group(1), 16) if o else None
    else:
        f = re.search(r"Bits? (\d+)(?::(\d+))? " + m.group(3) + r"\b", b)
        if not f: res.append((name, "FIELD_NOT_IN_RM", v, None)); continue
        hi, lo = int(f.group(1)), int(f.group(2) or f.group(1))
        acc = None
        rv = lo if m.group(4) == "POS" else ((1 << (hi - lo + 1)) - 1) << lo
    res.append((name, "OK" if rv == v else "MISMATCH", v, rv))
bad = [r for r in res if r[1] != "OK"]
print(json.dumps({"checked": len(res), "mismatch": bad}, indent=1))
sys.exit(1 if bad else 0)
