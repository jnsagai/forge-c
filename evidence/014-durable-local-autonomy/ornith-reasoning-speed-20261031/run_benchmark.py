"""Owner-requested standalone Ornith speed study; never activates factory jobs.

Numeric timings and final answers only. Reasoning content is discarded after
counting and is never written. Generated C executes on Omniverse only.
"""
import hashlib
import json
import os
import signal
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/mnt/data/forge-c/benchmarks/ornith-speed-20261031')
BASE = 'http://127.0.0.1:18581'
INSTANCE = json.loads((ROOT / 'server-instance.json').read_text())
START = time.monotonic()
DEADLINE = START + 1800
SOURCE = Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/source')
sys.path.insert(0, str(SOURCE / 'factory/python'))
from forge_factory.mcp.sdk import run_argv  # noqa: E402

CONFIGS = [('off', False, 0), ('budget512', True, 512),
           ('budget2048', True, 2048), ('default_on', True, -1)]
COMMON = {'model': 'ornith-1.5-35b-a3b-q8', 'temperature': 0.6,
          'top_p': 0.95, 'top_k': 20, 'min_p': 0.0, 'repeat_penalty': 1.0,
          'cache_prompt': False, 'max_tokens': 8192, 'stream': True,
          'stream_options': {'include_usage': True}}
CODE_PROMPT = '''Implement two portable C11 functions. Output only C source; a
single enclosing markdown C fence is allowed. Include stdint.h and stddef.h.
Do not provide main or any other external functions.

uint32_t replace_field(uint32_t original, unsigned lsb, unsigned width, uint32_t replacement);
For width 1..32, lsb 0..31 and lsb+width<=32, replace exactly those bits with the
low width bits of replacement, preserving all other bits. For every invalid
width or lsb return original unchanged. Do not shift a 32-bit value by 32 or more.

int poll_match(uint32_t (*read_word)(void *), void *ctx, uint32_t mask,
               uint32_t expected, unsigned max_reads);
A null callback returns -1 without a read. Otherwise make at most max_reads
callback invocations, stopping at the first word whose masked value equals the
masked expected value. Return 1 on match, 0 if the budget is exhausted. A zero
budget does not invoke the callback. Each iteration reads exactly once. ctx may
be null and is forwarded unchanged. No I/O, allocation, globals or hardware setup.
'''
NUMERIC_PROMPT = '''Return only one JSON object with decimal integer keys x,
updated and extracted. Compute the least nonnegative x with x%97=13, x%89=42,
x%83=6. For unsigned 32-bit reg=0xA55A5AA5, mask=0x00FF0000 and bits=0x005C0000,
updated=(reg & ~mask) | (bits & mask), reduced to 32 bits. extracted is bits
23:16 of updated. No explanation and no markdown.
'''
REVIEW_PROMPT = '''Review the following independent portable C11 functions against
their contracts. Return only JSON {"defective":["F1",...]} with exactly the IDs
that violate the stated contract, in sorted order. Do not list valid functions.
uint32_t is exactly 32 bits; all nonnull pointers are accessible; no concurrent
writers or interrupts. Do not infer extra requirements.
F1: width is 1..32; return its low-bit mask.
uint32_t f1(unsigned width) { return (1u << width) - 1u; }
F2: width is 1..32; return its low-bit mask.
uint32_t f2(unsigned width) { return width == 32 ? UINT32_MAX : ((UINT32_C(1) << width) - UINT32_C(1)); }
F3: mask and bits are arbitrary uint32_t; replace only masked bits and preserve
all other bits, taking replacement bits from bits.
void f3(uint32_t *r, uint32_t mask, uint32_t bits) { *r = (*r & ~mask) | bits; }
F4: width is 1..32, lsb is 0..31, lsb+width<=32; return that unsigned field.
uint32_t f4(uint32_t r, unsigned lsb, unsigned width) { return (r >> lsb) & (width == 32 ? UINT32_MAX : ((UINT32_C(1) << width) - UINT32_C(1))); }
F5: max_reads is 0..1000; return true if the accessible volatile register is 1
within at most max_reads reads, otherwise false. Zero budget performs no read.
int f5(volatile uint32_t *r, unsigned max_reads) { for (unsigned i=0; i<=max_reads; ++i) { if (*r == 1u) return 1; } return 0; }
F6: same replacement contract as F3; r is an accessible volatile pointer.
void f6(volatile uint32_t *r, uint32_t mask, uint32_t bits) { uint32_t old=*r; *r=(old & ~mask) | (bits & mask); }
'''
CASES = [('numeric', NUMERIC_PROMPT), ('author_c', CODE_PROMPT), ('review_c', REVIEW_PROMPT)]
HARNESS = r'''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <limits.h>
#include "candidate.c"
static unsigned checks=0U, failures=0U;
static void verify(int value) { ++checks; if (!value) ++failures; }
struct sequence { unsigned reads; unsigned match_at; uint32_t mask; uint32_t expected; };
static uint32_t read_word(void *arg) {
 struct sequence *s=(struct sequence *)arg;
 unsigned n=s->reads++;
 return n==s->match_at ? s->expected : (s->expected ^ s->mask);
}
static unsigned null_reads=0U;
static uint32_t read_null(void *arg) { verify(arg==NULL); ++null_reads; return 0U; }
int main(void) {
 const uint32_t values[]={0U,UINT32_MAX,0xA55A5AA5U,0x12345678U,0x80000000U};
 for(unsigned lsb=0U;lsb<=34U;++lsb) for(unsigned width=0U;width<=34U;++width)
 for(unsigned v=0U;v<5U;++v) for(unsigned r=0U;r<5U;++r) {
  uint32_t expected=values[v];
  if(width>=1U && width<=32U && lsb<=31U && width<=32U-lsb) {
   uint64_t mask=((UINT64_C(1)<<width)-UINT64_C(1))<<lsb;
   expected=(uint32_t)(((uint64_t)values[v]&~mask)|(((uint64_t)values[r]<<lsb)&mask));
  }
  verify(replace_field(values[v],lsb,width,values[r])==expected);
 }
 const unsigned boundaries[]={0U,31U,32U,33U,UINT_MAX};
 for(unsigned a=0U;a<5U;++a) for(unsigned b=0U;b<5U;++b) {
  unsigned lsb=boundaries[a], width=boundaries[b];
  uint32_t expected=0xA55A5AA5U;
  if(width>=1U && width<=32U && lsb<=31U && width<=32U-lsb) {
   uint64_t mask=((UINT64_C(1)<<width)-UINT64_C(1))<<lsb;
   expected=(uint32_t)(((uint64_t)expected&~mask)|(((uint64_t)0x5AA5A55AU<<lsb)&mask));
  }
  verify(replace_field(0xA55A5AA5U,lsb,width,0x5AA5A55AU)==expected);
 }
 for(unsigned budget=0U;budget<=16U;++budget) for(unsigned at=0U;at<=17U;++at)
 for(unsigned z=0U;z<2U;++z) {
  struct sequence s={0U,at,z ? 0U : 0x00F00000U,0x00500000U};
  int matched=budget>0U && (z || at<budget);
  unsigned reads=matched ? (z ? 1U : at+1U) : budget;
  verify(poll_match(read_word,&s,s.mask,s.expected,budget)==matched);
  verify(s.reads==reads);
 }
 verify(poll_match(NULL,NULL,0U,0U,10U)==-1);
 verify(poll_match(read_null,NULL,UINT32_MAX,0U,2U)==1);
 verify(null_reads==1U);
 printf("checks=%u failures=%u\n",checks,failures);
 return failures ? 1 : 0;
}
'''


