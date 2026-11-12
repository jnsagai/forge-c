"""Summarize retained standalone speed measurements; never upgrade an outcome."""
import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path


def median(values):
    return statistics.median(values) if values else None


def summarize(root):
    root = Path(root)
    rows = [json.loads(p.read_text()) for p in sorted((root / 'trials').glob('*/result.json'))]
    assert len({r['trial'] for r in rows}) == len(rows), 'DUPLICATE_TRIAL'
    original = json.loads((root / 'summary.json').read_text())
    report = {'schema': 'forge-c/ornith-descriptive-speed-report/1',
              'scope': 'Standalone synthetic cases, not full pipeline or model qualification',
              'recorded': len(rows), 'planned': 36, 'benchmark_summary': original, 'configs': {},
              'native_effort_levels': 'low/medium/high/xhigh render identically; no distinct trained template control',
              'reasoning_tokens': 'Retokenized text counts; native completion tokens include all generated tokens',
              'first_token_latency': 'Includes thinking tokens; not time to first final-answer token',
              'factory_activated': False, 'old_factory_mission_reset_or_renewed': False}
    for config in ('off', 'budget512', 'budget2048', 'default_on'):
        group = [r for r in rows if r['config'] == config]
        speed = [(r['generation'].get('timings') or {}).get('predicted_per_second') for r in group]
        speed = [v for v in speed if isinstance(v, (int, float))]
        report['configs'][config] = {
            'n': len(group), 'planned': 9, 'decode_tps_median': median(speed),
            'decode_tps_min': min(speed) if speed else None, 'decode_tps_max': max(speed) if speed else None,
            'wall_seconds_median': median([r['generation']['wall_seconds'] for r in group]),
            'reasoning_tokens_median': median([r['generation']['reasoning_tokens_retokenized'] for r in group]),
            'completion_tokens_total': sum((r['generation'].get('usage') or {}).get('completion_tokens', 0) for r in group),
            'case_passes': sum(r['verification']['status'] == 'PASS' for r in group),
            'truncated': sum(r['generation']['finish_reason'] == 'length' for r in group),
            'cases': {case: {
                'n': sum(r['case'] == case for r in group),
                'passes': sum(r['case'] == case and r['verification']['status'] == 'PASS' for r in group),
                'wall_seconds_median': median([r['generation']['wall_seconds'] for r in group if r['case'] == case]),
                'completion_tokens_median': median([(r['generation'].get('usage') or {}).get('completion_tokens', 0)
                                                    for r in group if r['case'] == case]),
            } for case in ('numeric', 'author_c', 'review_c')},
        }
    controls = root / 'controls/report.json'
    report['oracle_controls'] = json.loads(controls.read_text()) if controls.is_file() else {'status': 'NOT_RUN'}
    (root / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    columns = ['trial', 'case', 'repeat', 'config', 'native_completion_tokens', 'reasoning_tokens_retokenized',
               'request_seconds', 'decode_tps', 'finish_reason', 'verification']
    with (root / 'trials.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            gen = row['generation']
            writer.writerow({k: v for k, v in zip(columns, [row['trial'], row['case'], row['repeat'], row['config'],
                (gen.get('usage') or {}).get('completion_tokens'), gen['reasoning_tokens_retokenized'],
                gen['wall_seconds'], (gen.get('timings') or {}).get('predicted_per_second'),
                gen['finish_reason'], row['verification']['status']], strict=True)})
    def number(value):
        return 'UNKNOWN' if value is None else f'{value:.2f}'
    lines = ['# Ornith-1.5-35B-A3B Q8 reasoning-speed study — 31 October 2026', '',
        f'Recorded {len(rows)}/36 matched serial trials on Omniverse2, three cases × three repetitions per configuration.', '',
        'RTX 6000 Ada 48 GB; full GPU placement; 262144 context capacity; f16 KV; MTP off; 12 generation / 24 batch threads.',
        'Temperature 0.6, top_p 0.95, top_k 20, min_p 0, fixed matched seeds; prompt caching requested off.',
        'Warm-up and model hash verification precede timed trials. This is not a paired comparison with historical Qwen runs.', '',
        '| Configuration | Decode tok/s median (range) | Request seconds median | Thinking tokens median* | Cases passed / 9 | Truncated |',
        '|---|---:|---:|---:|---:|---:|']
    for name, value in report['configs'].items():
        lines.append(f"| {name} | {number(value['decode_tps_median'])} ({number(value['decode_tps_min'])}–{number(value['decode_tps_max'])}) | "
                     f"{number(value['wall_seconds_median'])} | {number(value['reasoning_tokens_median'])} | {value['case_passes']} | {value['truncated']} |")
    lines += ['', '*Thinking counts are re-tokenized separately and may differ at special-token/whitespace boundaries.', '',
        'The downloaded template has enable_thinking, with no reasoning_effort variable. The local rendered prompts for low, medium, high and xhigh have identical hashes. '
        'The measured alternatives therefore use explicit server thinking budgets: 512, 2048 or unrestricted within the common 8192 total-completion cap; off closes thinking before generation.', '',
        '| Case | off passes / 3 | budget512 passes / 3 | budget2048 passes / 3 | default_on passes / 3 |',
        '|---|---:|---:|---:|---:|']
    for case in ('numeric', 'author_c', 'review_c'):
        lines.append('| ' + case + ' | ' + ' | '.join(str(report['configs'][c]['cases'][case]['passes']) for c in report['configs']) + ' |')
    lines += ['', 'Numeric: exact integer CRT and 32-bit field arithmetic, strict final JSON. '
        'Author C: independent host compilation, UBSan and 31878 checks of field replacement and bounded callback polling. '
        'Review C: exactly three seeded defects among six functions; false rejections fail the case.', '',
        'The sample is small and synthetic. Pass counts are task observations, not general accuracy, reliability, model selection or ASPICE qualification. '
        'A thinking-budget cutoff is an experimental intervention; faster answers that fail checks are not an accepted quality improvement. '
        'First-token latency includes reasoning. Actual prompt lengths are in the raw timings; 262144 is capacity, not measured full-context throughput.', '',
        'No thought text is retained. Final answers, generated candidate C, oracle/compiler results, numeric usage, model SHA256, exact script and server flags are retained. '
        'Factory missions, production settings and old grants are unchanged.', '',
        'Model/template references: [official model](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B), '
        '[official template](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B/blob/main/chat_template.jinja), '
        '[llama.cpp request parsing](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/server-common.cpp).', '']
    (root / 'SPEED-REPORT.md').write_text('\n'.join(lines))
    return report


if __name__ == '__main__':
    report = summarize(sys.argv[1])
    print(json.dumps({'recorded': report['recorded'], 'configs': report['configs']}))
