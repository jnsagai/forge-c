"""Run the mutate.py mutant set against the independent shim-based oracle test."""
import sys, json, shutil, subprocess, tempfile, pathlib, importlib.util
sys.argv = [sys.argv[0]] + sys.argv[1:]
sw, target, oracle_dir, test = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3]), sys.argv[4]
spec = importlib.util.spec_from_file_location("m", pathlib.Path(__file__).with_name("mutate.py"))
src = (sw / target).read_text()
full = pathlib.Path(__file__).with_name("mutate.py").read_text()
code = "import re\n" + full[full.index("OPS = ["):full.index("src = (sw / target)")]
ns = {}; exec(code, ns)
res = []
for name, line, mtext in ns["mutants"](src):
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td); shutil.copytree(sw, t / "sw"); (t / "sw" / target).write_text(mtext)
        if target.startswith("ll/"): shutil.copy(t / "sw" / target, t / "sw" / "include" / pathlib.Path(target).name)
        inc = ["-I", str(t / "sw/include"), "-I", str(t / "sw/ll"), "-I", str(oracle_dir), "-include", str(oracle_dir / "shim.h")]
        objs = []
        ok = True
        for c in [p for p in (t / "sw/src").glob("*.c") if not p.name.endswith("ll_rcc.c")] + [pathlib.Path(test)]:
            o = t / (c.stem + ".o"); r = subprocess.run(["gcc", "-std=c99", "-O0", "-w", *inc, "-c", str(c), "-o", str(o)], capture_output=True); ok &= r.returncode == 0; objs.append(str(o))
        if not ok or subprocess.run(["gcc", *objs, "-o", str(t / "x")], capture_output=True).returncode:
            res.append({"op": name, "line": line, "r": "STILLBORN"}); continue
        try:
            r = subprocess.run([str(t / "x")], capture_output=True, text=True, timeout=5); v = "KILLED" if (r.returncode or " FAIL" in r.stdout) else "SURVIVED"
        except subprocess.TimeoutExpired: v = "KILLED"
        res.append({"op": name, "line": line, "r": v})
print(json.dumps(res))
