#!/usr/bin/env bash
# Compare host-built RCC driver code sizes after full native regression tests.
# Intentionally NOT a Flash/RAM/stack certification or target measurement.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
for tool in cmake ninja clang ctest size; do
  command -v "$tool" >/dev/null 2>&1 || { echo "MISSING: $tool" >&2; exit 2; }
done
mkdir -p "$root/evidence/oss-demo"
report="$root/evidence/oss-demo/host-opt-size.log"
{
  echo 'HOST ONLY optimization comparison, not MCU footprint proof'
  clang --version | head -1
  for level in Os O2 Oz; do
    build="$root/build/host-$level"
    echo "======= HOST -$level ======="
    cmake -S "$root" -B "$build" -G Ninja \
      -DCMAKE_C_COMPILER=clang -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_FLAGS_RELEASE="-$level -DNDEBUG" -DFORGE_COVERAGE=OFF
    cmake --build "$build"
    ctest --test-dir "$build" --output-on-failure
    echo 'Host archive section sizes:'
    size -A "$build/libforge_rcc_demo.a"
    echo 'Host compiler stack-usage estimates (NOT interrupt-inclusive):'
    find "$build/CMakeFiles/forge_rcc_demo.dir" -name '*.su' -type f -exec cat {} \;
  done
} > "$report" 2>&1 || { tail -80 "$report" >&2; exit 1; }
cat "$report"
