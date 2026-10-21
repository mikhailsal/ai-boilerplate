"""The template as a user receives it: a fresh clone runs the core through `./quality`.

The candidate's files are copied without installed environments or packages,
committed to a new repository, and driven through the root launcher symlink,
which prepares the pinned core offline from the shared caches.
"""

import shutil
from pathlib import Path

import pytest

from quality.testkit.gitrepo import GitRepo
from quality.testkit.scratch import Project, output

TEMPLATE = Path(__file__).resolve().parents[4]
INSTALLED = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", "node_modules", ".dart_tool", "vendor"
)


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Project:
    repo = GitRepo.create(tmp_path_factory.mktemp("export") / "template")
    shutil.copytree(TEMPLATE, repo.path, symlinks=True, ignore=INSTALLED, dirs_exist_ok=True)
    repo.commit_all("use the template")
    return Project(repo)


def test_the_exported_template_starts_and_answers(template: Project) -> None:
    version = template.quality("--version")
    assert version.returncode == 0, output(version)
    assert version.stdout_text().startswith("quality ")
    explained = template.quality("explain", "tests.failed")
    assert explained.returncode == 0, output(explained)
    assert explained.stdout_text().startswith("tests.failed: Tests failed")


def test_the_exported_template_validates_its_policy(template: Project) -> None:
    validated = template.quality("policy", "validate")
    assert validated.returncode == 0, output(validated)


def test_the_exported_template_lists_its_scenarios(template: Project) -> None:
    listed = template.quality("scenarios")
    assert listed.returncode == 0, output(listed)
    assert "quality-core" in listed.stdout_text()


def test_a_usage_error_exits_with_status_2(template: Project) -> None:
    unknown = template.quality("explain", "no.such-rule")
    assert unknown.returncode == 2, output(unknown)
