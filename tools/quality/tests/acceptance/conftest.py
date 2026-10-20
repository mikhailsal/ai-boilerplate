from pathlib import Path

import pytest

from quality.testkit.scratch import Project, create_project, output


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
