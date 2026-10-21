from pathlib import Path

import pytest

from quality.testkit import greetfixture, notesfixture
from quality.testkit.scratch import Project, create_project, dart, output, php, typescript

# Each of these runs several whole gates, so they go to the workers first
# instead of finishing last; the sort is stable, so every worker agrees.
LONGEST = "test_template.py"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    items.sort(key=lambda item: item.path.name != LONGEST)


@pytest.fixture
def project(tmp_path: Path) -> Project:
    """Return a committed project without hooks."""
    return create_project(tmp_path / "project")


@pytest.fixture
def hooked(project: Project) -> Project:
    """Return a committed project after `quality bootstrap` installed its pre-commit hook."""
    result = project.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return project


@pytest.fixture
def web(tmp_path: Path) -> Project:
    """Return a bootstrapped project with one TypeScript component, `web`."""
    created = create_project(tmp_path / "project", typescript("web"))
    result = created.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return created


@pytest.fixture
def calc(tmp_path: Path) -> Project:
    """Return a bootstrapped project with one Dart component, `calc`."""
    created = create_project(tmp_path / "project", dart("calc"))
    result = created.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return created


@pytest.fixture
def shop(tmp_path: Path) -> Project:
    """Return a bootstrapped project with one PHP component, `shop`."""
    created = create_project(tmp_path / "project", php("shop"))
    result = created.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return created


@pytest.fixture
def greet(tmp_path: Path) -> Project:
    """Return a bootstrapped project with the `greet` reference fixture."""
    files = {"greet": greetfixture.FILES}
    created = create_project(tmp_path / "project", greetfixture.SPEC, files=files)
    result = created.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return created


@pytest.fixture
def notes(tmp_path: Path) -> Project:
    """Return a bootstrapped project with the `notes` reference fixture."""
    files = {"notes": notesfixture.FILES}
    created = create_project(tmp_path / "project", notesfixture.SPEC, files=files)
    result = created.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return created
