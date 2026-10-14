#!/usr/bin/env bash
# Clang static analyzer for the host RCC example (not a MISRA or safety assessment).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
command -v clang >/dev/null 2>&1 || { echo 'MISSING OSS tool: clang' >&2; exit 2; }
mkdir -p "$root/evidence/oss-demo"
if ! clang --analyze -std=c11 -Wall -Wextra -Werror -Wconversion -Wsign-conversion \
    -I"$root/drivers/demo_rcc/include" "$root/drivers/demo_rcc/src/forge_rcc_demo.c" \
    > "$root/evidence/oss-demo/clang-analyzer.log" 2>&1; then
    cat "$root/evidence/oss-demo/clang-analyzer.log" >&2; exit 1
fi
{
  echo 'Clang Static Analyzer completed successfully; no diagnostics for this host demo.'
  clang --version | head -1
} >> "$root/evidence/oss-demo/clang-analyzer.log"
cat "$root/evidence/oss-demo/clang-analyzer.log"
