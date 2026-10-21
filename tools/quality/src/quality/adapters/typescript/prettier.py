"""Prettier, the formatter of the TypeScript profile.

The pinned Prettier checks explicit file lists with `--list-different`. An
empty ignore file replaces `.gitignore` and `.prettierignore`, so no file the
gate names can be skipped. A file Prettier cannot parse makes it exit 2 for the
whole run; such files are left to the type checker and ESLint, which report the
syntax error, and the others are checked again without them.
"""

from __future__ import annotations

import re
from pathlib import Path

from quality.adapters.native import fail, run_tool
from quality.adapters.target import Target
from quality.adapters.typescript.environment import Node
from quality.diagnostics import Diagnostic, Location, Rule
from quality.process import Command

FORMAT = Rule(
    id="typescript.format",
    title="TypeScript file is not formatted by the pinned Prettier",
    requirement="R04",
    explanation=(
        "Source, test, and configuration scripts are checked with `prettier --list-different` "
        "and the component's Prettier configuration. Ignore files do not apply to them."
    ),
    remedy="Run `./quality fix`, review the change, and stage it.",
)
RULES = (FORMAT,)

TIMEOUT = 600.0
TOOL = "prettier"
SYNTAX = re.compile(r"^\[error\] (.+?): SyntaxError: ", re.MULTILINE)


def prettier_argv(node: Node, script: Path, ignore: Path, *flags: str) -> tuple[str, ...]:
    """Build a Prettier command that honors no ignore file."""
    options = ("--ignore-path", str(ignore), "--no-error-on-unmatched-pattern")
    return (str(node.executable), str(script), *flags, *options)


def _unparsable(target: Target, stderr: str) -> set[str]:
    names: list[str] = SYNTAX.findall(stderr)
    return {target.relative(TOOL, name) for name in names}


def prettier_format(target: Target, *, node: Node, script: Path, home: Path) -> list[Diagnostic]:
    """Report each named file whose formatting differs from Prettier's."""
    ignore = home / "prettierignore"
    home.mkdir(parents=True, exist_ok=True)
    ignore.write_text("", encoding="utf-8")
    files: tuple[str, ...] = target.files
    while files:
        current = Target(target.component, target.snapshot, files)
        command = Command(
            (*prettier_argv(node, script, ignore, "--list-different"), *current.arguments()),
            cwd=target.directory,
            timeout=TIMEOUT,
            env=node.environ(home),
        )
        completed = run_tool(command, name=TOOL, accepted={0, 1, 2})
        if completed.returncode != 2:
            listed = completed.stdout_text().splitlines()
            return [
                FORMAT.diagnostic(
                    "the file is not formatted; run `./quality fix`",
                    location=Location(current.relative(TOOL, name)),
                    component=target.component.id,
                )
                for name in listed
                if name.strip()
            ]
        skipped = _unparsable(current, completed.stderr_text())
        if not skipped & set(files):
            fail(TOOL, f"exit status 2: {completed.stderr_text()}")
        files = tuple(path for path in files if path not in skipped)
    return []
