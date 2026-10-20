"""The installed tools and profile adapters a command runs with; nothing is downloaded."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from quality.adapters.native import ToolFailedError
from quality.adapters.python.environment import Environments, Uv
from quality.adapters.python.fixer import PythonFixer
from quality.adapters.python.profile import PythonProfile
from quality.adapters.python.provision import PythonSetup
from quality.adapters.typescript import environment as node_environment
from quality.adapters.typescript.fixer import TypeScriptFixer
from quality.adapters.typescript.profile import TypeScriptProfile
from quality.adapters.typescript.provision import TypeScriptSetup
from quality.cli.inventory_cmd import index_from
from quality.engine import ProfileAdapter, ProfileSetup, Tools
from quality.engine.fixes import ProfileFixer, worktree_entries
from quality.gitio import Candidate, Repository, revision, staged
from quality.policy import Profile
from quality.rules.coverage import ComponentCoverage
from quality.toolchain import (
    ManifestError,
    Tool,
    ToolchainError,
    cache_root,
    extra_path,
    install,
    load_manifest,
    locate,
    python_root,
)
from quality.toolchain.install import MISSING

# Ruff and Pyright are pinned by the core's own lockfile and installed beside its interpreter.
CORE_TOOLS = ("ruff", "pyright")
NODE = "node"


def pinned(name: str) -> Tool:
    """Return a tool of the manifest or raise ToolchainError."""
    try:
        return load_manifest().tools[name]
    except (ManifestError, KeyError) as error:
        raise ToolchainError(MISSING.diagnostic(f"toolchain manifest: {error}")) from error


def local_tools() -> Tools:
    """Locate the pinned tools of the common gates in the cache."""
    tool = pinned("gitleaks")
    root = cache_root()
    gitleaks = locate("gitleaks", tool, root)
    rules = extra_path("gitleaks", tool, root, "gitleaks.toml")
    if not rules.is_file():
        message = f"gitleaks rule set is not installed (expected {rules})"
        raise ToolchainError(MISSING.diagnostic(message))
    return Tools(python=Path(sys.executable), gitleaks=gitleaks, gitleaks_rules=rules)


def local_uv() -> Uv:
    """Locate the pinned uv and the directory of its managed interpreters."""
    return Uv(locate("uv", pinned("uv"), cache_root()), python_root())


def core_tool(name: str) -> Path:
    """Locate a tool installed in the core environment."""
    path = Path(sys.executable).parent / name
    if not (path.is_file() and os.access(path, os.X_OK)):
        message = f"{name} is not installed in the core environment (expected {path})"
        raise ToolchainError(MISSING.diagnostic(message))
    return path


def npm_pins() -> Mapping[str, str]:
    """Return the npm packages the TypeScript profile pins."""
    try:
        return load_manifest().packages.get("npm", {})
    except ManifestError as error:
        raise ToolchainError(MISSING.diagnostic(f"toolchain manifest: {error}")) from error


def npm_cache() -> Path:
    """Return the shared npm cache beside the toolchain cache."""
    return cache_root().parent / "npm"


def node_step(step: Callable[[str, Tool, Path], Path]) -> Callable[[], Path]:
    """Defer locating or installing the pinned Node until a TypeScript component needs it."""

    def run() -> Path:
        try:
            return step(NODE, pinned(NODE), cache_root())
        except ToolchainError as error:
            raise ToolFailedError(error.diagnostic) from error

    return run


def node_environments() -> node_environment.Environments:
    """Return the TypeScript environments, which locate the installed Node on first use."""
    return node_environment.Environments(node_step(locate), npm_cache())


def worktree_files(root: Path) -> list[str]:
    """List the working tree's tracked and untracked, not ignored, regular files."""
    return [entry.path for entry in worktree_entries(Repository.discover(root, os.environ))]


def local_profiles() -> Mapping[Profile, ProfileAdapter]:
    """Return the profile adapters of this build with their installed tools."""
    ruff, pyright = (core_tool(name) for name in CORE_TOOLS)
    python = PythonProfile(ruff=ruff, pyright=pyright, environments=Environments(local_uv()))
    typescript = TypeScriptProfile(node_environments(), npm_pins())
    return {Profile.PYTHON: python, Profile.TYPESCRIPT: typescript}


def local_setups() -> Mapping[Profile, ProfileSetup]:
    """Return what bootstrap and doctor use to provision and probe each profile."""
    typescript = TypeScriptSetup(node_step(locate), node_step(install), npm_cache(), npm_pins())
    return {Profile.PYTHON: PythonSetup(local_uv()), Profile.TYPESCRIPT: typescript}


def local_fixers() -> Mapping[Profile, ProfileFixer]:
    """Return the fixers of this build with their installed tools."""
    typescript = TypeScriptFixer(node_environments(), npm_pins(), worktree_files)
    return {Profile.PYTHON: PythonFixer(core_tool("ruff")), Profile.TYPESCRIPT: typescript}


def candidate_of(args: argparse.Namespace) -> tuple[Repository, Candidate]:
    """Return the repository and the candidate: `--rev`, or the index a hook selected."""
    repo = Repository.discover(Path.cwd(), os.environ)
    rev: str | None = args.rev
    if rev is not None:
        return repo, revision(repo, rev)
    return repo, staged(repo, index_from(os.environ, Path.cwd()))


def coverage_text(summaries: tuple[ComponentCoverage, ...]) -> str:
    """Describe the unit coverage of each tested component, one line each."""
    lines: list[str] = []
    for summary in summaries:
        branch = summary.branch.describe() if summary.branch is not None else "not measured"
        lines.append(
            f"unit coverage of {summary.component}: line {summary.line.describe()}, "
            f"branch {branch}, changed lines {summary.changed.describe()}\n"
        )
    return "".join(lines)


def coverage_json(summaries: tuple[ComponentCoverage, ...]) -> list[dict[str, object]]:
    """Return the unit coverage of each tested component as JSON-ready counters."""
    found: list[dict[str, object]] = []
    for summary in summaries:
        counters = {"line": summary.line, "branch": summary.branch, "changed": summary.changed}
        found.append(
            {
                "component": summary.component,
                **{
                    name: None if c is None else {"covered": c.covered, "total": c.total}
                    for name, c in counters.items()
                },
            }
        )
    return found
