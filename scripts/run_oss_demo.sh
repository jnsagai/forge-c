#!/usr/bin/env bash
# Demonstration only: LLVM host tests + MC/DC + deterministic evidence hashes.
# This is NOT a target build, MISRA compliance report, or ISO 26262 verification.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
build="$root/build/oss-demo"
mkdir -p "$build" "$root/evidence/oss-demo"
for tool in cmake ninja clang ctest llvm-profdata llvm-cov python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "MISSING OPEN-SOURCE TOOL: $tool" >&2; exit 2; }
done
{
  echo '## Build'; cmake -S "$root" -B "$build" -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_BUILD_TYPE=Debug -DFORGE_COVERAGE=ON -DFORGE_MCDC=ON
  cmake --build "$build" --verbose
  echo '## Tests'
  rm -f "$build/test.profraw" "$build/test.profdata"
  LLVM_PROFILE_FILE="$build/test.profraw" ctest --test-dir "$build" --output-on-failure
  test -s "$build/test.profraw" || { echo 'FAILED: no raw LLVM profile' >&2; exit 3; }
  echo '## MC/DC coverage'
  llvm-profdata merge -sparse "$build/test.profraw" -o "$build/test.profdata"
  llvm-cov report "$build/test_forge_rcc_demo" -instr-profile="$build/test.profdata" \
     -show-mcdc-summary "$root/drivers/demo_rcc/src/forge_rcc_demo.c"
  llvm-cov show "$build/test_forge_rcc_demo" -instr-profile="$build/test.profdata" \
     --show-mcdc "$root/drivers/demo_rcc/src/forge_rcc_demo.c"
} > "$root/evidence/oss-demo/llvm-host.log" 2>&1 || {
  echo 'FAIL: check evidence/oss-demo/llvm-host.log' >&2
  tail -30 "$root/evidence/oss-demo/llvm-host.log" >&2
  exit 1
}
cp "$build/test.profdata" "$root/evidence/oss-demo/test.profdata"
python3 "$root/tools/oss_demo_manifest.py" \
  --root "$root" \
  --log "$root/evidence/oss-demo/llvm-host.log" \
  --profile "$root/evidence/oss-demo/test.profdata" \
  --output "$root/evidence/oss-demo/manifest.json"
echo 'DEMO PASS: Clang host build/tests/LLVM MC/DC generated. Not ASIL B, not MISRA compliance.'
