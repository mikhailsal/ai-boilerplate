"""Bounded native template adoption observations, with an experimental overlay.

This is an automated Python-profile exercise, not a novice usability study or
product resource-policy integration. All subprocesses enter the kernel leaf.
"""

from __future__ import annotations

import json
import os
import time
import tomllib
import uuid
from collections.abc import Callable
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_kernel
from tests.acceptance.rl00bc.rl00bc_errors import expired, unavailable


def _component_files(root: Path, version: str, versions: dict[str, str]) -> None:
    names = ("coverage", "pytest", "pytest-cov")
    series = ".".join(version.split(".")[:2])
    pins = ", ".join(f'"{name}=={versions[name]}"' for name in names)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "pricing"\nversion = "0.1.0"\nrequires-python = "=={series}.*"\n'
        f"dependencies = []\n\n[dependency-groups]\ndev = [{pins}]\n"
        "\n[tool.uv]\npackage = false\n\n[tool.ruff]\nline-length = 100\n"
        '\n[tool.ruff.lint]\nselect = ["E", "F", "I"]\n'
        '\n[tool.pyright]\ntypeCheckingMode = "strict"\n'
        '\n[tool.pytest.ini_options]\npythonpath = ["src"]\n',
        encoding="utf-8",
    )
    (root / ".python-version").write_text(version + "\n", encoding="utf-8")
    (root / "src/pricing/__init__.py").write_text("", encoding="utf-8")
    (root / "src/pricing/core.py").write_text(
        '"""Small adoption fixture."""\n\n\ndef sign(value: int) -> int:\n'
        "    return -1 if value < 0 else 1\n",
        encoding="utf-8",
    )
    (root / "tests/test_pricing.py").write_text(
        '"""Exercise the fixture."""\n\nfrom pricing.core import sign\n\n\n'
        "def test_sign() -> None:\n"
        "    assert sign(-3) == -1\n    assert sign(4) == 1\n",
        encoding="utf-8",
    )


def _component(project: Path) -> None:
    """Build a locked tiny Python component from the exported core lock."""
    core = project / "tools/quality"
    header, *raw = (core / "uv.lock").read_text(encoding="utf-8").split("\n[[package]]\n")
    blocks = {str(tomllib.loads(block)["name"]): block for block in raw}
    names = ("coverage", "pytest", "pytest-cov")
    versions = {name: str(tomllib.loads(blocks[name])["version"]) for name in names}
    pending: list[str] = list(names)
    found: set[str] = set()
    while pending:
        name = pending.pop()
        if name not in found:
            found.add(name)
            pending.extend(
                str(dep["name"]) for dep in tomllib.loads(blocks[name]).get("dependencies", [])
            )
    root = project / "libs/pricing"
    (root / "src/pricing").mkdir(parents=True)
    (root / "tests").mkdir()
    version = (core / ".python-version").read_text(encoding="utf-8").strip()
    _component_files(root, version, versions)
    requirements = "".join(
        f'    {{ name = "{name}", specifier = "=={versions[name]}" }},\n' for name in names
    )
    dependencies = "".join(f'    {{ name = "{name}" }},\n' for name in names)
    blocks["pricing"] = (
        f'name = "pricing"\nversion = "0.1.0"\nsource = {{ virtual = "." }}\n'
        f"\n[package.dev-dependencies]\ndev = [\n{dependencies}]\n"
        f"\n[package.metadata]\n\n[package.metadata.requires-dev]\ndev = [\n{requirements}]\n"
    )
    (root / "uv.lock").write_text(
        header + "".join("\n[[package]]\n" + blocks[name] for name in sorted(found | {"pricing"})),
        encoding="utf-8",
    )


def _exports(root: Path, repo: Path, require: Callable[[str, list[str], Path], None]) -> None:
    template, old, project, new = (
        root / name for name in ("template-source", "template-old", "project", "template-new")
    )
    git = "/usr/bin/git"
    require("clone-template", [git, "clone", "--no-hardlinks", str(repo), str(template)], root)
    quality = str(template / "quality")
    require("source-old-revision", [git, "rev-parse", "HEAD"], template)
    require("export-old", [quality, "template", "export", str(old)], template)
    require("export-project", [quality, "template", "export", str(project)], template)
    readme = template / "README.md"
    marker = "\n<!-- RL00 lifecycle fixture: template update -->\n"
    readme.write_text(readme.read_text(encoding="utf-8") + marker, encoding="utf-8")
    require("stage-template-update", [git, "add", "README.md"], template)
    require(
        "commit-template-update", [git, "commit", "-m", "Add lifecycle fixture marker"], template
    )
    require("source-new-revision", [git, "rev-parse", "HEAD"], template)
    require("export-new", [quality, "template", "export", str(new)], template)