def now():
    return datetime.now(timezone.utc).isoformat()


def write(name, value):
    p = ROOT / name
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(tmp, p)


def guard():
    if time.monotonic() >= DEADLINE:
        raise RuntimeError('BENCHMARK_WALL_LIMIT')
    p = Path('/proc') / str(INSTANCE['pid'])
    if not p.is_dir() or p.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19] != INSTANCE['start_ticks']:
        raise RuntimeError('BENCHMARK_SERVER_IDENTITY_CHANGED_OR_ENDED')
    intent = json.loads(Path(INSTANCE['factory_intent_path']).read_text())
    if intent['mode'] != 'STOPPED' or intent['epoch'] != INSTANCE['factory_intent_epoch']:
        raise RuntimeError('NEWER_FACTORY_OPERATOR_INTENT')


def call(route, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + route, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def gpu():
    p = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu,temperature.gpu,power.draw,clocks.sm',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5, check=False)
    return {'columns': ['memory_MiB', 'gpu_percent', 'temperature_C', 'power_W', 'sm_MHz'],
            'rows': p.stdout.strip().splitlines(), 'exit_code': p.returncode}


def generate(body):
    guard()
    req = urllib.request.Request(BASE + '/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    start = time.monotonic()
    first = None
    final = []
    reasoning = []
    usage = None
    timings = None
    finish = None
    with urllib.request.urlopen(req, timeout=120) as stream:
        for raw in stream:
            guard()
            if not raw.startswith(b'data: '):
                continue
            payload = raw[6:].strip()
            if payload == b'[DONE]':
                break
            event = json.loads(payload)
            if event.get('error'):
                raise RuntimeError('PROVIDER_ERROR_' + str(event['error'].get('type', 'UNKNOWN')))
            if event.get('usage'):
                usage = event['usage']
            if event.get('timings'):
                timings = event['timings']
            for choice in event.get('choices') or []:
                delta = choice.get('delta') or {}
                content, thought = delta.get('content'), delta.get('reasoning_content')
                if content or thought:
                    first = time.monotonic() if first is None else first
                if content:
                    final.append(content)
                if thought:
                    reasoning.append(thought)
                if choice.get('finish_reason'):
                    finish = choice['finish_reason']
    elapsed = time.monotonic() - start
    thoughts = ''.join(reasoning)
    count = len(call('/tokenize', {'content': thoughts, 'add_special': False})['tokens']) if thoughts else 0
    # No thought text or its hash is persisted. Token count is re-tokenized,
    # distinct from the provider's native total completion-token count.
    del thoughts, reasoning
    answer = ''.join(final)
    if '<think>' in answer or '</think>' in answer:
        raise RuntimeError('UNPARSED_REASONING_IN_FINAL_CHANNEL')
    return answer, {'wall_seconds': elapsed, 'first_generated_token_seconds': None if first is None else first-start,
                    'timings': timings, 'usage': usage, 'finish_reason': finish,
                    'reasoning_tokens_retokenized': count, 'final_characters': len(answer),
                    'reasoning_content_collected': False}


def strip_fence(text):
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    return text


def verify(case, answer, path):
    started = time.monotonic()
    if case != 'author_c':
        strict = True
        try:
            value = json.loads(answer)
        except ValueError:
            strict = False
            try:
                value = json.loads(strip_fence(answer))
            except ValueError:
                return {'status': 'FAIL', 'json_contract_valid': False, 'error': 'INVALID_FINAL_JSON'}
        expected = ({'x': next(x for x in range(97*89*83) if x%97==13 and x%89==42 and x%83==6),
                     'updated': (0xA55A5AA5 & ~0x00FF0000) | (0x005C0000 & 0x00FF0000), 'extracted': 92}
                    if case == 'numeric' else {'defective': ['F1', 'F3', 'F5']})
        return {'status': 'PASS' if value == expected and strict else 'FAIL', 'json_contract_valid': strict,
                'answer_correct_after_optional_fence': value == expected, 'expected': expected,
                'verification_seconds': time.monotonic()-started}
    code = strip_fence(answer)
    if len(code) > 32768:
        return {'status': 'FAIL', 'error': 'FINAL_CODE_TOO_LARGE'}
    (path / 'candidate.c').write_text(code + '\n')
    (path / 'harness.c').write_text(HARNESS)
    cc = '/mnt/data/forge-c/toolchains/LLVM-19.1.7-Linux-X64/bin/clang'
    exe = path / 'oracle'
    built = run_argv([cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-Wconversion', '-Wshadow',
                      '-fsanitize=undefined', '-fno-sanitize-recover=all', str(path/'harness.c'), '-o', str(exe)],
                     path, 60, {'clang'})
    (path / 'compile.stdout').write_bytes(built.stdout)
    (path / 'compile.stderr').write_bytes(built.stderr)
    if built.exit_code != 0:
        return {'status': 'FAIL', 'compile_exit': built.exit_code, 'verification_seconds': time.monotonic()-started}
    ran = run_argv([str(exe)], path, 8, {'oracle'})
    (path / 'oracle.stdout').write_bytes(ran.stdout)
    (path / 'oracle.stderr').write_bytes(ran.stderr)
    return {'status': 'PASS' if ran.exit_code == 0 else 'FAIL', 'compile_exit': built.exit_code,
            'oracle_exit': ran.exit_code, 'oracle_summary': ran.stdout.decode(errors='replace').strip(),
            'verification_seconds': time.monotonic()-started,
            'candidate_sha256': hashlib.sha256((path/'candidate.c').read_bytes()).hexdigest()}


def summarize(rows, status):
    result = {'status': status, 'recorded_trials': len(rows), 'expected_trials': 36, 'configs': {},
              'model': INSTANCE['model_blob'], 'model_file_sha256': json.loads((ROOT/'model-hash-verification.json').read_text())['sha256'],
              'context_capacity': 262144, 'kv_cache': 'f16', 'mtp': 'OFF_FOR_THIS_CONTROLLED_REASONING_COMPARISON',
              'repetitions_per_case': 3, 'native_named_efforts': 'NO_DISTINCT_TEMPLATE_CONTROL_OBSERVED',
              'speed_not_factory_or_model_capability_qualification': True, 'reasoning_content_collected': False,
              'factory_grants_renewed': False, 'factory_jobs_launched': False, 'updated_utc': now()}
    for name, enabled, budget in CONFIGS:
        selected = [row for row in rows if row['config'] == name]
        speeds = [(r['generation'].get('timings') or {}).get('predicted_per_second') for r in selected]
        speeds = [v for v in speeds if isinstance(v, (int, float)) and v > 0]
        result['configs'][name] = {'thinking_enabled': enabled, 'thinking_budget_tokens': budget,
            'measured_trials': len(selected), 'expected_trials': 9,
            'median_decode_tokens_per_second': statistics.median(speeds) if speeds else None,
            'median_request_seconds': statistics.median([r['generation']['wall_seconds'] for r in selected]) if selected else None,
            'median_thinking_tokens_retokenized': statistics.median([r['generation']['reasoning_tokens_retokenized'] for r in selected]) if selected else None,
            'independent_case_passes': sum(r['verification']['status']=='PASS' for r in selected),
            'truncated': sum(r['generation']['finish_reason']=='length' for r in selected)}
    write('summary.json', result)
    return result


def stop_server():
    pid = INSTANCE['pid']
    p = Path('/proc') / str(pid)
    if not p.exists():
        return {'already_absent': True}
    if p.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19] != INSTANCE['start_ticks']:
        return {'error': 'PID_IDENTITY_CHANGED_NO_SIGNAL_SENT'}
    os.kill(pid, signal.SIGTERM)
    for _ in range(100):
        if not p.exists() or p.joinpath('stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z':
            return {'terminated': True, 'pid': pid}
        time.sleep(0.1)
    os.kill(pid, signal.SIGKILL)
    return {'kill_sent_after_bounded_term': True, 'pid': pid}


def interrupted(*_):
    raise KeyboardInterrupt


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    rows = []
    write('benchmark-scope.json', {'owner_request': 'Test downloaded Ornith Q8 speed across reasoning configurations',
          'request_date': '2026-10-31', 'configs': CONFIGS, 'cases': CASES, 'common_request': COMMON,
          'source_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'benchmark_deadline_host_epoch': time.time()+1800, 'factory_mission_untouched': True,
          'maximum_requests': 36, 'maximum_completion_tokens_per_request': 8192})
    try:
        props = call('/props')
        write('server-properties.json', props)
        # Balanced serial order, fixed case/seed pairs across all settings.
        for repeat in range(3):
            order = CONFIGS[repeat:] + CONFIGS[:repeat]
            for case, prompt in CASES:
                for name, enabled, budget in order:
                    guard()
                    trial = f'{case}-r{repeat+1}-{name}'
                    path = ROOT/'trials'/trial
                    path.mkdir(parents=True)
                    body = {**COMMON, 'messages': [{'role': 'system', 'content': 'Follow the task exactly. Put only the requested deliverable in the final answer.'},
                             {'role': 'user', 'content': prompt}], 'seed': 20261031+repeat,
                            'chat_template_kwargs': {'enable_thinking': enabled}, 'thinking_budget_tokens': budget}
                    write('progress.json', {'status': 'GENERATING', 'trial': trial, 'completed': len(rows), 'total': 36, 'at': now()})
                    before = gpu()
                    answer, generation = generate(body)
                    (path/'final-answer.txt').write_text(answer)
                    checked = verify(case, answer, path)
                    row = {'trial': trial, 'case': case, 'repeat': repeat+1, 'config': name,
                           'request_sha256': hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest(),
                           'generation': generation, 'verification': checked, 'gpu_before': before, 'gpu_after': gpu()}
                    write(str(path.relative_to(ROOT)/'result.json'), row)
                    rows.append(row)
                    summarize(rows, 'IN_PROGRESS')
                    print(json.dumps({'trial':trial, 'decode_tps':(generation.get('timings') or {}).get('predicted_per_second'),
                          'wall_seconds':generation['wall_seconds'], 'reasoning_tokens':generation['reasoning_tokens_retokenized'],
                          'verification':checked['status'], 'completed':len(rows)}), flush=True)
        result = summarize(rows, 'COMPLETED_DESCRIPTIVE_SPEED_STUDY')
        write('progress.json', {'status': 'COMPLETED', 'completed': len(rows), 'total': 36, 'at': now()})
        print(json.dumps({'status':result['status'], 'configs':result['configs']}), flush=True)
    except BaseException as exc:
        summarize(rows, 'PARTIAL_' + type(exc).__name__)
        write('progress.json', {'status': 'PARTIAL', 'error_type': type(exc).__name__, 'completed': len(rows), 'total': 36, 'at': now()})
        raise
    finally:
        write('shutdown.json', stop_server())
