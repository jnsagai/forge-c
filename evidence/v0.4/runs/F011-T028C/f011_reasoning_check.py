"""F011-T028C: does a candidate answer a schema-constrained request with reasoning_effort="none", the value the
local-rtx gateway forces on every request (llm_gateway.py)? Direct to the profile Ollama (loopback, in the profile
namespace); no content is stored here, only lengths, finish reasons and token counts."""
import json
import sys
import urllib.error
import urllib.request

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "claims"],
          "properties": {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                         "claims": {"type": "array", "items": {"type": "string"}}}}
MSG = [{"role": "user", "content": "Is 4096 a power of two? verdict PASS if yes, FAIL if no; claims empty."}]
rows = []
for model in sys.argv[1:]:
    for eff in ("none", "low", None):
        body = {"model": model, "messages": MSG, "stream": False, "max_tokens": 2048, "temperature": 0,
                "response_format": {"type": "json_schema", "json_schema": {"name": "p", "strict": True, "schema": SCHEMA}}}
        if eff:
            body["reasoning_effort"] = eff
        req = urllib.request.Request("http://127.0.0.1:11455/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=900).read())
        except urllib.error.HTTPError as e:
            rows.append({"model": model, "reasoning_effort": eff, "http": e.code, "error": e.read()[:160].decode()})
            continue
        m = r["choices"][0]["message"]
        try:
            valid = json.loads(m.get("content") or "")["verdict"] in ("PASS", "FAIL")
        except (ValueError, KeyError, TypeError):
            valid = False
        rows.append({"model": model, "reasoning_effort": eff, "content_chars": len(m.get("content") or ""),
                     "valid_json": valid, "reasoning_chars": len(m.get("reasoning") or ""),
                     "finish": r["choices"][0]["finish_reason"], "completion_tokens": r["usage"]["completion_tokens"]})
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11455" + "/api/generate",
                                                  data=json.dumps({"model": model, "keep_alive": 0}).encode())).read()
for x in rows:
    print(json.dumps(x))
none_ok = {x["model"]: x.get("valid_json", False) for x in rows if x["reasoning_effort"] == "none"}
print(json.dumps({"answers_with_reasoning_off": none_ok}))
