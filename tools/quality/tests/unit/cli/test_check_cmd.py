import json
from pathlib import Path

import pytest

from quality.cli import check_cmd
from quality.cli.main import main
from quality.testkit.gitrepo import GitRepo
from quality.testkit.policies import policy_toml
from quality.toolchain import ManifestError, cache_root, load_manifest

README = "# Project\n\nSee [agent instructions](AGENTS.md).\n"
AGENTS = "# Agents\n\nRun `quality check` before committing.\n"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GitRepo:
    cache = cache_root().parent.parent
    repo = GitRepo.create(tmp_path / "repo")
    repo.write("quality.toml", policy_toml())
    repo.write("README.md", README)
    repo.write("AGENTS.md", AGENTS)
    repo.write("src/app/__init__.py", "")
    repo.write("tests/test_app.py", "def test_ok():\n    pass\n")
    repo.git("add", "-A")
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(repo.home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    monkeypatch.chdir(repo.path)
    return repo


def test_the_staged_candidate_passes(project: GitRepo, capsys: pytest.CaptureFixture[str]) -> None:
    project.write("src/app/unstaged.py", "def broken(:\n")
    assert main(["check"]) == 0
    assert capsys.readouterr().out == (
        "PASSED: 0 error(s), 0 warning(s)\nchecked 5 files; 0 findings covered by exceptions\n"
    )


def test_violations_fail_with_a_json_report(
    project: GitRepo, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("src/app/a.py", "x = 1  # noqa\n")
    project.git("add", "-A")
    assert main(["check", "--staged", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["command"] == "check"
    assert (report["files"], report["excepted"]) == (6, 0)
    assert [d["rule"] for d in report["diagnostics"]] == ["suppressions.inline"]


def test_a_revision_is_checked(project: GitRepo, capsys: pytest.CaptureFixture[str]) -> None:
    project.git("commit", "-q", "-m", "first")
    project.write("AGENTS.md", "# Agents\n\nRun `quality nonsense`.\n")
    project.git("add", "-A")
    assert main(["check", "--rev", "HEAD"]) == 0
    assert main(["check"]) == 1
    assert "'quality nonsense' is not a command" in capsys.readouterr().out


def test_missing_tools_are_environment_errors(
    project: GitRepo,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = tmp_path / "empty-cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(empty))
    assert main(["check"]) == 3
    assert "(tools.missing)" in capsys.readouterr().out
    tool = load_manifest().tools["gitleaks"]
    binary = empty / "quality" / "toolchains" / f"gitleaks-{tool.version}" / tool.binary
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    assert main(["check"]) == 3
    assert "gitleaks rule set is not installed" in capsys.readouterr().out


def test_a_broken_manifest_is_an_environment_error(
    project: GitRepo, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> object:
        msg = "bad manifest"
        raise ManifestError(msg)

    monkeypatch.setattr(check_cmd, "load_manifest", broken)
    assert main(["check"]) == 3
    assert "toolchain manifest: bad manifest (tools.missing)" in capsys.readouterr().out


def test_outside_a_repository_is_an_environment_error(
    project: GitRepo,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    assert main(["check"]) == 3
    assert "(git.failed)" in capsys.readouterr().out
