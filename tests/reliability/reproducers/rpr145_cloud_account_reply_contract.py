"""Independent account reply-contract contrast; fake CLI, no login or network."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from forge_factory.lrtx.cloud_bridge import CodexBackend
SIGNATURE = "account bridge inherits an incompatible status-only worker reply contract"
def main():
    with tempfile.TemporaryDirectory() as td:
        def cli(argv, **kw):
            opts = [argv[i + 1] for i, v in enumerate(argv[:-1]) if v == '-c']
            scoped = any(v.startswith('developer_instructions=') and 'stateless model backend' in v for v in opts)
            if '--output-schema' in argv: answer = {'status': 'SMOKE_OK'}
            elif scoped: answer = {'action': 'tool_calls', 'tool_calls': [{'name': 'echo', 'arguments': {'text': 'hello'}}], 'content': ''}
            else: answer = {'status': 'BLOCKED', 'artifacts': [], 'issues': ['no MCP tools'], 'next_action': 'halt'}
            Path(argv[argv.index('-o') + 1]).write_text(json.dumps(answer))
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        be = CodexBackend(td, run=cli); cfg = {'model': 'gpt-6.1-terra'}
        control = be.answer({'model': cfg['model'], 'messages': [], 'response_format': {'type': 'json_schema', 'json_schema': {'schema': {'type': 'object', 'additionalProperties': False, 'required': ['status'], 'properties': {'status': {'type': 'string'}}}}}}, cfg)
        assert json.loads(control['text']) == {'status': 'SMOKE_OK'}, 'plain structured answer control failed'
        body = {'model': cfg['model'], 'messages': [{'role': 'user', 'content': 'Call echo with text hello'}], 'tool_choice': 'required', 'tools': [{'type': 'function', 'function': {'name': 'echo', 'parameters': {'type': 'object', 'additionalProperties': False, 'required': ['text'], 'properties': {'text': {'type': 'string'}}}}}]}
        try: r = be.answer(body, cfg)
        except RuntimeError as exc:
            if 'ENVELOPE_INVALID:$' in str(exc): print('SYMPTOM_PRESENT:' + SIGNATURE); return 1
            raise
        assert r['finish'] == 'tool_calls' and r['tool_calls'][0]['function']['name'] == 'echo'
        print('SYMPTOM_ABSENT'); return 0
if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as exc: print('REPRODUCER_ERROR:' + type(exc).__name__ + ':' + str(exc)[:160]); raise SystemExit(2)
