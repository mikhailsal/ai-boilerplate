"""R10, P11, and A16: a project's life from the template export to four languages.

A copy of the candidate is the template clone. The project it exports is
bootstrapped twice and makes its first commit with a cache that holds only
the core's Python tooling, so a Python project never needs the toolchains of
the dormant helpers. With the shared caches, a change to a dormant helper
runs that helper's checks, and the project then adds a TypeScript, a Dart, a
PHP, and a second Python component in one commit through the hook. Each step
depends on the one before it, so the steps are chained module fixtures.

The clone copies every file of the tree the test runs in, which is the
candidate's snapshot under `./quality self-test`; run natively, untracked
files of a working tree would become part of the template.
"""

import os
import shutil
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class Step:
    """A project after one step of its life, with what the step printed."""

    project: Project
    results: dict[str, Completed]


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


@pytest.fixture(scope="module")
def bootstrapped(clone: Project, tmp_path_factory: pytest.TempPathFactory) -> Step:
    target = clone.path.parent / "project"
    exported = clone.quality("template", "export", str(target))
    assert exported.returncode == 0, output(exported)
    caches = python_only_cache(tmp_path_factory.mktemp("python-only"))
    project = Project(GitRepo(target, clone.repo.home), caches)
    first = project.quality("bootstrap")
    assert first.returncode == 0, output(first)
    local = project.hook("pre-commit.local")
    local.write_text(LOCAL_HOOK)
    local.chmod(0o755)
    project.write("README.md", "# Edited by the user\n")
    hook = project.hook("pre-commit").read_bytes()
    second = project.quality("bootstrap")
    assert second.returncode == 0, output(second)
    assert project.hook("pre-commit").read_bytes() == hook
    assert local.read_text() == LOCAL_HOOK
    assert (project.path / "README.md").read_text() == "# Edited by the user\n"
    project.repo.git("checkout", "--", "README.md")
    return Step(project, {"export": exported, "first": first, "second": second})


@pytest.fixture(scope="module")
def started(bootstrapped: Step) -> Step:
    project = bootstrapped.project
    python_component(project, "libs/pricing", "pricing")
    added = add(project, "libs/pricing")
    project.repo.git("add", "quality.toml", "libs/pricing")
    setup = project.quality("bootstrap")
    assert setup.returncode == 0, output(setup)
    commit = project.commit("Add the pricing library", "quality.toml", "libs/pricing")
    assert commit.returncode == 0, output(commit)
    return Step(project, {"add": added, "bootstrap": setup, "commit": commit})


@pytest.fixture(scope="module")
def helper_changed(started: Step) -> Step:
    project = Project(started.project.repo)
    source = project.path / HELPER_SOURCE
    original = source.read_text(encoding="utf-8")
    source.write_text(original.replace(HELPER_COMMENT, f"// The n{HELPER_COMMENT[4:]}", 1))
    project.repo.git("add", HELPER_SOURCE)
    setup = project.quality("bootstrap")
    checked = project.quality("check")
    project.repo.git("restore", "--staged", "--worktree", HELPER_SOURCE)
    return Step(project, {"bootstrap": setup, "check": checked})


@pytest.fixture(scope="module")
def grown(helper_changed: Step) -> Step:
    project = helper_changed.project
    typescript_project(project.path / "apps/web", name="web")
    dart_project(project.path / "apps/calc", name="calc")
    php_project(project.path / "apps/shop")
    python_component(project, "libs/tax", "tax")
    for root in ("apps/web", "apps/calc", "apps/shop", "libs/tax"):
        add(project, root)
    project.repo.git("add", "quality.toml", "apps", "libs/tax")
    setup = project.quality("bootstrap")
    assert setup.returncode == 0, output(setup)
    commit = project.commit("Add a component of every profile", "quality.toml", "apps", "libs")
    return Step(project, {"bootstrap": setup, "commit": commit})


def test_the_export_bootstraps_twice_with_only_the_python_tooling(bootstrapped: Step) -> None:
    for name in ("first", "second"):
        text = output(bootstrapped.results[name])
        for helper in HELPERS:
            assert f"quality-{helper}-helper: dormant, so its {helper} tools wait" in text, text
    cache = Path(bootstrapped.project.environ()["XDG_CACHE_HOME"]) / "quality" / "toolchains"
    manifest = load_manifest()
    expected = sorted(f"{name}-{manifest.tools[name].version}" for name in CORE_TOOLS)
    assert sorted(entry.name for entry in cache.iterdir()) == expected
    assert not (bootstrapped.project.repo.home / ".local").exists()


def test_the_first_commit_adds_a_python_component_through_the_hook(started: Step) -> None:
    text = output(started.results["commit"])
    assert "unit coverage of pricing: line 100.00%" in text, text
    assert "unit coverage of quality-core" in text
    assert "-helper" not in text
    assert (started.project.path / ".git" / "local-ran").exists()
    log = started.project.repo.git("log", "--format=%s")
    assert log == "Add the pricing library\nStart from the quality template\n"


def test_changing_a_dormant_helper_runs_its_own_checks(helper_changed: Step) -> None:
    setup = output(helper_changed.results["bootstrap"])
    assert helper_changed.results["bootstrap"].returncode == 0, setup
    assert "quality-typescript-helper: dormant" not in setup
    assert "quality-dart-helper: dormant, so its dart tools wait" in setup
    checked = helper_changed.results["check"]
    assert checked.returncode == 0, output(checked)
    assert "unit coverage of quality-typescript-helper" in output(checked)
    assert "unit coverage of quality-dart-helper" not in output(checked)


def test_a16_a_clean_four_language_project_passes_the_hook(grown: Step) -> None:
    commit = grown.results["commit"]
    text = output(commit)
    assert commit.returncode == 0, text
    for component in ("pricing", "tax", "web", "calc", "shop"):
        assert f"unit coverage of {component}: line 100.00%" in text, component
    for helper in HELPERS:
        assert f"unit coverage of quality-{helper}-helper" in text, helper
    assert "dormant" not in output(grown.results["bootstrap"])
