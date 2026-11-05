"""Read-only GGUF metadata reader (KV section only). Prints scalar keys, array lengths, and chat-template facts
(not its text). Usage: ggufmeta.py <blob> <out.json> [<template_out_path>]"""
import json, struct, sys
T = {0:'<B',1:'<b',2:'<H',3:'<h',4:'<I',5:'<i',6:'<f',7:'<?',10:'<Q',11:'<q',12:'<d'}
f = open(sys.argv[1], 'rb')
def rd(fmt): s = struct.calcsize(fmt); return struct.unpack(fmt, f.read(s))[0]
def rstr(): n = rd('<Q'); return f.read(n).decode('utf-8', 'replace')
def val(t):
    if t in T: return rd(T[t])
    if t == 8: return rstr()
    if t == 9:
        et = rd('<I'); n = rd('<Q')
        if et == 8:
            for _ in range(n): rstr()
        else:
            f.seek(struct.calcsize(T[et]) * n, 1)
        return {'array_type': et, 'len': n}
    raise ValueError(t)
assert f.read(4) == b'GGUF'
ver = rd('<I'); nt = rd('<Q'); nkv = rd('<Q')
kv = {}
for _ in range(nkv):
    k = rstr(); t = rd('<I'); kv[k] = val(t)
tpl = kv.get('tokenizer.chat_template', '')
if len(sys.argv) > 3:
    open(sys.argv[3], 'w').write(tpl)
out = {'gguf_version': ver, 'n_tensors': nt, 'n_kv': nkv,
       'kv': {k: (v if not isinstance(v, str) or len(v) < 200 else f'<str len {len(v)}>') for k, v in kv.items()},
       'chat_template_facts': {'present': bool(tpl), 'length': len(tpl),
           'mentions_think_tag': '<think>' in tpl, 'mentions_enable_thinking': 'enable_thinking' in tpl,
           'mentions_reasoning_content': 'reasoning_content' in tpl, 'mentions_tool_call': 'tool_call' in tpl,
           'mentions_reasoning_effort': 'reasoning_effort' in tpl}}
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print(json.dumps(out['chat_template_facts']))
print(json.dumps({k: v for k, v in out['kv'].items() if not k.startswith('tokenizer.ggml')}, indent=0)[:4000])
