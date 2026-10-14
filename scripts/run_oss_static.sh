#!/usr/bin/env bash
# Independent static analysis using only open-source tooling.
# Fails closed if an expected tool is not installed.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/evidence/oss-demo"
for tool in clang cppcheck; do
  command -v "$tool" >/dev/null 2>&1 || { echo "MISSING: $tool; install it first (no static-analysis PASS recorded)" >&2; exit 2; }
done
{
  echo '# Clang static analyzer'
  clang --analyze -std=c11 -Wall -Wextra -Werror \
    -I"$root/drivers/demo_rcc/include" "$root/drivers/demo_rcc/src/forge_rcc_demo.c"
  echo '# Cppcheck defect analysis'
  cppcheck --std=c11 --enable=warning,style,performance,portability \
    --error-exitcode=1 --inline-suppr --quiet \
    -I"$root/drivers/demo_rcc/include" "$root/drivers/demo_rcc/src/forge_rcc_demo.c"
  echo 'STATIC_ANALYSIS_COMPLETED (NOT MISRA coverage and NOT safety signoff)'
} > "$root/evidence/oss-demo/static.log" 2>&1 || {
  tail -50 "$root/evidence/oss-demo/static.log" >&2; exit 1;
}
cat "$root/evidence/oss-demo/static.log"
