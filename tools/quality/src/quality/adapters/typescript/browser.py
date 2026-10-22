"""The browser target of the TypeScript profile (decisions 0017 and 0018).

A component with `target = "browser"` gets the Node gates and the browser
static gates: the React Hooks and JSX accessibility rules in its ESLint
configuration, import boundaries, Stylelint and Prettier for its CSS, and its
HTML entry points. It passes only when every browser gate of the decisions ran
on it. Until this build implements them all, its static gates, its suites,
bootstrap, and doctor report the gates it lacks, so no browser component can
pass on the gates that exist. Like a profile without an adapter, the finding
cannot be excepted.
"""

from __future__ import annotations

import posixpath
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import PurePosixPath

from quality.adapters.native import ToolFailedError
from quality.adapters.typescript.config import typescript_files
from quality.diagnostics import Diagnostic, Kind, Rule
from quality.discovery import Region, region_of
from quality.discovery.classify import relative_to
from quality.policy import Component
from quality.testing import StaticRequest

MISSING = (
    "the production build",
    "the jsdom unit suite",
    "the Chromium scenarios",
    "the accessibility scans",
)

INCOMPLETE = Rule(
    id="typescript.browser-incomplete",
    title="This build of the gate cannot check a browser component yet",
    requirement="R01",
    explanation=(
        "A browser component passes only when its browser gates ran: the browser lint rules, "
        "the CSS and HTML checks, the isolated production build, the jsdom unit suite, and "
        "the Chromium scenarios with their accessibility scans. This build of the gate does "
        "not implement all of them, so it fails the component instead of passing it on the "
        "gates that exist."
    ),
    remedy=(
        "Update tools/quality to a release that supports browser components, or remove "
        '`target = "browser"` while the component is not a browser application.'
    ),
    kind=Kind.ENVIRONMENT,
)
RULES = (INCOMPLETE,)

HOOKS = ("react-hooks/rules-of-hooks", "react-hooks/exhaustive-deps")
# The rules of the plugin's recommended configuration that judge markup the
# user reaches: names, labels, roles, focus, and keyboard access.
ACCESSIBILITY = tuple(
    f"jsx-a11y-x/{name}"
    for name in (
        "alt-text",
        "anchor-has-content",
        "anchor-is-valid",
        "aria-props",
        "aria-proptypes",
        "aria-role",
        "aria-unsupported-elements",
        "click-events-have-key-events",
        "heading-has-content",
        "html-has-lang",
        "iframe-has-title",
        "interactive-supports-focus",
        "label-has-associated-control",
        "no-noninteractive-element-interactions",
        "no-static-element-interactions",
        "role-has-required-aria-props",
        "role-supports-aria-props",
        "tabindex-no-positive",
    )
)
TEST_RULES = ("@typescript-eslint/no-floating-promises",)
JSX = frozenset({".tsx", ".jsx"})
VARIANTS = {".scss": "Sass", ".sass": "Sass", ".less": "Less", ".styl": "Stylus"}


def unsupported(component: Component) -> list[Diagnostic]:
    """Return why a browser component cannot be checked yet; nothing for a Node component."""
    if not component.in_browser:
        return []
    return [
        INCOMPLETE.diagnostic(
            f"'{component.id}' targets the browser; this build lacks {', '.join(MISSING)}",
            component=component.id,
        )
    ]


def incomplete(component: Component) -> ToolFailedError:
    """Return the failure of a browser component's suite while its gates are missing."""
    (finding,) = unsupported(component)
    return ToolFailedError(finding)


def server_module(component: Component, path: str) -> bool:
    """Whether a repository path matches one of the component's declared server modules."""
    settings = component.browser_settings
    relative = PurePosixPath(relative_to(component, path))
    return any(relative.full_match(pattern) for pattern in settings.server_modules)


@dataclass(frozen=True, slots=True)
class BrowserFiles:
    """The files of a browser component that its browser gates check, as repository paths.

    `sources` are the TypeScript files of the source roots except the declared
    server modules, `tests` those of the test roots, `styles` the CSS files,
    `variants` the Sass, Less, and Stylus files, `entries` the declared HTML
    entry points, and `owned` every file the component owns.
    """

    sources: tuple[str, ...]
    tests: tuple[str, ...]
    styles: tuple[str, ...]
    variants: tuple[str, ...]
    entries: tuple[str, ...]
    owned: frozenset[str]

    def required_rules(self) -> dict[str, tuple[str, ...]]:
        """Return the ESLint rules each source and test file must have enabled."""
        required: dict[str, tuple[str, ...]] = {
            path: HOOKS + (ACCESSIBILITY if PurePosixPath(path).suffix in JSX else ())
            for path in self.sources
        }
        required.update(dict.fromkeys(self.tests, TEST_RULES))
        return required


def _suffixed(paths: tuple[str, ...], suffixes: Collection[str]) -> tuple[str, ...]:
    return tuple(path for path in paths if PurePosixPath(path).suffix.lower() in suffixes)


def browser_files(request: StaticRequest) -> BrowserFiles:
    """Sort the files of a browser component's static request for its browser gates."""
    component = request.component
    scripts = typescript_files(request.files)
    regions = {path: region_of(component, path) for path in scripts}
    everything = (*request.files, *request.configs, *request.resources)
    return BrowserFiles(
        sources=tuple(
            path
            for path in scripts
            if regions[path] is Region.SOURCE and not server_module(component, path)
        ),
        tests=tuple(path for path in scripts if regions[path] is Region.TESTS),
        styles=_suffixed(everything, (".css",)),
        variants=_suffixed(everything, VARIANTS),
        entries=tuple(
            posixpath.normpath(posixpath.join(component.root, entry))
            for entry in component.browser_settings.entries
        ),
        owned=frozenset(everything),
    )
