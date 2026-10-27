"""R10, P11, and A16: a project's life from the template export to four languages.

A copy of the candidate is the template clone, and each test exports its own
project from it, so the tests run independently. With a cache that holds only
the core's Python tooling, an export bootstraps twice and makes its first
commit with a Python component, so a Python project never needs the
toolchains of the dormant helpers. With the shared caches, a change to a
dormant helper runs that helper's checks, and a project adds a component of
every profile in one commit through the hook.
"""

from collections.abc import Callable
from pathlib import Path

from quality.process import Completed
from quality.testkit.dartproject import dart_project
from quality.testkit.phpproject import php_project
from quality.testkit.pythonproject import CORE_PYTHON, python_project
from quality.testkit.scratch import CORE, TESTS, Project, output
from quality.testkit.typescriptproject import typescript_project
from quality.toolchain import load_manifest

type Export = Callable[..., Project]
type Caches = Callable[..., dict[str, str]]

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


def local_hook(project: Project) -> Path:
    """Install the user's own `pre-commit.local` hook, which marks that it ran."""
    local = project.hook("pre-commit.local")
    local.write_text(LOCAL_HOOK)
    local.chmod(0o755)
    return local


def test_the_export_bootstraps_twice_with_only_the_python_tooling(
    export: Export, limited_cache: Caches, tmp_path: Path
) -> None:
    caches = limited_cache(tmp_path / "caches", CORE_TOOLS)
    project = export(tmp_path / "project", caches)
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
    export: Export, limited_cache: Caches, tmp_path: Path
) -> None:
    project = export(tmp_path / "project", limited_cache(tmp_path / "caches", CORE_TOOLS))
    bootstrap(project)
    local_hook(project)
    python_component(project, "libs/pricing", "pricing")
    pin = project.path / "libs/pricing/.python-version"
    pin.unlink()
    add(project, "libs/pricing")
    assert pin.read_text() == CORE_PYTHON.read_text()
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


def test_changing_a_dormant_helper_runs_its_own_checks(export: Export, tmp_path: Path) -> None:
    project = export(tmp_path / "project")
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


def test_a16_a_clean_four_language_project_passes_the_hook(export: Export, tmp_path: Path) -> None:
    project = export(tmp_path / "project")
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
    for helper in HELPERS:
        assert f"quality-{helper}-helper: dormant" not in setup, setup
    # The shipped browser example runs only when it changes, so no Chromium.
    assert "example-web: dormant, so its typescript tools wait" in setup, setup
    assert "Chromium" not in setup, setup
    commit = project.commit("Add a component of every profile", "quality.toml", "apps", "libs")
    text = output(commit)
    assert commit.returncode == 0, text
    for component in ("pricing", "tax", "web", "calc", "shop"):
        assert f"unit coverage of {component}: line 100.00%" in text, component
    for helper in HELPERS:
        assert f"unit coverage of quality-{helper}-helper" in text, helper
