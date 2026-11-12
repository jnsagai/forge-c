"""Independent kernel observation: nested candidate isolation must expose pinned ST inputs read-only.

The explicit-readable control proves that the dependency and nested backend work.
No vendor contents, secrets, inference or production state are copied to output.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

SIGNATURE = "scoped CRE verifier cannot read its pinned ST dependencies"
PROBE = '''import hashlib,json,os,pathlib,sys
header,state=map(pathlib.Path,sys.argv[1:])
r={"sha256":None,"writable":False,"state_visible":state.exists()}
try:r["sha256"]=hashlib.sha256(header.read_bytes()).hexdigest()
except FileNotFoundError:pass
try:
 fd=os.open(header,os.O_WRONLY);os.close(fd);r["writable"]=True
except OSError:pass
print(json.dumps(r))
'''


def main():
    from forge_factory.common import REPO_ROOT, data_root
    from forge_factory.reliability import isolation

    os.environ[isolation.MODE_ENV] = "bubblewrap"
    if isolation.backend() != "bubblewrap":
        raise RuntimeError("NESTED_BUBBLEWRAP_UNAVAILABLE")
    inputs = data_root() / "inputs"
    header = inputs / "st/stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_crc.h"
    expected = {"sha256": hashlib.sha256(header.read_bytes()).hexdigest(), "writable": False,
                "state_visible": False}
    env = {"PATH": os.environ["PATH"], "FORGE_REPO_ROOT": str(REPO_ROOT),
           "FORGE_DATA_ROOT": str(data_root()), "PYTHONPATH": str(REPO_ROOT / "factory/python")}
    with tempfile.TemporaryDirectory(prefix="rpr156-") as d:
        scratch = Path(d)

        def observe(readable):
            p = isolation.execute("verifier", [sys.executable, "-c", PROBE, str(header),
                                                str(data_root() / "state")], cwd=scratch, env=env,
                                  writable=[scratch], readable=readable, timeout=20)
            if p.returncode:
                raise RuntimeError("NESTED_NAMESPACE_PROBE_FAILED")
            return json.loads(p.stdout)

        if observe([inputs, inputs.resolve()]) != expected:
            raise RuntimeError("EXPLICIT_READONLY_CONTROL_FAILED")
        observed = observe([])
        if observed == expected:
            print("SYMPTOM_ABSENT")
        elif observed == {**expected, "sha256": None}:
            print("SYMPTOM_PRESENT:" + SIGNATURE)
            return 1
        else:
            raise RuntimeError("UNEXPECTED_CONFINEMENT_RESULT")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("REPRODUCER_ERROR:" + type(exc).__name__ + ":" + str(exc)[:160])
        raise SystemExit(2)
