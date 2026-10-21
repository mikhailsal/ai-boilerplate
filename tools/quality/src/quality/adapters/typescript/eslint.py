"""ESLint with typescript-eslint, the linter of the TypeScript profile.

Before ESLint runs, the helper asks it for the configuration of every named
file: a file without one, or one linted without type information
(`projectService` or `project`), fails, because a configuration can otherwise
lint nothing or only the rules that need no types. ESLint then runs on the
explicit file list with `--no-ignore`, and bulk suppressions are read from an
empty file in the work area instead of the candidate's
`eslint-suppressions.json`. Every message is an error, warnings included, and
so is an unused disable directive; parse errors are messages too.
"""

from __future__ import annotations

from pathlib import Path

from quality.adapters.native import run_tool
from quality.adapters.target import Entry, Target, document, findings, location, number
from quality.adapters.typescript import helper
from quality.adapters.typescript.environment import Node
from quality.boundedio import JsonValue
from quality.diagnostics import Diagnostic, Rule
from quality.process import Command

LINT = Rule(
    id="typescript.lint",
    title="ESLint finding",
    requirement="R04",
    explanation=(
        "Source and test files are linted by the pinned ESLint with the component's flat "
        "configuration, which must give every file type information. Ignore patterns, bulk "
        "suppressions, and warning levels do not apply."
    ),
    remedy="Fix the finding; `./quality fix` applies ESLint's fixes to the working tree.",
)
RULES = (LINT,)

TIMEOUT = 900.0
TOOL = "eslint"
OPTIONS = (
    "--format",
    "json",
    "--no-ignore",
    "--report-unused-disable-directives-severity",
    "error",
)


def _configuration(file: helper.Entry) -> str | None:
    if helper.flag(file, "ignored") or not helper.flag(file, "configured"):
        return "no ESLint configuration lints this file; every source and test file is linted"
    if not helper.flag(file, "typed"):
        return (
            "ESLint lints this file without type information; "
            "set parserOptions.projectService in eslint.config.*"
        )
    return None


def eslint_configuration(
    target: Target, *, node: Node, work: Path, program: Path = helper.HELPER
) -> list[Diagnostic]:
    """Report named files that ESLint would not lint with type information."""
    request: dict[str, JsonValue] = {
        "eslint": str(target.directory),
        "cwd": str(target.directory),
        "files": [*target.arguments()],
    }
    response = helper.run_helper(
        helper.Program(node, program), "eslint-config", request, work=work, cwd=target.directory
    )
    found: list[Diagnostic] = []
    for file in helper.entries(response, "files"):
        message = _configuration(file)
        if message is not None:
            path = target.relative(helper.TOOL, helper.text(file, "file"))
            found.append(
                LINT.diagnostic(
                    message, location=location(path, None, None), component=target.component.id
                )
            )
    return found


def _message(entry: Entry) -> str:
    rule = entry.get("ruleId")
    text = str(entry.get("message", "")).strip()
    return f"{rule}: {text}" if isinstance(rule, str) and rule else text


def eslint_lint(target: Target, *, node: Node, script: Path, work: Path) -> list[Diagnostic]:
    """Lint the named files; every message is an error."""
    work.mkdir(parents=True, exist_ok=True)
    suppressions = work / "eslint-suppressions.json"
    suppressions.write_text("{}", encoding="utf-8")
    argv = (
        str(node.executable),
        str(script),
        *OPTIONS,
        "--suppressions-location",
        str(suppressions),
        *target.arguments(),
    )
    home = work / "typescript-home" / "eslint"
    command = Command(argv, cwd=target.directory, timeout=TIMEOUT, env=node.environ(home))
    completed = run_tool(command, name=TOOL, accepted={0, 1})
    found: list[Diagnostic] = []
    for result in findings(TOOL, document(TOOL, completed)):
        path = target.relative(TOOL, result.get("filePath"))
        found.extend(
            LINT.diagnostic(
                _message(message),
                location=location(path, number(message, "line"), number(message, "column")),
                component=target.component.id,
            )
            for message in findings(TOOL, result.get("messages", []))
        )
    return found
