#!/bin/sh
# T057 (US3, SC-007): the same sealed demo project gated and sealed under other standard profiles; skills unchanged.
#   APM=<apm> sh run_profiles.sh <ready-project> <work-dir> <example-project-json>
set -u
SRC=$1; WORK=$2; EX=$3
PY=$(python3 -c 'import sys; print(sys.executable)')
for P in "generic HI-2" "iso26262 HI-2" "iec61508 HI-2"; do
  set -- $P; PROFILE=$1; LEVEL=$2; C="$WORK/$PROFILE"
  rm -rf "$C"; mkdir -p "$C"; (cd "$SRC" && tar -cf - .) | (cd "$C" && tar -xf -); cd "$C"
  rm -rf .claude/skills/hi-* .agents/skills/hi-*
  HOME="$WORK/apm-home" "$APM" install --target claude,codex >/dev/null 2>&1 || echo "apm install failed"
  git add -A && git -c user.name=forge-c-hi -c user.email=demo@example.invalid commit -qm "profile case $PROFILE: start"
  echo "## $PROFILE $LEVEL"
  echo "\$ hi init --force --from <example> --profile $PROFILE --level $LEVEL"
  $PY -B .claude/skills/hi-gates/scripts/hi.py init --force --from "$EX" --profile $PROFILE --level $LEVEL
  for S in sys-req sw-req; do echo "\$ hi gate $S"; $PY -B .claude/skills/hi-gates/scripts/hi.py gate $S; done
  echo "\$ hi seal"; $PY -B .claude/skills/hi-gates/scripts/hi.py seal
  PKG=$(ls -td hi/packages/*/ | head -1)
  echo "-- manifest: $($PY -c "import json;m=json.load(open('$PKG/manifest.json'));print(m['profile'], m['integrity_level'], m['level_name'], m['status'], len(m['gaps']), 'gaps')")"
  echo "-- gates.md stage names: $(grep -o '^| sw-req: [^|]*' $PKG/gates.md | head -1) / $(grep -o '^| sys-req: [^|]*' $PKG/gates.md | head -1)"
  echo "-- git diff --stat of the installed skills: '$(git diff --stat -- .claude/skills .agents/skills)'"
  echo
done
