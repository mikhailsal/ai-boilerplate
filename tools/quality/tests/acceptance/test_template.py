"""R10, P11, and A16: a project's life from the template export to four languages.

A copy of the candidate is the template clone, and each test exports its own
project from it, so the tests run independently. With a cache that holds only
the core's Python tooling, an export bootstraps twice and makes its first
commit with a Python component, so a Python project never needs the
toolchains of the dormant helpers. With the shared caches, a change to a
dormant helper runs that helper's checks, and a project adds a component of
every profile in one commit through the hook.

The clone copies every file of the tree the test runs in, which is the
candidate's snapshot under `./quality self-test`; run natively, untracked
files of a working tree would become part of the template.
"""

import os
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

from quality.process import Completed
from quality.testkit.dartproject import dart_project
from quality.testkit.gitrepo import GitRepo
from quality.testkit.phpproject import php_project
from quality.testkit.pythonproject import python_project
from quality.testkit.scratch import CORE, TESTS, Project, output, shared_caches
from quality.testkit.typescriptproject import typescript_project
from quality.toolchain import load_manifest

TEMPLATE = Path(__file__).resolve().parents[4]
INSTALLED = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", "node_modules", ".dart_tool", "vendor"
)
# The pinned tools of the core's common gates; no profile toolchain among them.
CORE_TOOLS = ("uv", "gitleaks", "actionlint", "osv-scanner")
HELPERS = ("typescript", "dart", "php")
LOCAL_HOOK = '#!/bin/sh\ntouch "$(git rev-parse --git-dir)/local-ran"\n'
HELPER_SOURCE = "tools/quality/helpers/typescript/src/naming.ts"
HELPER_COMMENT = "// Names of functions and of the scopes that qualify them."
PURE = "Pure calculations without a boundary."


def python_component(project: Project, root: str, name: str) -> None:
    files = {
        f"src/{name}/__init__.py": "",
        f"src/{name}/core.py": CORE,
        f"tests/test_{name}.py": TESTS.format(name=name),
    }
    python_project(project.path / root, files, name=name)


def add(project: Project, root: str) -> Completed:
    added = project.quality("component", "add", root, "--no-boundary-reason", PURE)
    assert added.returncode == 0, output(added)
    return added


def bootstrap(project: Project) -> Completed:
    result = project.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return result


def link_or_copy(source: str, target: str) -> None:
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def python_only_cache(root: Path) -> dict[str, str]:
    """Return cache variables that reach only uv, CPython, and the core's tools.

    uv ignores a linked interpreter directory, so the interpreters are copied,
    as hard links where the file system allows.
    """
    shared = shared_caches(os.environ)
    quality = Path(shared["XDG_CACHE_HOME"]) / "quality"
    toolchains = root / "quality" / "toolchains"
    interpreters = root / "quality" / "python"
    toolchains.mkdir(parents=True)
    interpreters.mkdir()
    manifest = load_manifest()
    for name in CORE_TOOLS:
        entry = f"{name}-{manifest.tools[name].version}"
        (toolchains / entry).symlink_to(quality / "toolchains" / entry)
    for interpreter in (quality / "python").glob("cpython-*"):
        if not interpreter.is_symlink():
            target = interpreters / interpreter.name
            shutil.copytree(interpreter, target, symlinks=True, copy_function=link_or_copy)
    uv = shared.get("UV_CACHE_DIR") or str(Path(shared["XDG_CACHE_HOME"]) / "uv")
    return {"XDG_CACHE_HOME": str(root), "UV_CACHE_DIR": uv}


@pytest.fixture(scope="module")
def clone(tmp_path_factory: pytest.TempPathFactory) -> Project:
    repo = GitRepo.create(tmp_path_factory.mktemp("clone") / "template")
    shutil.copytree(TEMPLATE, repo.path, symlinks=True, ignore=INSTALLED, dirs_exist_ok=True)
    repo.commit_all("use the template")
    return Project(repo)


def export(clone: Project, target: Path, caches: Mapping[str, str] | None = None) -> Project:
    """Export a project from the clone; `caches` replaces the shared caches."""
    exported = clone.quality("template", "export", str(target))
    assert exported.returncode == 0, output(exported)
    return Project(GitRepo(target, clone.repo.home), caches)


