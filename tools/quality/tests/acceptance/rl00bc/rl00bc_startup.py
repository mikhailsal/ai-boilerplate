"""Check the pre-bootstrap import surface with the runner's actual Python.

This script parses source without importing the experiment or starting payloads.
Pinned-controller modules imported lazily after preparation are separate inputs.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import NoReturn

PREFIX = "tests.acceptance."
ROOTS = (
    "rl00bc_driver",
    "rl00bc_service",
    "rl00bc_exec",
    "rl00bc_native",
    "rl00bc_guardian_race_controller",
)


def _invalid(message: str) -> NoReturn:
    raise ValueError(message)


def _module(repo: Path, name: str) -> Path | None:
    if not name.startswith(PREFIX):
        return None
    path = repo / "tools/quality" / (name.replace(".", "/") + ".py")
    return path if path.is_file() else None


def _imports(repo: Path, body: list[ast.stmt]) -> list[Path]:
    found: list[Path] = []
    for statement in body:
        if isinstance(statement, ast.Import):
            names = [item.name for item in statement.names]
        elif isinstance(statement, ast.ImportFrom) and statement.module is not None:
            names = [
                statement.module,
                *(statement.module + "." + item.name for item in statement.names),
            ]
        else:
            continue
        found.extend(path for name in names if (path := _module(repo, name)) is not None)
    return found


def _parse(repo: Path, path: Path) -> tuple[list[Path], dict[str, object]]:
    if path.stat().st_size > 2 * 1024 * 1024:
        _invalid("startup source exceeds its finite parse bound")
    relative = path.relative_to(repo).as_posix()
    try:
        tree = ast.parse(path.read_bytes(), filename=relative)
    except SyntaxError as error:
        return [], {
            "path": relative,
            "status": "syntax-error",
            "line": error.lineno,
            "message": error.msg,
        }
    return _imports(repo, tree.body), {"path": relative, "status": "parsed"}


def check(repo: Path) -> dict[str, object]:
    """Follow top-level experiment imports from every system-interpreter entry point."""
    base = repo / "tools/quality/tests/acceptance/rl00bc"
    pending = [base / (name + ".py") for name in ROOTS]
    visited: set[Path] = set()
    records: list[dict[str, object]] = []
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        if len(visited) > 64:
            _invalid("startup import surface exceeds its finite module bound")
        imports, record = _parse(repo, path)
        records.append(record)
        pending.extend(imports)
    return {
        "interpreter": sys.executable,
        "version": sys.version,
        "scope": "syntax and top-level imports only; no payload or runtime capability proof",
        "files": records,
        "success": all(item["status"] == "parsed" for item in records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.repo.absolute())
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
