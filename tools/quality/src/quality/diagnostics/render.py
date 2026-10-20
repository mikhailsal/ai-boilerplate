"""Human and machine renderings of an outcome."""

from __future__ import annotations

import json
from typing import Any

from quality.diagnostics.model import Diagnostic, Outcome

REPORT_SCHEMA_VERSION = 1


def diagnostic_to_dict(diagnostic: Diagnostic) -> dict[str, Any]:
    """Convert one diagnostic to a JSON-compatible mapping."""
    location = diagnostic.location
    return {
        "rule": diagnostic.rule,
        "severity": diagnostic.severity.value,
        "kind": diagnostic.kind.value,
        "message": diagnostic.message,
        "path": location.path if location else None,
        "line": location.line if location else None,
        "column": location.column if location else None,
        "component": diagnostic.component,
        "hint": diagnostic.hint,
        "data": dict(sorted(diagnostic.data.items())),
    }


def outcome_to_json(outcome: Outcome, *, command: str) -> str:
    """Render an outcome as a stable JSON document."""
    document = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "command": command,
        "exit_code": int(outcome.exit_code()),
        "summary": {
            "errors": len(outcome.errors),
            "warnings": len(outcome.warnings),
            "total": len(outcome.diagnostics),
        },
        "diagnostics": [diagnostic_to_dict(d) for d in outcome.diagnostics],
    }
    return json.dumps(document, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def render_text(outcome: Outcome) -> str:
    """Render an outcome for a terminal, one finding per paragraph."""
    lines: list[str] = []
    for diagnostic in outcome.diagnostics:
        where = diagnostic.location.render() + ": " if diagnostic.location else ""
        scope = f" [{diagnostic.component}]" if diagnostic.component else ""
        lines.append(
            f"{where}{diagnostic.severity.value}: {diagnostic.message} ({diagnostic.rule}){scope}"
        )
        if diagnostic.hint:
            lines.append(f"  hint: {diagnostic.hint}")
    errors, warnings = len(outcome.errors), len(outcome.warnings)
    verdict = "FAILED" if outcome.exit_code() else "PASSED"
    lines.append(f"{verdict}: {errors} error(s), {warnings} warning(s)")
    return "\n".join(lines) + "\n"