def local_hook(project: Project) -> Path:
    """Install the user's own `pre-commit.local` hook, which marks that it ran."""
    local = project.hook("pre-commit.local")
    local.write_text(LOCAL_HOOK)
    local.chmod(0o755)
    return local


def test_the_export_bootstraps_twice_with_only_the_python_tooling(
    clone: Project, tmp_path: Path
) -> None:
    caches = python_only_cache(tmp_path / "caches")
    project = export(clone, tmp_path / "project", caches)
    first = bootstrap(project)
    local = local_hook(project)
    project.write("README.md", "# Edited by the user\n")
    hook = project.hook("pre-commit").read_bytes()
    second = bootstrap(project)
    assert project.hook("pre-commit").read_bytes() == hook
    assert local.read_text() == LOCAL_HOOK
    assert (project.path / "README.md").read_text() == "# Edited by the user\n"
    for result in (first, second):
        text = output(result)
        for helper in HELPERS:
            assert f"quality-{helper}-helper: dormant, so its {helper} tools wait" in text, text
    cache = Path(caches["XDG_CACHE_HOME"]) / "quality" / "toolchains"
    manifest = load_manifest()
    expected = sorted(f"{name}-{manifest.tools[name].version}" for name in CORE_TOOLS)
    assert sorted(entry.name for entry in cache.iterdir()) == expected
    assert not (project.repo.home / ".local").exists()


def test_the_first_commit_adds_a_python_component_through_the_hook(
    clone: Project, tmp_path: Path
) -> None:
    project = export(clone, tmp_path / "project", python_only_cache(tmp_path / "caches"))
    bootstrap(project)
    local_hook(project)
    python_component(project, "libs/pricing", "pricing")
    add(project, "libs/pricing")
    project.repo.git("add", "quality.toml", "libs/pricing")
    bootstrap(project)
    commit = project.commit("Add the pricing library", "quality.toml", "libs/pricing")
    text = output(commit)
    assert commit.returncode == 0, text
    assert "unit coverage of pricing: line 100.00%" in text, text
    assert "unit coverage of quality-core" in text
    assert "-helper" not in text
    assert (project.path / ".git" / "local-ran").exists()
    log = project.repo.git("log", "--format=%s")
    assert log == "Add the pricing library\nStart from the quality template\n"


def test_changing_a_dormant_helper_runs_its_own_checks(clone: Project, tmp_path: Path) -> None:
    project = export(clone, tmp_path / "project")
    bootstrap(project)
    source = project.path / HELPER_SOURCE
    original = source.read_text(encoding="utf-8")
    source.write_text(original.replace(HELPER_COMMENT, f"// The n{HELPER_COMMENT[4:]}", 1))
    project.repo.git("add", HELPER_SOURCE)
    setup = output(bootstrap(project))
    assert "quality-typescript-helper: dormant" not in setup
    assert "quality-dart-helper: dormant, so its dart tools wait" in setup
    checked = project.quality("check")
    assert checked.returncode == 0, output(checked)
    assert "unit coverage of quality-typescript-helper" in output(checked)
    assert "unit coverage of quality-dart-helper" not in output(checked)


def test_a16_a_clean_four_language_project_passes_the_hook(clone: Project, tmp_path: Path) -> None:
    project = export(clone, tmp_path / "project")
    bootstrap(project)
    python_component(project, "libs/pricing", "pricing")
    python_component(project, "libs/tax", "tax")
    typescript_project(project.path / "apps/web", name="web")
    dart_project(project.path / "apps/calc", name="calc")
    php_project(project.path / "apps/shop")
    for root in ("libs/pricing", "libs/tax", "apps/web", "apps/calc", "apps/shop"):
        add(project, root)
    project.repo.git("add", "quality.toml", "apps", "libs")
    setup = output(bootstrap(project))
    assert "dormant" not in setup
    commit = project.commit("Add a component of every profile", "quality.toml", "apps", "libs")
    text = output(commit)
    assert commit.returncode == 0, text
    for component in ("pricing", "tax", "web", "calc", "shop"):
        assert f"unit coverage of {component}: line 100.00%" in text, component
    for helper in HELPERS:
        assert f"unit coverage of quality-{helper}-helper" in text, helper
