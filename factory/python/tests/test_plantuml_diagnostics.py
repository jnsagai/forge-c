"""A view failure must identify its actual checked file, including debug-path calls."""
from subprocess import CompletedProcess

import pytest
from forge_factory.inspection import views
from forge_factory.mcp.sdk import ToolContext
from forge_factory.mcp.servers import docs
from test_swe2_architecture import ARCH_MIN, DYNAMIC_PUML, STATIC_PUML


@pytest.fixture
def diagrams(tmp_path, monkeypatch):
    (tmp_path / "workproducts/SWE.2").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.2/software_architecture.md").write_text(ARCH_MIN)
    (tmp_path / views.STATIC).write_text(STATIC_PUML)
    (tmp_path / views.DYNAMIC).write_text(DYNAMIC_PUML)
    monkeypatch.setattr(views, "plantuml_jar", lambda: tmp_path / "fixture.jar")
    return tmp_path


@pytest.mark.parametrize("bad", [views.STATIC, views.DYNAMIC])
def test_syntax_failure_names_actual_view_and_does_not_render(diagrams, monkeypatch, bad):
    calls = []

    def run(args, cwd, **kwargs):
        calls.append(args)
        failed = bad in args
        return CompletedProcess(args, int(failed), "", "Some diagram description contains errors" if failed else "")

    monkeypatch.setattr(views, "_plantuml", run)
    report = views.check_views(diagrams, render=True)
    assert report["verdict"] == "FAIL"
    assert report["major_findings"] == ["VIEWS:SYNTAX:" + bad + ":Some diagram description contains errors"]
    assert report["stats"]["syntax"] == "FAIL"
    assert all(c[0] in ("-checkonly", "-syntax") for c in calls)


def test_debug_path_does_not_misattribute_canonical_view_failure(diagrams, monkeypatch):
    debug = "workproducts/SWE.2/_debug.puml"
    (diagrams / debug).write_text("@startuml\nAlice -> Bob : hello\n@enduml\n")
    monkeypatch.setattr(views, "_plantuml", lambda args, cwd, **kwargs: CompletedProcess(
        args, int(views.STATIC in args), "", "Some diagram description contains errors"))
    ctx = ToolContext("forge-docs-mcp", "validate_artifact", "swe2-author", "SWE.2", diagrams, "diagnostic-test")
    report = docs.validate_artifact(ctx, docs.ValidateIn(path=debug, check="plantuml"))
    assert report["status"] == "FAIL"  # no waiver of the actual bad canonical view
    assert views.STATIC in report["issues"][0]
    assert report["metrics"]["validation_scope"] == "CANONICAL_ARCHITECTURE_VIEWS"
    assert report["metrics"]["requested_path"] == debug
    assert report["metrics"]["checked_static"] == views.STATIC
    assert report["metrics"]["checked_dynamic"] == views.DYNAMIC
    assert report["metrics"]["syntax_static"] == "FAIL"
    assert report["metrics"]["syntax_dynamic"] == "PASS"


def test_parser_line_is_included_for_a_failing_canonical_view(diagrams, monkeypatch):
    def run(args, cwd, **kwargs):
        if args == ["-syntax"]:
            return CompletedProcess(args, 200, "ERROR\n3\nSyntax Error? (Assumed diagram type: component)\n", "")
        failed = views.STATIC in args
        return CompletedProcess(args, int(failed), "", "Some diagram description contains errors" if failed else "")

    monkeypatch.setattr(views, "_plantuml", run)
    report = views.check_views(diagrams)
    assert report["verdict"] == "FAIL"
    assert report["major_findings"] == [
        "VIEWS:SYNTAX:" + views.STATIC + ":line 4:Syntax Error? (Assumed diagram type: component)"]


@pytest.mark.parametrize("diagnostic", [
    CompletedProcess([], 0, "ERROR\n3\nnot a failing parser response\n", ""),
    CompletedProcess([], 200, "unstructured output", ""),
    CompletedProcess([], 200, "ERROR\n99999999\noutside the source\n", ""),
    None,
])
def test_optional_diagnostics_never_waive_the_failure(diagrams, monkeypatch, diagnostic):
    from subprocess import TimeoutExpired

    def run(args, cwd, **kwargs):
        if args == ["-syntax"]:
            if diagnostic is None:
                raise TimeoutExpired("fixture", 15)
            return diagnostic
        failed = views.STATIC in args
        return CompletedProcess(args, int(failed), "", "original syntax failure" if failed else "")

    monkeypatch.setattr(views, "_plantuml", run)
    report = views.check_views(diagrams)
    assert report["verdict"] == "FAIL"
    assert report["major_findings"] == ["VIEWS:SYNTAX:" + views.STATIC + ":original syntax failure"]
