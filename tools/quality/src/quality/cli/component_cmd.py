"""`quality component add`: declare an application component in quality.toml (decision 0016).

The command only edits the policy in the work tree. It never stages, never
creates the native project, and never downloads; `quality bootstrap` then
installs what the new component's profile needs. A TypeScript project with
React or Vite evidence must name its target, so registration never guesses
whether its code runs in the browser (decision 0017).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from quality.catalog import build_registry
from quality.cli import Subcommands
from quality.diagnostics import Outcome
from quality.diagnostics.render import render_text
from quality.discovery import frontend
from quality.discovery.manifests import PARSERS, ManifestError
from quality.gitio import GitioError, Repository
from quality.policy import Bundler, Capability, ExecutionTarget, Framework, Profile, cross_validate
from quality.policy.edit import Draft, EditError, add_component, component_toml
from quality.policy.load import POLICY_FILE

NAME = "component"
ACTIONS = frozenset({"add"})
# Source and unit test directories each profile's native tools expect by default.
CONVENTIONS: dict[Profile, tuple[tuple[str, ...], tuple[str, ...]]] = {
    Profile.PYTHON: (("src",), ("tests",)),
    Profile.TYPESCRIPT: (("src",), ("tests",)),
    Profile.DART: (("lib", "bin"), ("test",)),
    Profile.PHP: (("src",), ("tests",)),
}


class UsageError(ValueError):
    """An argument that cannot describe the component."""


def register(commands: Subcommands) -> None:
    """Add the `component` subcommand group."""
    parser = commands.add_parser(
        NAME,
        help="declare components in quality.toml",
        description="Declare a component of an existing native project in quality.toml.",
    )
    actions = parser.add_subparsers(dest="action", metavar="<action>", required=True)
    add = actions.add_parser(
        "add",
        help="add an application component to quality.toml",
        description="Append a [[components]] table for the native project in ROOT to "
        "quality.toml in the work tree. The profile follows from the project's manifest, the "
        "ID from the directory name, and the source and unit test directories from the "
        "profile's conventions, unless the options name them. The edited policy is validated "
        "before it is written; nothing is staged. Exit 0 when added, 2 when the arguments or "
        "the resulting policy are invalid, 3 on Git errors.",
    )
    add.add_argument("root", help="the component's directory, relative to the current one")
    add.add_argument("--id", help="the component ID (default: the directory name)")
    add.add_argument("--profile", choices=[str(profile) for profile in Profile])
    add.add_argument("--source", action="append", help="a source directory (repeatable)")
    add.add_argument("--unit", action="append", help="a unit test directory (repeatable)")
    add.add_argument(
        "--capability", action="append", default=[], help="a declared capability (repeatable)"
    )
    add.add_argument("--no-boundary-reason", help="why the component has no capabilities")
    add.add_argument(
        "--target",
        choices=[str(target) for target in ExecutionTarget],
        help="where a typescript component runs (default: node); browser declares a React + "
        "Vite application with the ui capability",
    )
    add.set_defaults(handler=run_add)


def _relative_root(top: Path, root: str) -> tuple[Path, str]:
    directory = (Path.cwd() / root).resolve()
    if not directory.is_relative_to(top) or not directory.is_dir():
        msg = f"'{root}' is not a directory of this repository"
        raise UsageError(msg)
    relative = directory.relative_to(top).as_posix()
    return directory, relative or "."


def _profile(directory: Path, chosen: str | None) -> Profile:
    if chosen is not None:
        return Profile(chosen)
    found = {profile for name, (profile, _) in PARSERS.items() if (directory / name).is_file()}
    if len(found) != 1:
        names = ", ".join(sorted(PARSERS))
        msg = f"cannot tell the profile from the manifests ({names}); name it with --profile"
        raise UsageError(msg)
    return found.pop()


def _target(directory: Path, profile: Profile, chosen: str | None) -> ExecutionTarget | None:
    if profile is not Profile.TYPESCRIPT:
        if chosen is not None:
            msg = "--target applies only to the typescript profile"
            raise UsageError(msg)
        return None
    try:
        evidence = frontend.inspect(directory)
    except ManifestError as error:
        raise UsageError(str(error)) from error
    if chosen is None:
        if evidence.found:
            msg = (
                f"found {', '.join(evidence.found)}, so the target is ambiguous; "
                "name it with --target browser or --target node"
            )
            raise UsageError(msg)
        return None
    target = ExecutionTarget(chosen)
    if target is ExecutionTarget.BROWSER and evidence.unsupported:
        msg = (
            f"{', '.join(evidence.unsupported)} is not supported; "
            "the browser target supports React with Vite"
        )
        raise UsageError(msg)
    if target is ExecutionTarget.BROWSER and evidence.missing:
        msg = f"a React + Vite application needs {', '.join(evidence.missing)}"
        raise UsageError(msg)
    return target


def _directories(
    directory: Path, chosen: list[str] | None, defaults: tuple[str, ...]
) -> tuple[str, ...]:
    if chosen:
        return tuple(chosen)
    present = tuple(name for name in defaults if (directory / name).is_dir())
    if not present:
        msg = f"none of {', '.join(defaults)} exists in the component"
        raise UsageError(msg)
    return present


def _draft(args: argparse.Namespace, top: Path) -> Draft:
    directory, root = _relative_root(top, args.root)
    profile = _profile(directory, args.profile)
    target = _target(directory, profile, args.target)
    browser = target is ExecutionTarget.BROWSER
    capabilities = tuple(args.capability)
    if browser and Capability.UI not in capabilities:
        capabilities = (Capability.UI, *capabilities)
    sources, units = CONVENTIONS[profile]
    if not capabilities and args.no_boundary_reason is None:
        msg = "declare --capability, or explain with --no-boundary-reason why there is none"
        raise UsageError(msg)
    return Draft(
        id=args.id or directory.name,
        profile=str(profile),
        root=root,
        source=_directories(directory, args.source, sources),
        unit=_directories(directory, args.unit, units),
        capabilities=tuple(str(name) for name in capabilities),
        no_boundary_reason=args.no_boundary_reason,
        target=None if target is None else str(target),
        framework=str(Framework.REACT) if browser else None,
        bundler=str(Bundler.VITE) if browser else None,
    )


def _policy_text(top: Path) -> str:
    path = top / POLICY_FILE
    if not path.is_file():
        msg = f"there is no {POLICY_FILE} at the repository root"
        raise UsageError(msg)
    return path.read_text(encoding="utf-8")


def run_add(args: argparse.Namespace) -> int:
    """Add the component to the work tree's policy and print the new table."""
    try:
        top = Repository.discover(Path.cwd(), os.environ).worktree
        draft = _draft(args, top)
        block = component_toml(draft)
        text, policy = add_component(_policy_text(top), block)
    except UsageError as error:
        print(f"component add: {error}", file=sys.stderr)
        return 2
    except GitioError as error:
        outcome = Outcome.of([error.diagnostic])
    except EditError as error:
        outcome = Outcome.of(error.diagnostics)
    else:
        outcome = Outcome.of(cross_validate(policy, build_registry().ids()))
        if not outcome.errors:
            (top / POLICY_FILE).write_text(text, encoding="utf-8")
            print(f"added to {POLICY_FILE}:\n\n{block}")
            print(
                "next: stage the component and quality.toml, run ./quality bootstrap, then commit"
            )
    if outcome.diagnostics:
        sys.stdout.write(render_text(outcome))
    return int(outcome.exit_code())
