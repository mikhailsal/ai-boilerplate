"""Keep retained fixture instances separate across native workers and source files."""

from __future__ import annotations

from tests.acceptance.rl00bc import rl00bc_dart_binding, rl00bc_resource_oracle

PHASES = {
    "python": ("session-setup-start", "session-setup"),
    "php": ("class-setup-start", "class-setup-end"),
    "node": ("retained-allocation-start", "retained-allocation-end"),
    "browser": ("retained-allocation-start", "retained-allocation-end"),
    "dart": ("retained-allocation-start", "retained-allocation-end"),
}


def _context(event: dict[str, object], run: dict[str, object]) -> str | None:
    value = event.get("fixture_context")
    if not isinstance(value, str) or not value:
        return None
    prefix, marker, path = value.partition("file:")
    if not marker:
        return value
    relative = rl00bc_dart_binding.relative_source(marker + path, run.get("corpus_root"))
    return prefix + relative if relative is not None else None


def _groups(
    profile: str, events: list[dict[str, object]], run: dict[str, object]
) -> tuple[dict[tuple[int, str, str], list[dict[str, object]]], list[str]]:
    groups: dict[tuple[int, str, str], list[dict[str, object]]] = {}
    gaps: list[str] = []
    for event in events:
        if (
            event.get("label", event.get("case")) != "retained"
            or event.get("phase") not in PHASES[profile]
        ):
            continue
        pid, worker, context = event.get("pid"), event.get("worker"), _context(event, run)
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or context is None:
            gaps.append("retained fixture lacks actual PID or source/project context")
            continue
        key = (pid, str(worker) if worker is not None else str(pid), context)
        groups.setdefault(key, []).append(event)
    return groups, gaps


def _records(
    profile: str, groups: dict[tuple[int, str, str], list[dict[str, object]]]
) -> list[dict[str, object]]:
    return [
        {
            "pid": pid,
            "worker": worker,
            "context": context,
            "ordered_setup": rl00bc_resource_oracle.ordered(rows, PHASES[profile]),
            "events": rows,
        }
        for (pid, worker, context), rows in groups.items()
    ]


def _selected_context(events: list[dict[str, object]], run: dict[str, object]) -> str | None:
    contexts = {_context(event, run) for event in events}
    return next(iter(contexts)) if len(contexts) == 1 else None


def _context_rows(groups: dict[tuple[int, str, str], list[dict[str, object]]],
                  context: str | None) -> list[dict[str, object]]:
    return [event for key, rows in groups.items() if key[2] == context for event in rows]


def select(
    profile: str,
    canonical: dict[str, object],
    strict: dict[str, object],
    canonical_events: list[dict[str, object]],
    strict_events: list[dict[str, object]],
    canonical_case: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Bind shared setup context while retaining every separately observed fixture."""
    before, first_gaps = _groups(profile, canonical_events, canonical)
    after, second_gaps = _groups(profile, strict_events, strict)
    context = _selected_context(canonical_case, canonical)
    canonical_rows = _context_rows(before, context)
    strict_rows = _context_rows(after, context)
    original = _records(profile, before)
    gaps = [*first_gaps, *second_gaps]
    if context is None:
        gaps.append("selected case has no unique observed fixture context")
    ordered = bool(original) and all(row["ordered_setup"] is True for row in original)
    return (
        canonical_rows,
        strict_rows,
        {
            "selected_context": context,
            "canonical_instances": original,
            "strict_instances": _records(profile, after),
            "gaps": gaps,
            "canonical_all_ordered": ordered and not first_gaps,
            "context_bound": context is not None and bool(canonical_rows) and bool(strict_rows),
            "interpretation": "shared fixture costs stay separate from individual case costs",
        },
    )
