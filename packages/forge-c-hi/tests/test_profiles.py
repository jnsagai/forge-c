"""T006: standard profiles are valid, identifier-only, and resolved deterministically."""
from __future__ import annotations

import json

import pytest

from conftest import PKG, REFS
from forge_hi.config import ConfigError, effective_rigor, load_profile, load_project, native_level_name
from forge_hi.jsonschema_lite import validate

PROFILES = REFS / "profiles"
SHIPPED = ["generic", "iso26262", "iec61508", "aspice40"]
SCHEMA = json.loads((REFS / "schemas" / "profile.schema.json").read_text())


def _project(root, **over):
    doc = {
        "schema": "forge-c-hi/project@1",
        "project_id": "demo-project",
        "integrity_level": "HI-2",
        "input_class": "natural_language",
        "entry_stage": "sys-req",
        "inputs": [{"path": "needs.md", "kind": "needs"}],
        "roles": {
            "author": {"harness": "manual", "command": []},
            "inspector": {"harness": "manual", "command": []},
        },
    }
    doc.update(over)
    (root / ".hi").mkdir(exist_ok=True)
    (root / ".hi" / "project.json").write_text(json.dumps(doc))
    return doc


@pytest.mark.parametrize("pid", SHIPPED + ["_template"])
def test_profile_files_validate(pid):
    doc = json.loads((PROFILES / f"{pid}.json").read_text())
    assert validate(doc, SCHEMA) == []


@pytest.mark.parametrize("pid", SHIPPED)
def test_clause_refs_are_identifiers_only(pid):
    doc = load_profile(pid)
    for stage, refs in doc["clause_refs"].items():
        for ref in refs:
            assert len(ref) <= 40, (stage, ref)
            assert len(ref.split()) <= 6, (stage, ref)
            assert not any(p in ref for p in ("!", "?", ". ")) and not ref.endswith("."), (stage, ref)


@pytest.mark.parametrize("pid", SHIPPED)
def test_every_mapped_level_has_rigor(pid):
    doc = load_profile(pid)
    assert set(doc["level_map"]) == set(doc["rigor"])


def test_absent_profile_defaults_to_generic(tmp_project):
    _project(tmp_project)
    proj = load_project(tmp_project)
    assert proj["profile"] == "generic"
    assert effective_rigor(proj)["independence"]


def test_unmapped_level_is_refused(tmp_project):
    _project(tmp_project, profile="iec61508", integrity_level="HI-0")
    with pytest.raises(ConfigError):
        effective_rigor(load_project(tmp_project))


def test_unknown_profile_is_refused(tmp_project):
    _project(tmp_project, profile="no-such-standard")
    with pytest.raises(ConfigError):
        effective_rigor(load_project(tmp_project))


def test_invalid_project_is_refused(tmp_project):
    _project(tmp_project, integrity_level="ASIL-B")
    with pytest.raises(ConfigError):
        load_project(tmp_project)


@pytest.mark.parametrize(
    "pid,level,name", [("iso26262", "HI-2", "ASIL B"), ("iec61508", "HI-2", "SIL 2"), ("generic", "HI-2", "HI-2")]
)
def test_native_level_names(pid, level, name):
    assert native_level_name(load_profile(pid), level) == name


def test_example_projects_use_mapped_levels():
    examples = sorted((PKG / "examples").glob("*/hi-project.example.json"))
    for ex in examples:
        doc = json.loads(ex.read_text())
        prof = load_profile(doc.get("profile", "generic"))
        assert doc["integrity_level"] in prof["level_map"], ex
