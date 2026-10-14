#!/usr/bin/env bash
set -euo pipefail
python3 -m unittest discover -s tests -v
printf '\nScaffold tests done. Run make profile separately; pilot is DRAFT and must block release until approved.\n'
