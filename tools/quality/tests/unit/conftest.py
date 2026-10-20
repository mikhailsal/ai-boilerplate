from pathlib import Path

import pytest

from quality.testkit.gitrepo import GitRepo


@pytest.fixture
def repo(tmp_path: Path) -> GitRepo:
    return GitRepo.create(tmp_path / "repo")
