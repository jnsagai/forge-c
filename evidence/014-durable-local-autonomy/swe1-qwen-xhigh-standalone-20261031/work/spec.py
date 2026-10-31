"""xhigh arm: llama-server argv from stack.llama_server_spec for the MAX profile (production-local-014 root, own port);
gateway env as in the medium arm (workspace profile), except FORGE_GATEWAY_REASONING = the max profile's
gateway.reasoning block (stack.gateway_reasoning, i.e. copied from the file). Read-only; writes JSON files."""
import json, os, sys
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from forge_factory.lrtx import stack
from forge_factory.lrtx.request_measurement import policy as rm_policy

W = Path(sys.argv[1])
MAX, WSP = "local-rtx-v2-omniverse2-q38-aspice-max-mtp", "local-rtx-v2-omniverse2-q38-delivery-first"
LLAMA, ROOT = 18599, Path("/mnt/data/forge-c/production-local-014")
smax, sws = stack.settings(MAX), stack.settings(WSP)
pmax, pws = smax["profile"], sws["profile"]
ports = dict(smax["ports"]); ports["llama"] = LLAMA
argv, penv, health, models = stack.llama_server_spec(ROOT, pmax, ports, {})
pm = dict(sws["ports"]); pm["llama"] = LLAMA
argv_medium = stack.llama_server_spec(ROOT, pws, pm, {})[0]
json.dump({"argv": argv, "env": penv, "health": health, "models": models, "profile": MAX, "root_used": str(ROOT),
           "profile_default_root": pmax["deployment"]["default_root"],
           "diff_vs_medium_argv_same_port": [[a, b] for a, b in zip(argv_medium, argv) if a != b],
           "len_medium": len(argv_medium), "len_xhigh": len(argv)}, open(W / "llama.spec.json", "w"), indent=1)
adm = pws["admission"]
gw = {"FORGE_GATEWAY_MAX_INFLIGHT": str(adm["max_inflight"]), "FORGE_GATEWAY_MAX_QUEUE": str(adm["max_queue"]),
      "FORGE_GATEWAY_MAX_WAIT_S": str(adm["max_wait_s"]),
      "FORGE_GATEWAY_SAMPLE_S": str((pws.get("measurement") or {}).get("sample_s", 10)),
      "FORGE_GATEWAY_REASONING": stack.gateway_reasoning(pmax),
      "FORGE_GATEWAY_REQUEST_MEASUREMENT": json.dumps(rm_policy(pws))}
if pws.get("gateway", {}).get("measure_unbound_requests") is True:
    gw["FORGE_GATEWAY_MEASURE_UNBOUND"] = "1"
    gw["FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT"] = str(pws["runtime"]["context_limit_tokens"])
gw["FORGE_GATEWAY_REQUEST_TIMEOUT_S"] = str(stack.gateway_timeout(pws))
if "drop_retries" in pws.get("gateway", {}):
    gw["FORGE_GATEWAY_DROP_RETRIES"] = str(pws["gateway"]["drop_retries"])
gw["FORGE_GATEWAY_ROUTES"] = json.dumps({m: f"http://127.0.0.1:{LLAMA}" for m in models})
json.dump(gw, open(W / "gateway.env.json", "w"), indent=1, sort_keys=True)
json.dump({"max_profile_gateway_reasoning": (pmax.get("gateway") or {}).get("reasoning"),
           "workspace_profile_gateway_reasoning": (pws.get("gateway") or {}).get("reasoning"),
           "max_profile_llama_server": pmax["runtime"]["llama_server"],
           "workspace_profile_llama_server": pws["runtime"]["llama_server"]},
          open(W / "reasoning-sources.json", "w"), indent=1, sort_keys=True)
print(json.dumps({"argv": " ".join(argv), "diff": [[a, b] for a, b in zip(argv_medium, argv) if a != b],
                  "lens": [len(argv_medium), len(argv)], "gateway_env": gw}, indent=1))
