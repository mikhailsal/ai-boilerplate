"""Compare actual Dart report sources without equating run-local numeric IDs."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import cast
from urllib.parse import unquote, urlsplit


def relative_source(source: object, root: object) -> str | None:
    """Normalize an observed native file path only within its recorded corpus."""
    if not isinstance(source, str) or not isinstance(root, str):
        return None
    parsed = urlsplit(source)
    if parsed.scheme and (parsed.scheme != "file" or parsed.netloc):
        return None
    path = PurePosixPath(unquote(parsed.path))
    if ".." in path.parts:
        return None
    if path.is_absolute():
        try:
            path = path.relative_to(PurePosixPath(root))
        except ValueError:
            return None
    return path.as_posix() if path.parts else None


def _case(run: dict[str, object], identity: str, variant: str) -> dict[str, object]:
    value = run.get("native_cases")
    if not isinstance(value, list):
        return {}
    rows = [cast(dict[str, object], item) for item in cast(list[object], value)
            if isinstance(item, dict)]
    matches = [row for row in rows
               if row.get("id") == identity and row.get("variant", "default") == variant]
    return matches[0] if len(matches) == 1 else {}


def compare(canonical: dict[str, object], strict: dict[str, object],
            identity: str, variant: str) -> dict[str, object]:
    """Require the same observed source and preserve each actual testStart ID."""
    original, selected = _case(canonical, identity, variant), _case(strict, identity, variant)
    before = relative_source(original.get("source"), canonical.get("corpus_root"))
    after = relative_source(selected.get("source"), strict.get("corpus_root"))
    identifiers = [original.get("native_id"), selected.get("native_id")]
    observed = all(isinstance(value, int) and not isinstance(value, bool) for value in identifiers)
    return {
        "canonical_source": before, "strict_source": after,
        "canonical_native_id": identifiers[0], "strict_native_id": identifiers[1],
        "run_local_ids_observed": observed,
        "bound": observed and before is not None and before == after,
        "interpretation": "same actual source; numeric IDs remain local to each run",
    }
