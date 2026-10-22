"""What `bootstrap` downloads for a TypeScript component and what `doctor` probes offline.

Bootstrap installs the pinned Node, then runs the component's `npm ci` once with
network access in a throwaway copy of the package manifests, which fills the
shared npm cache. Only the lockfile and the package.json files of the root and
its workspace members are copied: the project's `.npmrc` is not, so the install
uses the public registry and no credentials. Doctor locates Node without
downloading it and repeats the install offline (decision 0010). A browser
component gets nothing until this build can check it.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from quality.adapters.typescript import browser
from quality.adapters.typescript.config import check_config
from quality.adapters.typescript.environment import Node, npm_ci
from quality.adapters.typescript.lockfile import LOCKFILE, MANIFEST, Lock
from quality.diagnostics import Diagnostic
from quality.policy import Component


def copy_manifests(lock: Lock, root: Path, target: Path) -> Path:
    """Copy what `npm ci` reads below `root` into `target`; return the copied lock directory."""
    base = root.resolve()
    directory = lock.directory.resolve()
    sources = [directory / LOCKFILE, directory / MANIFEST]
    sources += [(directory / member).resolve() / MANIFEST for member in lock.members()]
    for source in sources:
        if source.is_file():
            copy = target / source.relative_to(base)
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, copy)
    return target / directory.relative_to(base)


@dataclass(slots=True)
class TypeScriptSetup:
    """Provisions and probes component packages with the pinned Node."""

    locate: Callable[[], Path]
    install: Callable[[], Path]
    cache: Path
    pins: Mapping[str, str]
    _done: set[tuple[bool, Path]] = field(default_factory=set[tuple[bool, Path]])

    def _installed(self, component: Component, root: Path, *, offline: bool) -> list[Diagnostic]:
        incomplete = browser.unsupported(component)
        if incomplete:
            return incomplete
        settings, report = check_config(component, root, self.pins)
        if settings is None or report.found:
            return report.found
        node = Node(self.locate() if offline else self.install(), self.cache)
        lock = settings.lock
        if (offline, lock.directory) in self._done:
            return []
        with tempfile.TemporaryDirectory(prefix=f"quality-{component.id}-") as scratch:
            copied = copy_manifests(lock, root, Path(scratch) / "packages")
            npm_ci(node, copied, Path(scratch) / "home", label=component.id, offline=offline)
        self._done.add((offline, lock.directory))
        return []

    def provision(self, component: Component, root: Path) -> list[Diagnostic]:
        """Install the pinned Node and cache the locked packages."""
        return self._installed(component, root, offline=False)

    def probe(self, component: Component, root: Path) -> list[Diagnostic]:
        """Install the locked packages offline into a throwaway directory."""
        return self._installed(component, root, offline=True)
