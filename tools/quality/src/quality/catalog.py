"""The registry of every rule known to this build of the gate."""

from __future__ import annotations

from quality.diagnostics import RuleRegistry
from quality.policy import load, schema, validate


def build_registry() -> RuleRegistry:
    """Collect the rules declared by every feature module."""
    return RuleRegistry([*load.RULES, *validate.RULES, *schema.RULES])
