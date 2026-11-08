"""Require observed identity and phase scope before accepting a case comparison."""

from __future__ import annotations

from typing import cast


def matches(oracle: dict[str, object], *, memory: bool, shared: bool = False) -> bool:
    """Keep a raw resource cause separate from proof about the selected subject."""
    evidence = oracle.get("evidence")
    if oracle.get("canonical_identity_bound") is not True or not isinstance(evidence, dict):
        return False
    phases = cast(dict[str, object], evidence)
    if phases.get("canonical_complete") is not True or phases.get("strict_phase_entered") is not True:
        return False
    if shared:
        value = phases.get("shared_fixture_contexts")
        if not isinstance(value, dict):
            return False
        context = cast(dict[str, object], value)
        if context.get("context_bound") is not True or context.get("canonical_all_ordered") is not True:
            return False
    elif oracle.get("strict_identity_bound") is not True:
        return False
    resource = phases.get("resource")
    return not memory or (
        isinstance(resource, dict)
        and cast(dict[str, object], resource).get("own_memory_after_entry") is True
    )
