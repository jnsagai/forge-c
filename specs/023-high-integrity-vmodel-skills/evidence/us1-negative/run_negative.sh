#!/bin/sh
# T042: quickstart V3 negative cases, each on a fresh copy of a sealed, READY demo project (run 6).
#   APM=<apm> sh run_negative.sh <ready-project> <work-dir>   (output: one block per case, JSON lines from `hi`)
# Each copy gets the current package installed (apm install) and a clean commit, as an assisted user would have.
set -u
SRC=$1; WORK=$2
PY=$(python3 -c 'import sys; print(sys.executable)')
fresh() {  # copy the whole project (apm_modules holds the deployment record apm install needs)
  rm -rf "$WORK/$1"; mkdir -p "$WORK/$1"
  (cd "$SRC" && tar -cf - .) | (cd "$WORK/$1" && tar -xf -)
  cd "$WORK/$1"; HI=".claude/skills/hi-gates/scripts/hi.py"
  # apm keeps no trusted deployment baseline for a copied project: remove the deployed skills (no local edits) first
  rm -rf .claude/skills/hi-* .agents/skills/hi-*
  # its own APM home: the user's receipts bind the original project and refuse a copy of it
  HOME="$WORK/apm-home" "$APM" install --target claude,codex >/dev/null 2>&1 || echo "apm install failed"
  git add -A && git -c user.name=forge-c-hi -c user.email=demo@example.invalid commit -qm "negative case $1: start" \
    && echo "(copy of the READY project with the current package installed, committed: $(git rev-parse --short HEAD))"
}
step() { echo "\$ $*"; "$@"; echo "exit $?"; }

echo "## 0. Control: the unchanged copy seals READY"
fresh case0
step $PY $HI seal

echo; echo "## 1. Delete one trace link: a software requirement no longer cites the system requirement only it refines"
fresh case1
$PY - <<'EOF'
import json
from collections import Counter
p = "hi/sw-req/requirements.json"; d = json.load(open(p))
cites = Counter(s["id"] for i in d["items"] for s in i["sources"] if s.get("id", "").startswith("SYS-"))
it, link = next((i, s["id"]) for i in d["items"] if len(i["sources"]) > 1
                for s in i["sources"] if cites.get(s.get("id")) == 1)
it["sources"] = [s for s in it["sources"] if s.get("id") != link]
json.dump(d, open(p, "w"), indent=1)
print(f"removed {it['id']} -> {link}; remaining sources:", [s.get("id") for s in it["sources"]])
EOF
step $PY $HI trace --stage sw-req
step $PY $HI seal

echo; echo "## 2a. A required gate that cannot run: a document source without a local index"
fresh case2
mkdir -p docs && printf '%%PDF-1.4\n%% placeholder, not a real manual\n' > docs/rm.pdf
$PY - <<'EOF'
import json
p = ".hi/project.json"; d = json.load(open(p))
d["inputs"].append({"path": "docs/rm.pdf", "kind": "reference_document", "doc_id": "RM-DEMO"})
json.dump(d, open(p, "w"), indent=2)
p = "hi/sw-req/requirements.json"; d = json.load(open(p))
d["items"][0]["sources"].append({"kind": "document", "doc_id": "RM-DEMO", "section": "4.2", "page": 12})
json.dump(d, open(p, "w"), indent=1)
print("declared RM-DEMO and cited it from", d["items"][0]["id"], "- no 'hi doc-index' was run")
EOF
step $PY $HI gate sw-req
step $PY $HI seal
echo; echo "## 2b. Without poppler, building the index is NOT_RUN, never a pass"
step env PATH=/nonexistent "$PY" $HI doc-index docs/rm.pdf --doc-id RM-DEMO

echo; echo "## 3. A write outside the author's scope"
fresh case3
step $PY $HI role set author sys-req
echo '{"tool_name": "Write", "tool_input": {"file_path": "src/supervisor.c", "content": "int x;"}}' > "$WORK/hook.json"
echo "\$ guard.py < Write src/supervisor.c   (author of sys-req may write hi/sys-req/** only)"
$PY .claude/skills/hi-gates/scripts/guard.py < "$WORK/hook.json"; echo "exit $?"
echo '{"tool_name": "Write", "tool_input": {"file_path": "hi/sys-req/notes.md", "content": "x"}}' > "$WORK/hook.json"
echo "\$ guard.py < Write hi/sys-req/notes.md   (inside the scope)"
$PY .claude/skills/hi-gates/scripts/guard.py < "$WORK/hook.json"; echo "exit $?"
rm -f "$WORK/hook.json"
echo "-- bypass the hook: write the file directly"
mkdir -p src && echo "int x;" > src/supervisor.c
step $PY $HI scope --role author --stage sys-req
step $PY $HI role clear
