"""The source commit is checked against the running source, not the campaign's repository.

On the real line the campaign lives in its own small data repository, which never holds the factory
commit. The private launch rehearsal refused every durable launch with SOURCE_REVISION_UNRESOLVED.
"""
import subprocess

import pytest
from forge_factory.afo import line_recovery as R


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout.strip()


def repository(path, name):
    path.mkdir()
    git(path, "init", "-q")
    (path / name).write_text(name)
    git(path, "add", name)
    git(path, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", name)
    return git(path, "rev-parse", "HEAD")


@pytest.fixture
def repositories(tmp_path, monkeypatch):
    source, data = tmp_path / "source", tmp_path / "data"
    revision = repository(source, "factory")
    repository(data, "campaign")
    monkeypatch.setattr(R, "REPO_ROOT", source)
    return revision


def test_running_source_commit_resolves_though_campaign_repository_lacks_it(repositories):
    assert R._revision(repositories) == repositories


def test_unknown_commit_still_refuses(repositories):
    with pytest.raises(R.BindingRefused, match="SOURCE_REVISION_UNRESOLVED"):
        R._revision("0" * 40)


def test_malformed_revision_still_refuses(repositories):
    with pytest.raises(R.BindingRefused, match="SOURCE_REVISION_INVALID"):
        R._revision("HEAD")
