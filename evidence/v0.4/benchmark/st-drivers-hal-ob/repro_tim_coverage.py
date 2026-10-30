"""Read-only replay of TIM's LLVM coverage symptom; PASS means reproduced, never valid coverage."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from forge_factory.common import state_dir

workspace = state_dir() / 'workorders/WO-AFO-a06f0cfbf6e556cc-a1/workspace'
build = workspace / 'build/tests-unit'
binary, profile = build / 'test_tim', build / 'merged.profdata'
command = ['llvm-cov', 'export', '-summary-only', '-instr-profile=' + str(profile), str(binary)]
proc = subprocess.run(command, capture_output=True, timeout=60)
record = {'observation': 'SYMPTOM_PRESENT' if proc.returncode and b'truncated coverage data' in proc.stderr else
          'SYMPTOM_NOT_REPRODUCED', 'root_cause_status': 'UNKNOWN', 'exit_code': proc.returncode,
          'command': command, 'stderr': proc.stderr.decode(errors='replace'), 'stdout_bytes': len(proc.stdout),
          'inputs': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (binary, profile)],
          'tool_path': shutil.which('llvm-cov'),
          'tool_version': subprocess.check_output(['llvm-cov', '--version']).decode().strip(),
          'interpretation': 'A successful replay check establishes the failed export symptom only. Coverage metrics '
          'remain unavailable; no factory cause, fix, effectiveness or delivered-code diagnosis is verified.'}
print(json.dumps(record, indent=2))
assert record['observation'] == 'SYMPTOM_PRESENT', 'record the new observation before changing the diagnosis'
