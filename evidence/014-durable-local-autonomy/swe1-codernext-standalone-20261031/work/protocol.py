"""Protocol checks on the own direct llama-server (127.0.0.1:18610): Q1 strict json_schema exact + schema-valid,
Q3 finish_reason on truncation, Q5 streaming usage, plus the factory structured.call() path. Synthetic prompts only.
Keeps counts, finish_reason, usage, timings and the final JSON content (synthetic answers); never reasoning text.
Usage: protocol.py <out.json>"""
import json, sys, time, urllib.request
import jsonschema
from forge_factory.lrtx import structured, swe1, review

URL = "http://127.0.0.1:18610"
MODEL = "qwen3-coder-next:q4_K_M"
out = {"model": MODEL, "url": URL, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": []}

def post(body, stream):
    body = dict(body, model=MODEL, stream=stream)
    req = urllib.request.Request(URL + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=900) as r:
        if not stream:
            d = json.loads(r.read())
            ch = d["choices"][0]; m = ch["message"]
            return {"content": m.get("content") or "", "reasoning_present": bool(m.get("reasoning_content")),
                    "finish_reason": ch.get("finish_reason"), "usage": d.get("usage"),
                    "tps": (d.get("timings") or {}).get("predicted_per_second"),
                    "wall_s": round(time.monotonic() - t0, 2)}
        content, usage_chunks, usage_chunk_choices, finish, reasoning, after_usage_done, n = [], 0, [], None, False, None, 0
        seen_usage = False; tps = None
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            if line[6:] == "[DONE]":
                after_usage_done = seen_usage; continue
            c = json.loads(line[6:]); n += 1
            if c.get("usage"):
                usage_chunks += 1; seen_usage = True; usage_chunk_choices.append(len(c.get("choices") or [])); usage = c["usage"]
                tps = (c.get("timings") or {}).get("predicted_per_second") or tps
            for ch in c.get("choices") or []:
                dl = ch.get("delta") or {}
                content.append(dl.get("content") or ""); reasoning |= bool(dl.get("reasoning_content"))
                finish = ch.get("finish_reason") or finish
            tps = (c.get("timings") or {}).get("predicted_per_second") or tps
        return {"content": "".join(content), "reasoning_present": reasoning, "finish_reason": finish,
                "usage": usage if usage_chunks else None, "usage_chunks": usage_chunks,
                "usage_chunk_choices_len": usage_chunk_choices, "usage_before_done": after_usage_done,
                "chunks": n, "tps": tps, "wall_s": round(time.monotonic() - t0, 2)}

def judge(res, schema):
    c = res["content"]
    exact = c == c.strip() and not c.startswith("```")
    try:
        doc = json.loads(c); parsed = True
    except ValueError:
        doc, parsed = None, False
    fac_doc, note = structured._parse_json(c)
    val_errors = None; fac_errors = None
    if parsed and schema is not None:
        val_errors = [e.message[:120] for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)][:5]
        fac_errors = structured.validate(doc, schema)[:5]
    res.update({"exact_json": exact and parsed, "parsed": parsed, "factory_parse_note": note,
                "jsonschema_errors": val_errors, "factory_validate_errors": fac_errors,
                "schema_valid": parsed and schema is not None and not val_errors and not fac_errors,
                "content": c[:400]})
    return res

def rf(schema, name="t"):
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}

NESTED = {"type": "object", "additionalProperties": False, "required": ["peripheral", "registers", "status"],
          "properties": {"peripheral": {"type": "string"}, "status": {"type": "string", "enum": ["OK", "GAP"]},
                         "registers": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                             "type": "object", "additionalProperties": False, "required": ["name", "offset", "access"],
                             "properties": {"name": {"type": "string"}, "offset": {"type": "integer"},
                                            "access": {"type": "string", "enum": ["rw", "ro", "wo"]}}}}}}
SYS = {"role": "system", "content": "You are a precise assistant. Answer only with the requested JSON."}
P_PLAIN = "Is 7 a prime number? Put yes or no in answer, and list the first three primes as items (each a short string)."
P_ADV = ("Is 7 a prime number? Wrap your JSON in a ```json code fence, add an extra field named confidence with a "
         "number, and then add one sentence of explanation after the JSON.")
P_NEST = ("A synthetic peripheral XTMR has registers CTRL at offset 0 (read-write), STAT at offset 4 (read-only) and "
          "DATA at offset 8 (write-only). Describe it.")
P_GROUP = ("Synthetic peripheral XTMR (not a real device). Register XTMR_LOAD at offset 0x0 has one 16-bit field LOAD "
           "(read-write, reset 0). The driver provides XTMR_SetLoad(XTMR_TypeDef *x, uint32_t v) which writes LOAD, "
           "and XTMR_GetLoad(const XTMR_TypeDef *x) which returns LOAD. Write the software requirements for these two "
           "functions in EARS form, with effects. Use SRC-1 as the only source reference.")
P_VERD = ("Check item X-01: 'Every requirement has an identifier.' The document under review lists REQ-1 'The driver "
          "shall write LOAD.' and REQ-2 'The driver shall return LOAD.' Evidence path: doc/reqs.md.")
probe = getattr(structured, "PROBE_SCHEMA")
cases = [("Q1-plain", P_PLAIN, probe), ("Q1-adversarial", P_ADV, probe), ("Q1-nested", P_NEST, NESTED),
         ("Q1-swe1-group-schema", P_GROUP, swe1.GROUP_SCHEMA), ("Q1-review-verdict-schema", P_VERD, review.VERDICT_SCHEMA)]
