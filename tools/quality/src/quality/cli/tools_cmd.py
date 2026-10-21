"""`quality tools`: install the pinned standalone tools into the local cache."""

from __future__ import annotations

import argparse
import sys

from quality.cli import Subcommands
from quality.diagnostics import Diagnostic, Outcome
from quality.diagnostics.render import render_text
from quality.toolchain import ManifestError, ToolchainError, cache_root, install, load_manifest
from quality.toolchain.install import INSTALL_FAILED

NAME = "tools"
ACTIONS = frozenset({"install"})
DEFAULT_TOOLS = ("gitleaks", "actionlint", "osv-scanner")


def register(commands: Subcommands) -> None:
    """Add the `tools` subcommand group."""
    parser = commands.add_parser(
        NAME,
        help="install pinned standalone tools",
        description="Install tools pinned in tools/quality/toolchains.toml into the cache. "
        "Downloads are verified against their SHA-256 checksums before anything is installed.",
    )
    actions = parser.add_subparsers(dest="action", metavar="<action>", required=True)
    add = actions.add_parser(
        "install",
        help="download, verify, and install pinned tools",
        description="Install the named tools, or the default ones (gitleaks, actionlint, and "
        "osv-scanner). Exit 0 when all are installed, 2 for unknown names, 3 when a download "
        "fails.",
    )
    add.add_argument("names", nargs="*", help="tool names from toolchains.toml")
    add.set_defaults(handler=run_install)


def run_install(args: argparse.Namespace) -> int:
    """Install each requested tool and print where it is."""
    found: list[Diagnostic] = []
    try:
        manifest = load_manifest()
    except ManifestError as error:
        found.append(INSTALL_FAILED.diagnostic(str(error)))
        sys.stdout.write(render_text(Outcome.of(found)))
        return int(Outcome.of(found).exit_code())
    names: list[str] = list(args.names) or list(DEFAULT_TOOLS)
    unknown = [name for name in names if name not in manifest.tools]
    if unknown:
        print(f"unknown tools: {', '.join(unknown)}", file=sys.stderr)
        return 2
    root = cache_root()
    for name in names:
        try:
            path = install(name, manifest.tools[name], root)
        except ToolchainError as error:
            found.append(error.diagnostic)
            continue
        print(f"{name} {manifest.tools[name].version}: {path}")
    outcome = Outcome.of(found)
    if found:
        sys.stdout.write(render_text(outcome))
    return int(outcome.exit_code())