def _onboard(project: Path, require: Callable[[str, list[str], Path], None]) -> str:
    git = "/usr/bin/git"
    require("bootstrap-after-export", [str(project / "quality"), "bootstrap"], project)
    require("bootstrap-warm", [str(project / "quality"), "bootstrap"], project)
    _component(project)
    customization = project / "libs/pricing/src/pricing/core.py"
    custom_text = customization.read_text(encoding="utf-8").replace(
        "Small adoption fixture.", "Downstream customized pricing fixture."
    )
    customization.write_text(custom_text, encoding="utf-8")
    require(
        "component-add",
        [
            str(project / "quality"),
            "component",
            "add",
            "libs/pricing",
            "--no-boundary-reason",
            "Pure calculations without a boundary.",
        ],
        project,
    )
    require("stage-component", [git, "add", "quality.toml", "libs/pricing"], project)
    require("bootstrap-component", [str(project / "quality"), "bootstrap"], project)
    require("native-check", [str(project / "quality"), "check"], project)
    require(
        "first-protected-own-test",
        [str(project / "quality"), "test", "--component", "pricing"],
        project,
    )
    require("commit-component", [git, "commit", "-m", "Add pricing fixture"], project)
    return custom_text


def _update(
    root: Path, custom_text: str, gaps: list[str], require: Callable[[str, list[str], Path], None]
) -> None:
    project, old, new = root / "project", root / "template-old", root / "template-new"
    git = "/usr/bin/git"
    branch = str(
        tomllib.loads((project / "quality.toml").read_text(encoding="utf-8"))["repository"].get(
            "default_branch", "main"
        )
    )
    require("fetch-old", [git, "fetch", str(old), f"{branch}:template-old"], project)
    require("fetch-new", [git, "fetch", str(new), f"{branch}:template-new"], project)
    patch = root / "update.patch"
    require(
        "update-diff",
        [git, "diff", "--binary", f"--output={patch}", "template-old", "template-new"],
        project,
    )
    if patch.stat().st_size == 0:
        gaps.append(
            "Old and new exports have no difference; update and rollback cannot be demonstrated."
        )
        return
    marker = "\n<!-- RL00 lifecycle fixture: template update -->\n"
    customization = project / "libs/pricing/src/pricing/core.py"
    require("update-apply", [git, "apply", "--3way", str(patch)], project)
    if marker not in (project / "README.md").read_text(encoding="utf-8"):
        unavailable("updated export marker missing")
    if customization.read_text(encoding="utf-8") != custom_text:
        unavailable("update changed downstream customization")
    require("update-bootstrap", [str(project / "quality"), "bootstrap"], project)
    require("update-check", [str(project / "quality"), "check", "--all"], project)
    require("rollback-apply", [git, "apply", "--3way", "--reverse", str(patch)], project)
    if marker in (project / "README.md").read_text(encoding="utf-8"):
        unavailable("rollback retained update marker")
    if customization.read_text(encoding="utf-8") != custom_text:
        unavailable("rollback changed downstream customization")
    require("rollback-check", [str(project / "quality"), "check", "--all"], project)
    require("rollback-diff", [git, "diff", "--cached", "--exit-code"], project)


class _Runner:
    def __init__(self, work: Group, env: dict[str, str], output: Path, deadline: int) -> None:
        self.work, self.env, self.output, self.deadline = work, env, output, deadline
        self.phases: dict[str, object] = {}
        self.active = 0.0

    def require(self, name: str, argv: list[str], cwd: Path) -> None:
        try:
            remaining = (self.deadline - time.monotonic_ns()) / 1e9
            if remaining <= 3:
                expired("original deadline exhausted")
            result = rl00bc_kernel.execute(
                self.work,
                argv,
                cwd,
                self.env,
                self.output / name,
                memory_mib=3072,
                tasks=256,
                native_seconds=remaining,
                ancestor_deadline_ns=self.deadline,
            )
            self.phases[name] = {
                "argv": argv,
                "cwd": str(cwd),
                "evidence": str(self.output / name / "result.json"),
                "success": result.get("success"),
                "cause": result.get("cause"),
                "native_status": result.get("native_status"),
                "cleanup_complete": result.get("cleanup_complete"),
                "elapsed_seconds": result.get("elapsed_seconds"),
            }
            elapsed = result.get("elapsed_seconds")
            if not isinstance(elapsed, int | float) or isinstance(elapsed, bool):
                unavailable("kernel elapsed time unavailable")
            self.active += float(elapsed)
            if not result.get("success") or not result.get("cleanup_complete"):
                unavailable(f"{name} did not complete successfully")
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            if name not in self.phases:
                self.phases[name] = {
                    "argv": argv,
                    "cwd": str(cwd),
                    "error": f"{type(error).__name__}: {error}",
                }
            raise


