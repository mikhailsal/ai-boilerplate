"""Apply registered exceptions exactly; report expired, due, unused, and invalid ones (R05)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from quality.diagnostics import Diagnostic, Kind, Location, Rule, Severity
from quality.policy import PolicyException

EXPIRED = Rule(
    id="exceptions.expired",
    title="Exception has expired",
    requirement="R05",
    explanation="A temporary exception stops applying on its expiry date.",
    remedy="Fix the finding and remove the exception, or renew it with a new reason.",
)
REVIEW_DUE = Rule(
    id="exceptions.review-due",
    title="Permanent exception is due for review",
    requirement="R05",
    explanation="A permanent exception still applies after its review date, with a warning.",
    remedy="Review the exception and move its review date forward, or remove it.",
    severity=Severity.WARNING,
)
UNUSED = Rule(
    id="exceptions.unused",
    title="Exception matches no finding",
    requirement="R05",
    explanation=(
        "An exception whose rule ran over the candidate but matched nothing is stale, so it "
        "cannot silently cover a future finding."
    ),
    remedy="Remove the exception.",
)
NOT_ALLOWED = Rule(
    id="exceptions.not-allowed",
    title="Rule cannot be excepted",
    requirement="R05",
    explanation=(
        "Policy, Git, discovery, secret, exception, test, coverage, and tool failure rules "
        "cannot be excepted; coverage floors change only in quality.toml, for every component."
    ),
    remedy="Remove the exception and fix the cause.",
)
RULES = (EXPIRED, REVIEW_DUE, UNUSED, NOT_ALLOWED)

FIXED_PREFIXES = (
    "policy.",
    "git.",
    "discovery.",
    "secrets.",
    "exceptions.",
    "tests.",
    "coverage.",
)
POLICY_FILE = "quality.toml"


def exceptable(rule: Rule) -> bool:
    """Whether findings of this rule may be covered by an exception."""
    return rule.kind is Kind.VIOLATION and not rule.id.startswith(FIXED_PREFIXES)


def describe(exception: PolicyException) -> str:
    """Name an exception by its scope."""
    symbol = f" '{exception.symbol}'" if exception.symbol is not None else ""
    return f"exception for '{exception.rule}' at '{exception.path}'{symbol}"


@dataclass(frozen=True, slots=True)
class Applied:
    """Diagnostics left after exceptions, plus the findings about the exceptions."""

    diagnostics: tuple[Diagnostic, ...]
    excepted: int


def _matches(exception: PolicyException, diagnostic: Diagnostic) -> bool:
    return (
        diagnostic.kind is Kind.VIOLATION
        and diagnostic.location is not None
        and exception.rule == diagnostic.rule
        and exception.path == diagnostic.location.path
        and exception.symbol == diagnostic.data.get("symbol")
    )


def apply_exceptions(
    diagnostics: Iterable[Diagnostic],
    exceptions: Sequence[PolicyException],
    *,
    rules: Mapping[str, Rule],
    ran: frozenset[str],
    today: date,
) -> Applied:
    """Remove findings covered by an active exception and report exception problems."""
    found: list[Diagnostic] = []
    active: list[PolicyException] = []
    for exception in exceptions:
        problem, applies = _screen(exception, rules.get(exception.rule), today)
        if problem is not None:
            found.append(problem)
        if applies:
            active.append(exception)
    used: set[int] = set()
    excepted = 0
    for diagnostic in diagnostics:
        position = next((i for i, e in enumerate(active) if _matches(e, diagnostic)), None)
        if position is None:
            found.append(diagnostic)
        else:
            used.add(position)
            excepted += 1
    found.extend(_unused(active, used, ran))
    return Applied(tuple(found), excepted)


def _screen(
    exception: PolicyException, rule: Rule | None, today: date
) -> tuple[Diagnostic | None, bool]:
    """Return the problem with an exception, if any, and whether it still applies."""
    location = Location(POLICY_FILE)
    if rule is not None and not exceptable(rule):
        return NOT_ALLOWED.diagnostic(
            f"{describe(exception)} is not allowed", location=location
        ), False
    if exception.expires is not None and exception.expires < today:
        message = f"{describe(exception)} expired on {exception.expires.isoformat()}"
        return EXPIRED.diagnostic(message, location=location), False
    if exception.review is not None and exception.review < today:
        message = f"{describe(exception)} was due for review on {exception.review.isoformat()}"
        return REVIEW_DUE.diagnostic(message, location=location), True
    return None, True


def _unused(
    active: Sequence[PolicyException], used: set[int], ran: frozenset[str]
) -> Iterator[Diagnostic]:
    """Exceptions of rules that ran over the whole candidate and matched nothing."""
    for position, exception in enumerate(active):
        if position not in used and exception.rule in ran:
            message = f"{describe(exception)} matches no finding"
            yield UNUSED.diagnostic(message, location=Location(POLICY_FILE))
