"""`quality fix` for TypeScript: Prettier and ESLint fixes, applied through a copy.

The tools need the component's locked packages, and installing them would
replace the working tree's own `node_modules`. The fixer therefore copies the
working tree's tracked and untracked, not ignored, regular files into a
temporary directory, installs the lockfile offline there, and runs
`eslint --fix` on the component's TypeScript files and `prettier --write` on
them and on the configuration scripts at the component root. A changed file is
copied back only while its working-tree content is still the copied one, so an
edit made in the meantime is never overwritten. Nothing is staged, and what
remains is reported as the check reports it (decision 0011).

Configuration scripts in subdirectories are checked but not formatted here,
because the fixer receives only the source and test files of the inventory.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from quality.adapters.native import run_tool
from quality.adapters.target import Target
from quality.adapters.typescript import eslint, prettier
from quality.adapters.typescript.config import check_config, typescript_files
from quality.adapters.typescript.environment import Environments, Node, tool_script
from quality.adapters.typescript.helper import HELPER
from quality.adapters.typescript.lockfile import NODE_MODULES
from quality.diagnostics import Diagnostic
from quality.discovery.filetypes import CONFIG_SCRIPT_PATTERN
from quality.policy import Component
from quality.process import Command

TIMEOUT = 900.0
TOOLS = ("eslint", "prettier")


def config_scripts(component: Component, listed: Iterable[str]) -> tuple[str, ...]:
    """Return the configuration scripts at the component root."""
    root = PurePosixPath(component.root)
    return tuple(
        path
        for path in listed
        if PurePosixPath(path).parent == root
        and CONFIG_SCRIPT_PATTERN.match(PurePosixPath(path).name)
    )


def copy_tree(root: Path, target: Path, paths: Iterable[str]) -> None:
    """Copy the regular files among `paths` from `root` to `target`, without `node_modules`."""
    for path in paths:
        source = root / path
        if NODE_MODULES in PurePosixPath(path).parts or source.is_symlink() or not source.is_file():
            continue
        copy = target / path
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, copy)


def copy_back(copy: Path, root: Path, before: Mapping[str, bytes]) -> None:
    """Write each fixed file to the working tree unless it changed there meanwhile."""
    for path, original in before.items():
        fixed = (copy / path).read_bytes()
        current = root / path
        if fixed != original and current.read_bytes() == original:
            current.write_bytes(fixed)


@dataclass(slots=True)
class TypeScriptFixer:
    """Applies the component's locked ESLint fixes and Prettier formatting."""

    environments: Environments
    pins: Mapping[str, str]
    listing: Callable[[Path], Iterable[str]]
    helper: Path = HELPER

    def _apply(self, node: Node, script: Path, target: Target, *flags: str) -> None:
        # `eslint --fix` exits 1 when findings remain; `prettier --write` exits 2 on a syntax error.
        command = Command(
            (str(node.executable), str(script), *flags, *target.arguments()),
            cwd=target.directory,
            timeout=TIMEOUT,
            env=node.environ(target.snapshot.parent / "home" / script.name),
        )
        run_tool(command, name=script.name, accepted={0, 1, 2})

    def _fixed(
        self, component: Component, copy: Path, files: tuple[str, ...], configs: tuple[str, ...]
    ) -> list[Diagnostic]:
        settings, report = check_config(component, copy, self.pins)
        if settings is None or report.found:
            return report.found
        work = copy.parent / "work"
        top = settings.lock.directory
        node = self.environments.install(top, work, label=component.id)
        linted = Target(component, copy, files)
        formatted = Target(component, copy, (*files, *configs))
        scripts = {
            name: tool_script(name, linted.directory, top, self.pins[name]) for name in TOOLS
        }
        home = work / "typescript-home" / component.id
        found: list[Diagnostic] = []
        if files:
            self._apply(node, scripts["eslint"], linted, "--fix", "--no-ignore")
            found += eslint.eslint_configuration(linted, node=node, work=work, program=self.helper)
            found += eslint.eslint_lint(linted, node=node, script=scripts["eslint"], work=home)
        ignore = home / "prettierignore"
        home.mkdir(parents=True, exist_ok=True)
        ignore.write_text("", encoding="utf-8")
        self._apply(node, scripts["prettier"], formatted, "--write", "--ignore-path", str(ignore))
        found += prettier.prettier_format(
            formatted, node=node, script=scripts["prettier"], home=home
        )
        return found

    def fix(self, component: Component, root: Path, files: tuple[str, ...]) -> list[Diagnostic]:
        """Fix and format the files in a copy, copy them back, and return what remains."""
        listed = sorted(set(self.listing(root)))
        configs = config_scripts(component, listed)
        checked = typescript_files(files)
        if not checked and not configs:
            return check_config(component, root, self.pins)[1].found
        with tempfile.TemporaryDirectory(prefix=f"quality-fix-{component.id}-") as scratch:
            copy = Path(scratch) / "tree"
            copy_tree(root, copy, listed)
            before = {
                path: (copy / path).read_bytes()
                for path in (*checked, *configs)
                if (copy / path).is_file()
            }
            kept = tuple(path for path in checked if path in before)
            found = self._fixed(component, copy, kept, tuple(p for p in configs if p in before))
            copy_back(copy, root, before)
        return found
