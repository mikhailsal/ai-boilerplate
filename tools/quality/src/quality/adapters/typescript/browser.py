"""The browser target of the TypeScript profile (decisions 0017 and 0018).

A component with `target = "browser"` passes only when every browser gate of
the decisions ran on it. Until this build implements them all, preparing such a
component reports the gates it lacks, so no browser component can pass on the
Node gates alone. Like a profile without an adapter, the finding cannot be
excepted.
"""

from __future__ import annotations

from quality.diagnostics import Diagnostic, Kind, Rule
from quality.policy import Component

MISSING = (
    "the browser lint rules",
    "the CSS and HTML checks",
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
        "Node gates alone."
    ),
    remedy=(
        "Update tools/quality to a release that supports browser components, or remove "
        '`target = "browser"` while the component is not a browser application.'
    ),
    kind=Kind.ENVIRONMENT,
)
RULES = (INCOMPLETE,)


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
