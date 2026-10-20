"""R03: a candidate is judged by its own core, not by unstaged edits to the validator."""

from pathlib import Path

import pytest

from quality.testkit.scratch import CORE, Project, create_project, output, rules_of

HANDLER = "tools/quality/src/quality/cli/check_cmd.py"
# Redefines the handler of `quality check`, so the edited core returns `status` unread.
SABOTAGE = "\n\ndef run_check(args: object) -> int:\n    return {status}\n"


@pytest.fixture
def embedded(tmp_path: Path) -> Project:
    """Return a hooked project that embeds the core under test at tools/quality."""
    project = create_project(tmp_path / "project", core=True)
    result = project.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return project


def sabotage(project: Project, status: int) -> None:
    """Make the working-tree core's `check` return `status` without checking anything."""
    handler = project.path / HANDLER
    handler.write_text(handler.read_text() + SABOTAGE.format(status=status))


def test_unstaged_validator_edits_cannot_accept_a_violation(embedded: Project) -> None:
    first = embedded.head()
    sabotage(embedded, 0)
    embedded.write("app/src/app/core.py", "import os\n" + CORE)
    rejected = embedded.commit("unused import", "app/src/app/core.py")
    assert rejected.returncode == 1, output(rejected)
    assert "python.lint" in rules_of(rejected)
    assert embedded.head() == first
    # Staged, the edit is the candidate's own core; CI runs it from the commit.
    accepted = embedded.commit("edit the core", "app/src/app/core.py", HANDLER)
    assert accepted.returncode == 0, output(accepted)


def test_unstaged_validator_edits_cannot_block_a_clean_change(embedded: Project) -> None:
    first = embedded.head()
    sabotage(embedded, 1)
    embedded.write("README.md", "# Scratch project\n\nSee [agent instructions](AGENTS.md) first.\n")
    accepted = embedded.commit("clarify the readme", "README.md")
    assert accepted.returncode == 0, output(accepted)
    assert embedded.head() != first
    assert embedded.repo.git("status", "--porcelain") == f" M {HANDLER}\n"


def test_an_unstaged_core_lock_is_an_environment_error(embedded: Project) -> None:
    lock = embedded.path / "tools" / "quality" / "uv.lock"
    lock.write_text(lock.read_text() + "\n")
    result = embedded.quality("check")
    assert result.returncode == 3, output(result)
    assert rules_of(result) == {"core.environment"}
