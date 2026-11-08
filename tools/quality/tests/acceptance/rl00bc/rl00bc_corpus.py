"""Preregistered identities and native selectors for the RL00b/c fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from tests.acceptance.rl00bc.rl00bc_errors import invalid


@dataclass(frozen=True)
class Case:
    """One expected native identity and the provider's exact selector."""

    identity: str
    variant: str
    selector: str


_PY_SMALL = ("ordinary", "setup", "teardown", "child")
_PY_LARGE = (*_PY_SMALL, "allocation", "retained", "parameter-cheap", "parameter-heavy",
             "slow", "justified", *(f"cheap-{i:02d}" for i in range(1, 7)))
_PHP_LARGE = (*_PY_SMALL, "allocation", "retained", "parameterCheap", "parameterHeavy",
              "slow", "justified", *(f"cheap{i:02d}" for i in range(1, 7)))
_VM_SMALL = ("ordinary", "fixture", "child", "parameter-heavy")
_VM_LARGE = (*_VM_SMALL, "parameter-cheap", *(f"cheap-{i}" for i in range(11)))


def _python(size: str) -> list[Case]:
    names = _PY_SMALL if size == "small" else _PY_LARGE
    return [Case(f"test_subject::test_subject[{name}]", name, name) for name in names]


def _php(size: str) -> list[Case]:
    names = _PY_SMALL if size == "small" else _PHP_LARGE
    cases: list[Case] = []
    for name in names:
        method = (f'testparameter with data set "{name}"' if name.startswith("parameter")
                  else f"test{name}")
        cases.append(Case(f"SubjectTest::{method}", name, name))
    return cases


def _vm(profile: str, size: str) -> list[Case]:
    names = _VM_SMALL if size == "small" else _VM_LARGE
    if profile == "node":
        return [Case(name, "default", name) for name in names]
    if profile == "dart":
        return [Case(f"{name} case", "default", f"{name} case") for name in names]
    return [Case(f"parameter:{name}[{project}]", project, f"parameter:{name}[{project}]")
            for name in names for project in ("desktop", "mobile")]


def expected(profile: str, size: str) -> list[Case]:
    """Return fixed expectations without consulting a native report."""
    if size not in ("small", "large"):
        invalid("unknown corpus size")
    if profile == "python":
        return _python(size)
    if profile == "php":
        return _php(size)
    if profile in ("node", "dart", "browser"):
        return _vm(profile, size)
    invalid("unknown corpus profile")


def verify(profile: str, size: str, cases: object) -> list[dict[str, object]]:
    """Reject missing, duplicate, unexpected, or malformed native identities."""
    if not isinstance(cases, list):
        invalid("native corpus is not a list")
    rows: list[dict[str, object]] = []
    observed: set[tuple[str, str]] = set()
    for value in cast(list[object], cases):
        if not isinstance(value, dict):
            invalid("invalid native corpus case")
        row = cast(dict[str, object], value)
        identity, variant = row.get("id"), row.get("variant", "default")
        if not isinstance(identity, str) or not isinstance(variant, str):
            invalid("native corpus lacks identity or variant")
        key = (identity, variant)
        if key in observed:
            invalid("duplicate native corpus identity")
        observed.add(key)
        rows.append(row)
    required = {(case.identity, case.variant) for case in expected(profile, size)}
    if observed != required:
        invalid("native corpus differs from preregistered identities")
    return rows


def verify_selected(case: Case, cases: object) -> None:
    """Check the exact native identity returned by a provider selector."""
    if not isinstance(cases, list):
        invalid("selector output must be a list")
    items = cast(list[object], cases)
    if len(items) != 1:
        invalid("selector did not produce exactly one case")
    value = items[0]
    if not isinstance(value, dict):
        invalid("selector produced an invalid case")
    row = cast(dict[str, object], value)
    if row.get("id") != case.identity or row.get("variant", "default") != case.variant:
        invalid("selector produced a different native identity or variant")
