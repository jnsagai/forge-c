#!/bin/sh
# T053 (US2-AS3): a missing or unreadable reference document stops a driver project at intake, never later.
#   sh run_us2_negative.sh <package-dir> <work-dir>
set -u
PKG=$1; WORK=$2
PY=$(python3 -c 'import sys; print(sys.executable)')
HI="$PKG/.apm/skills/hi-gates/scripts/hi.py"
step() { echo "\$ $*" | sed "s|$PKG|<package>|g; s|$PY|python3|g"; "$@"; echo "exit $?"; }
rm -rf "$WORK"; mkdir -p "$WORK/needs" "$WORK/docs"; cd "$WORK"
printf '| CON-WDG-001 | Driver scope: the independent watchdog only. |\n' > needs/scope.md

echo "## 1. The reference document does not exist"
step $PY $HI init --level HI-2 --class reference_document --input docs/rm.pdf:reference_document:RM-DEMO \
  --input needs/scope.md:constraints
test -f .hi/project.json && echo "project.json written (unexpected)" || echo "no project.json written"

echo; echo "## 2. The reference document exists but is not a readable PDF"
printf 'this is not a PDF\n' > docs/rm.pdf
step $PY $HI init --level HI-2 --class reference_document --input docs/rm.pdf:reference_document:RM-DEMO \
  --input needs/scope.md:constraints
step $PY $HI doc-index docs/rm.pdf --doc-id RM-DEMO
test -f .hi/docs/RM-DEMO.index.json && echo "index written (unexpected)" || echo "no index written"

echo; echo "## 3. A readable document, but no index built yet: a citation cannot pass the source gate"
PKG="$PKG" $PY - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.environ["PKG"], "tests"))
from test_doc_index import make_pdf  # a generated PDF, no vendor content
from pathlib import Path; make_pdf(Path("docs/rm.pdf"), ["4 Watchdog\n4.2 Start\nText."])
PYEOF
step $PY $HI init --force --level HI-2 --class reference_document --input docs/rm.pdf:reference_document:RM-DEMO \
  --input needs/scope.md:constraints
$PY - <<'PYEOF'
import json, os
os.makedirs("hi/sw-req", exist_ok=True)
json.dump({"schema": "forge-c-hi/requirement-set@1", "stage": "sw-req", "baseline_id": "BL", "status": "draft",
           "provenance": {"role": "author", "skill": "hi-sw-req-author", "skill_version": "0.1.0", "harness": "manual",
                          "model": None, "model_family": "x", "input_hashes": {}, "created_utc": "2026-11-23T00:00:00Z",
                          "run_id": "neg"},
           "items": [{"id": "DRV-WDG-001", "level": "driver_interface", "derived": False, "status": "proposed",
                      "verification_method": "test",
                      "text": "The driver shall start the independent watchdog when the start service is called.",
                      "sources": [{"kind": "document", "doc_id": "RM-DEMO", "section": "4.2", "page": 12}]}],
           "open_points": []}, open("hi/sw-req/requirements.json", "w"), indent=1)
print("wrote one DRV item citing RM-DEMO 4.2 p.12")
PYEOF
step $PY $HI gate sw-req