def _environment(home: Path, environment: dict[str, str]) -> dict[str, str]:
    cache = home / ".cache"
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(home),
        "XDG_CACHE_HOME": str(cache),
        "UV_CACHE_DIR": str(cache / "uv"),
        "CI": "1",
        "LANG": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_NAME": "RL00 fixture",
        "GIT_AUTHOR_EMAIL": "rl00@example.invalid",
        "GIT_COMMITTER_NAME": "RL00 fixture",
        "GIT_COMMITTER_EMAIL": "rl00@example.invalid",
    }
    for key in ("RL00_PYTHON", "RL00_CHILD_PYTHON"):
        if key in environment:
            env[key] = environment[key]
    return env


REQUIRED_GAPS = [
    "Human understanding, administrator wait and novice usability are unmeasured.",
    ("Only the Python onboarding fixture is exercised; other profile adoption remains unproved."),
    (
        "The standalone experimental kernel overlay is not integrated into "
        "exported quality or hooks."
    ),
    (
        "Missing-delegation failure is unrun; actual host provisioning is "
        "a separate parent-mode observation."
    ),
    (
        "The update fixture changes an exported document, "
        "not a matched resource-policy core or schema."
    ),
]


def _report(runner: _Runner, project: Path, gaps: list[str], started: int) -> dict[str, object]:
    gaps.extend(REQUIRED_GAPS)
    return {
        "phases": runner.phases,
        "required_gaps": gaps,
        "fixture": str(project),
        "source_revisions": {
            "old": "scratch clone initial HEAD; see source-old-revision log",
            "new": "scratch clone fixture commit; see source-new-revision log",
        },
        "cache": {
            "initial": "fresh isolated HOME and XDG/uv caches before export",
            "bootstrap_after_export": "cache may have been populated by template exports",
            "warm": "same cache after first project bootstrap",
            "network_downloads": "see bounded bootstrap logs; not separately counted",
        },
        "timing": {
            "total_seconds": (time.monotonic_ns() - started) / 1e9,
            "active_command_seconds": runner.active,
            "human_wait_seconds": None,
            "administrator_wait_seconds": None,
            "understanding_seconds": None,
        },
        "limits": {"memory_mib": 3072, "tasks": 256, "ancestor_deadline_ns": runner.deadline},
        "protection": (
            "experimental standalone overlay only; unmodified export and hooks "
            "do not enforce resource policy"
        ),
        "provisioning": "parent service supplies prepared or administrator-required host mode",
        "profile": "python",
        "result_understood_by_human": None,
    }


def adopt(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    environment: dict[str, str],
    *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Exercise native export, onboarding, update and rollback under one deadline."""
    started = time.monotonic_ns()
    repo, scratch, output = repo.absolute(), scratch.absolute(), output.absolute()
    scratch.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=False)
    root = scratch / f"adoption-{uuid.uuid4().hex}"
    root.mkdir()
    home = root / "home"
    home.mkdir()
    runner = _Runner(work, _environment(home, environment), output, ancestor_deadline_ns)
    phases = runner.phases
    gaps: list[str] = []

    project = root / "project"
    phases["missing_delegation"] = {
        "status": "unrun",
        "reason": (
            "An actual undelegated branch was not provided; simulated preflight is not proof."
        ),
    }
    try:
        _exports(root, repo, runner.require)
        custom_text = _onboard(project, runner.require)
        _update(root, custom_text, gaps, runner.require)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        gaps.append(f"Native adoption stopped: {type(error).__name__}: {error}")
    result = _report(runner, project, gaps, started)
    (output / "adoption.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return result
