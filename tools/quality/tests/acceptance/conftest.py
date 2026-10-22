import os
import shutil
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

import pytest

from quality.testkit import greetfixture, notesfixture
from quality.testkit.gitrepo import GitRepo
from quality.testkit.scratch import (
    Project,
    browser,
    create_project,
    dart,
    output,
    php,
    shared_caches,
    typescript,
)
from quality.toolchain import load_manifest

# Each of these runs several whole gates, so they go to the workers first
# instead of finishing last; the sort is stable, so every worker agrees.
LONGEST = frozenset({"test_template.py", "test_frontend_start.py"})
TEMPLATE = Path(__file__).resolve().parents[4]
# What a clone of the template leaves out: Git data and installed packages.
INSTALLED = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", "node_modules", ".dart_tool", "vendor"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    items.sort(key=lambda item: item.path.name not in LONGEST)


def _link_or_copy(source: str, target: str) -> None:
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _limited_cache(root: Path, tools: Iterable[str], shared: Iterable[str] = ()) -> dict[str, str]:
    """Return cache variables that reach only CPython, the `tools`, and the `shared` caches.

    uv ignores a linked interpreter directory, so the interpreters are copied,
    as hard links where the file system allows.
    """
    caches = shared_caches(os.environ)
    quality = Path(caches["XDG_CACHE_HOME"]) / "quality"
    toolchains = root / "quality" / "toolchains"
    interpreters = root / "quality" / "python"
    toolchains.mkdir(parents=True)
    interpreters.mkdir()
    manifest = load_manifest()
    for name in tools:
        entry = f"{name}-{manifest.tools[name].version}"
        (toolchains / entry).symlink_to(quality / "toolchains" / entry)
    for name in shared:
        (root / "quality" / name).symlink_to(quality / name)
    for interpreter in (quality / "python").glob("cpython-*"):
        if not interpreter.is_symlink():
            target = interpreters / interpreter.name
            shutil.copytree(interpreter, target, symlinks=True, copy_function=_link_or_copy)
    uv = caches.get("UV_CACHE_DIR") or str(Path(caches["XDG_CACHE_HOME"]) / "uv")
    return {"XDG_CACHE_HOME": str(root), "UV_CACHE_DIR": uv}


@pytest.fixture
def limited_cache() -> Callable[..., dict[str, str]]:
    """Return the function that builds a cache holding only some of the toolchains."""
    return _limited_cache


@pytest.fixture(scope="module")
def clone(tmp_path_factory: pytest.TempPathFactory) -> Project:
    """Return a committed copy of the template, shared by a module.

    The clone copies every file of the tree the test runs in, which is the
    candidate's snapshot under `./quality self-test`; run natively, untracked
    files of a working tree would become part of the template.
    """
    repo = GitRepo.create(tmp_path_factory.mktemp("clone") / "template")
    shutil.copytree(TEMPLATE, repo.path, symlinks=True, ignore=INSTALLED, dirs_exist_ok=True)
    repo.commit_all("use the template")
    return Project(repo)


@pytest.fixture
def export(clone: Project) -> Callable[..., Project]:
    """Return the function that exports a project from the clone."""

    def exported(target: Path, caches: Mapping[str, str] | None = None) -> Project:
        """Export into `target`; `caches` replaces the shared caches."""
        result = clone.quality("template", "export", str(target))
        assert result.returncode == 0, output(result)
        return Project(GitRepo(target, clone.repo.home), caches)

    return exported


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


@pytest.fixture(scope="module")
def counter(tmp_path_factory: pytest.TempPathFactory) -> Project:
    """Return a bootstrapped project with the browser counter `web`, shared by a module."""
    created = create_project(tmp_path_factory.mktemp("counter") / "project", browser())
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
