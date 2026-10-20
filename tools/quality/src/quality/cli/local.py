"""The installed tools and profile adapters a command runs with; nothing is downloaded."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from quality.adapters.python.environment import Environments, Uv
from quality.adapters.python.fixer import PythonFixer
from quality.adapters.python.profile import PythonProfile
from quality.adapters.python.provision import PythonSetup
from quality.cli.inventory_cmd import index_from
from quality.engine import ProfileAdapter, ProfileSetup, Tools
from quality.engine.fixes import ProfileFixer
from quality.gitio import Candidate, Repository, revision, staged
from quality.policy import Profile
from quality.rules.coverage import ComponentCoverage
from quality.toolchain import (
    ManifestError,
    Tool,
    ToolchainError,
    cache_root,
    extra_path,
    load_manifest,
    locate,
    python_root,
)
from quality.toolchain.install import MISSING

# Ruff and Pyright are pinned by the core's own lockfile and installed beside its interpreter.
CORE_TOOLS = ("ruff", "pyright")


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


def local_profiles() -> Mapping[Profile, ProfileAdapter]:
    """Return the profile adapters of this build with their installed tools."""
    ruff, pyright = (core_tool(name) for name in CORE_TOOLS)
    python = PythonProfile(ruff=ruff, pyright=pyright, environments=Environments(local_uv()))
    return {Profile.PYTHON: python}


def local_setups() -> Mapping[Profile, ProfileSetup]:
    """Return what bootstrap and doctor use to provision and probe each profile."""
    return {Profile.PYTHON: PythonSetup(local_uv())}


def local_fixers() -> Mapping[Profile, ProfileFixer]:
    """Return the fixers of this build with their installed tools."""
    return {Profile.PYTHON: PythonFixer(core_tool("ruff"))}


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
