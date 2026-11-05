"""Private engineering contrast: pin source imports before pytest changes test search path."""
import os
import sys
from pathlib import Path
source=Path(sys.argv[1]).resolve()
os.environ['FORGE_REPO_ROOT']=str(source)
sys.path.insert(0,str(source/'factory/python'))
from forge_factory.lrtx import stack
assert Path(stack.__file__).resolve()==source/'factory/python/forge_factory/lrtx/stack.py'
print('ACTUAL_STACK_SOURCE='+str(Path(stack.__file__).resolve()),flush=True)
import pytest
raise SystemExit(pytest.main(sys.argv[2:]))
