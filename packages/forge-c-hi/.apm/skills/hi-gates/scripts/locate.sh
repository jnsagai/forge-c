#!/bin/sh
# Locate and run a forge-c-hi hi-gates script from wherever APM installed the skill.
# Usage: sh locate.sh <script.py> [args...]
# The search order is: $HI_GATES_DIR, then each APM target skill root under the project directory
# ($CLAUDE_PROJECT_DIR or the current directory).
f="$1"; shift
base="${CLAUDE_PROJECT_DIR:-.}"
for d in "${HI_GATES_DIR:-}" \
         "$base/.claude/skills/hi-gates/scripts" "$base/.agents/skills/hi-gates/scripts" \
         "$base/.github/skills/hi-gates/scripts" "$base/.cursor/skills/hi-gates/scripts" \
         "$base/.kiro/skills/hi-gates/scripts" "$base/.gemini/skills/hi-gates/scripts" \
         "$base/.opencode/skills/hi-gates/scripts" "$base/.windsurf/skills/hi-gates/scripts"; do
  if [ -n "$d" ] && [ -f "$d/$f" ]; then
    exec "${HI_PYTHON:-python3}" "$d/$f" "$@"
  fi
done
echo "forge-c-hi: hi-gates/scripts/$f not found (is the forge-c-hi APM package installed?)" >&2
exit 127
