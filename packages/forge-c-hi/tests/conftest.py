"""Shared fixtures for the forge-c-hi package tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1]
SKILLS = PKG / ".apm" / "skills"
GATES = SKILLS / "hi-gates"
REFS = GATES / "references"
SCRIPTS = GATES / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SPECS = PKG.parents[1] / "specs" / "023-high-integrity-vmodel-skills"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def skills_root() -> Path:
    return SKILLS


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A git-initialised empty consumer project."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path
