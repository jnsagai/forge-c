"""Omission test: llama-server argv per run from stack.llama_server_spec (medium = workspace profile, xhigh = max profile;
production-local-014 root; own ports) and the gateway env of the medium / xhigh arms with only the route port
changed. Read-only; writes work-<run>/llama.spec.json and work-<run>/gateway.env.json."""
import json, os, sys
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from forge_factory.lrtx import stack

D = Path(sys.argv[1])
ROOT = Path("/mnt/data/forge-c/production-local-014")
RUNS = {"medium": ("local-rtx-v2-omniverse2-q38-delivery-first", 18602,
                   "/mnt/data/forge-c/operations/swe1-qwen-20261031/work/gateway.env.json"),
        "xhigh": ("local-rtx-v2-omniverse2-q38-aspice-max-mtp", 18605,
                  "/mnt/data/forge-c/operations/swe1-qwen-xhigh-20261031/work/gateway.env.json")}
for run, (prof_id, port, gwsrc) in RUNS.items():
    s = stack.settings(prof_id)
    ports = dict(s["ports"]); ports["llama"] = port
    argv, penv, health, models = stack.llama_server_spec(ROOT, s["profile"], ports, {})
    W = D / f"work-{run}"; W.mkdir(parents=True, exist_ok=True)
    json.dump({"argv": argv, "env": penv, "health": health, "models": models, "profile": prof_id, "root_used": str(ROOT)},
              open(W / "llama.spec.json", "w"), indent=1)
    gw = json.load(open(gwsrc))
    gw["FORGE_GATEWAY_ROUTES"] = json.dumps({m: f"http://127.0.0.1:{port}" for m in models})
    json.dump(gw, open(W / "gateway.env.json", "w"), indent=1, sort_keys=True)
    print(run, " ".join(argv)); print(run, "FORGE_GATEWAY_REASONING", gw["FORGE_GATEWAY_REASONING"])
