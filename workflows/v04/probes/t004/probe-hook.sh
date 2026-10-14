#!/usr/bin/env bash
# T004 probe hook (host side, blocking pre_tool_use): log context, deny native shell.
log="${FORGE_PROBE_HOOK_LOG:-/tmp/forge-probe-hooks.jsonl}"
ctx="$(cat)"
printf '%s\n' "$ctx" | tr -d '\n' >> "$log"; printf '\n' >> "$log"
tool="$(printf '%s' "$ctx" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))' 2>/dev/null)"
if [ "$tool" = "shell" ]; then
  echo '{"decision":"block","reason":"FORGE_POLICY: native shell denied for this role"}'
  exit 2
fi
exit 0
