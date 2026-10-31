"""Run synthetic oracle controls after all GPU measurements, never as model results."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path('/mnt/data/forge-c/benchmarks/ornith-speed-20261031')
spec = importlib.util.spec_from_file_location('bench', ROOT/'run_benchmark.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

REFERENCE = '''#include <stdint.h>
#include <stddef.h>
uint32_t replace_field(uint32_t original, unsigned lsb, unsigned width, uint32_t replacement)
{
 if (width == 0U || width > 32U || lsb > 31U || width > 32U-lsb) return original;
 if (width == 32U) return replacement;
 uint32_t low=(UINT32_C(1)<<width)-UINT32_C(1);
 uint32_t mask=low<<lsb;
 return original ^ ((original ^ (replacement<<lsb)) & mask);
}
int poll_match(uint32_t (*read_word)(void *), void *ctx, uint32_t mask, uint32_t expected, unsigned max_reads)
{
 if (read_word == NULL) return -1;
 while (max_reads != 0U) {
  --max_reads;
  uint32_t word=read_word(ctx);
  if ((word & mask) == (expected & mask)) return 1;
 }
 return 0;
}
'''

controls = [
    ('positive_reference', REFERENCE, 'PASS'),
    ('negative_full_width', REFERENCE.replace('if (width == 32U) return replacement;',
                                             'if (width == 32U) return UINT32_MAX;'), 'FAIL'),
    ('negative_zero_budget', REFERENCE.replace('while (max_reads != 0U)',
                                              '++max_reads; while (max_reads != 0U)'), 'FAIL'),
    ('negative_wrong_null', REFERENCE.replace('if (read_word == NULL) return -1;',
                                             'if (read_word == NULL) return 0;'), 'FAIL'),
]
rows = []
for name, code, expected in controls:
    path = ROOT/'controls'/name
    path.mkdir(parents=True)
    result = bench.verify('author_c', code, path)
    rows.append({'id': name, 'authorship': 'SYNTHETIC_REFERENCE_NOT_MODEL_OUTPUT',
                 'expected': expected, 'observed': result, 'matches_expected': result['status'] == expected,
                 'harness_sha256': hashlib.sha256((path/'harness.c').read_bytes()).hexdigest()})
report = {'scope': 'Independent oracle positive and seeded-negative controls after inference',
          'run_after_gpu_measurements': (ROOT/'shutdown.json').is_file(),
          'controls': rows, 'status': 'PASS' if all(r['matches_expected'] for r in rows) else 'FAIL'}
(ROOT/'controls/report.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
print(json.dumps(report))
if report['status'] != 'PASS':
    raise SystemExit(1)