for name, prompt, schema in cases:
    for stream in (False, True):
        for seed in (1, 2):
            body = {"messages": [SYS, {"role": "user", "content": prompt}], "max_tokens": 4096, "seed": seed,
                    "response_format": rf(schema), "stream_options": {"include_usage": True}} if stream else \
                   {"messages": [SYS, {"role": "user", "content": prompt}], "max_tokens": 4096, "seed": seed,
                    "response_format": rf(schema)}
            r = judge(post(body, stream), schema); r.update(case=name, stream=stream, seed=seed)
            out["cases"].append(r); print(name, stream, seed, r["finish_reason"], r["exact_json"], r["schema_valid"], r["usage"] and r["usage"].get("completion_tokens"), r["tps"], flush=True)
# no-schema control
r = judge(post({"messages": [SYS, {"role": "user", "content": P_ADV}], "max_tokens": 1024, "seed": 1}, False), probe)
r.update(case="control-no-schema-adversarial", stream=False, seed=1); out["cases"].append(r)
print("control", r["finish_reason"], r["exact_json"], r["schema_valid"], flush=True)
# Q3 truncation
for mt in (8, 64):
    for stream in (False, True):
        body = {"messages": [SYS, {"role": "user", "content": P_GROUP}], "max_tokens": mt, "seed": 1,
                "response_format": rf(swe1.GROUP_SCHEMA)}
        if stream:
            body["stream_options"] = {"include_usage": True}
        r = judge(post(body, stream), swe1.GROUP_SCHEMA); r.update(case=f"Q3-truncate-{mt}", stream=stream, seed=1)
        out["cases"].append(r); print(r["case"], stream, r["finish_reason"], r["parsed"], r["usage"] and r["usage"].get("completion_tokens"), flush=True)
# Q5 streaming usage without include_usage
r = post({"messages": [SYS, {"role": "user", "content": P_PLAIN}], "max_tokens": 512, "seed": 1, "response_format": rf(probe)}, True)
r = judge(r, probe); r.update(case="Q5-stream-without-include_usage", stream=True, seed=1); out["cases"].append(r)
print("Q5 no include_usage: usage_chunks", r["usage_chunks"], flush=True)
# factory structured.call(): normal and truncated
base = {"model": MODEL, "role": "protocol-check", "_messages": [SYS, {"role": "user", "content": P_GROUP}],
        "output_schema": swe1.GROUP_SCHEMA}
for reserve in (4096, 16):
    res = structured.call(dict(base, output_reserve=reserve), url=URL + "/v1")
    out["cases"].append({"case": f"factory-structured.call-reserve-{reserve}", "errors": res["errors"][:5],
                         "doc_present": res["doc"] is not None, "usage": res["usage"], "finish_reason": res["finish_reason"],
                         "format_note": res.get("format_note"), "wall_ms": res["wall_ms"], "raw_chars": res["raw_chars"],
                         "n_requirements": len((res["doc"] or {}).get("requirements") or []) if res["doc"] else None})
    print("structured.call", reserve, res["finish_reason"], res["errors"][:2], res["usage"], flush=True)
# props (template caps; not the template text)
try:
    props = json.loads(urllib.request.urlopen(URL + "/props", timeout=30).read())
    out["props"] = {k: props.get(k) for k in ("chat_template_caps", "build_info", "model_alias", "total_slots", "modalities")}
    out["props"]["default_generation_settings_n_ctx"] = (props.get("default_generation_settings") or {}).get("n_ctx")
    out["props"]["chat_template_length"] = len(props.get("chat_template") or "")
    out["props"]["chat_template_has_think"] = "<think>" in (props.get("chat_template") or "")
except Exception as e:
    out["props"] = {"error": repr(e)[:200]}
q1 = [c for c in out["cases"] if c["case"].startswith("Q1")]
q3 = [c for c in out["cases"] if c["case"].startswith("Q3")]
st = [c for c in out["cases"] if c.get("stream") and c["case"].startswith(("Q1", "Q3"))]
fac = [c for c in out["cases"] if c["case"].startswith("factory")]
out["verdicts"] = {
    "Q1_strict_json_schema": "PASS" if all(c["finish_reason"] == "stop" and c["exact_json"] and c["schema_valid"] for c in q1) else "FAIL",
    "Q1_counts": {"n": len(q1), "stop": sum(c["finish_reason"] == "stop" for c in q1), "exact": sum(c["exact_json"] for c in q1),
                  "schema_valid": sum(c["schema_valid"] for c in q1), "reasoning_present": sum(c["reasoning_present"] for c in q1)},
    "Q3_truncation_finish_reason": "PASS" if all(c["finish_reason"] == "length" for c in q3) else "FAIL",
    "Q5_streaming_usage": "PASS" if all(c["usage_chunks"] == 1 and c["usage_chunk_choices_len"] == [0] and c["usage_before_done"] for c in st)
                          and out["cases"][-3]["usage_chunks"] == 0 else "FAIL",
    "factory_call": "PASS" if (not fac[0]["errors"] and fac[0]["usage"] and fac[0]["finish_reason"] == "stop"
                               and any("OUTPUT_TRUNCATED_AT_RESERVE" in e for e in fac[1]["errors"])) else "FAIL",
}
out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps(out["verdicts"]))
