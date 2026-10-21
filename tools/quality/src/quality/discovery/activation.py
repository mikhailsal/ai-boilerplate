"""Which components a run validates; see the roles in decision 0003."""

from __future__ import annotations

from collections.abc import Iterable

from quality.discovery.classify import under
from quality.policy import Component, Policy, Role


def is_active(policy: Policy, component: Component, changed: Iterable[str] = ()) -> bool:
    """Return whether a component's gates run for this candidate.

    Application and tooling components always run. A helper runs in maintainer
    mode, when an application component uses its profile, or when the candidate
    changes one of its files.
    """
    if component.role is not Role.HELPER or policy.repository.mode == "maintainer":
        return True
    if any(
        other.role is Role.APPLICATION and other.profile is component.profile
        for other in policy.components
    ):
        return True
    return any(under(path, component.root) for path in changed)


def active_components(policy: Policy, changed: Iterable[str] = ()) -> tuple[Component, ...]:
    """Return the components whose gates run, in declaration order."""
    paths = tuple(changed)
    return tuple(c for c in policy.components if is_active(policy, c, paths))
