"""Derive the llama-server argv (stack.llama_server_spec) and the gateway env (as stack._start builds it) for the
workspace profile, with the production-local-014 root and this run's own ports. Read-only; writes two JSON files."""
import json, os, sys
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from forge_factory.lrtx import stack
from forge_factory.lrtx.request_measurement import policy as rm_policy

W, pid = Path(sys.argv[1]), sys.argv[2]
s = stack.settings(pid)
prof = s["profile"]
root = Path("/mnt/data/forge-c/production-local-014")
ports = dict(s["ports"]); ports["llama"] = 18596
argv, penv, health, models = stack.llama_server_spec(root, prof, ports, {})
json.dump({"argv": argv, "env": penv, "health": health, "models": models, "profile_root_env": prof["deployment"]["root_env"],
           "profile_default_root": prof["deployment"]["default_root"], "root_used": str(root), "profile_ports": s["ports"]},
          open(W / "llama.spec.json", "w"), indent=1)
adm = prof["admission"]
gw = {"FORGE_GATEWAY_MAX_INFLIGHT": str(adm["max_inflight"]), "FORGE_GATEWAY_MAX_QUEUE": str(adm["max_queue"]),
      "FORGE_GATEWAY_MAX_WAIT_S": str(adm["max_wait_s"]),
      "FORGE_GATEWAY_SAMPLE_S": str((prof.get("measurement") or {}).get("sample_s", 10)),
      "FORGE_GATEWAY_REASONING": stack.gateway_reasoning(prof),
      "FORGE_GATEWAY_REQUEST_MEASUREMENT": json.dumps(rm_policy(prof))}
if prof.get("gateway", {}).get("measure_unbound_requests") is True:
    gw["FORGE_GATEWAY_MEASURE_UNBOUND"] = "1"
    gw["FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT"] = str(prof["runtime"]["context_limit_tokens"])
gw["FORGE_GATEWAY_REQUEST_TIMEOUT_S"] = str(stack.gateway_timeout(prof))
if "drop_retries" in prof.get("gateway", {}):
    gw["FORGE_GATEWAY_DROP_RETRIES"] = str(prof["gateway"]["drop_retries"])
gw["FORGE_GATEWAY_ROUTES"] = json.dumps({m: f"http://127.0.0.1:{ports['llama']}" for m in models})
json.dump(gw, open(W / "gateway.env.json", "w"), indent=1, sort_keys=True)
print(json.dumps({"argv": " ".join(argv), "gateway_env": gw}, indent=1))
