#!/usr/bin/env python3
"""forge-c-hi `hi` command line. Usage: python3 hi.py <command> [options]; see SKILL.md."""
import os
import sys

sys.dont_write_bytecode = True  # never write __pycache__ into the installed skills (scope gate)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from forge_hi.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
