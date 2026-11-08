"""Compare canonical coverage to the declared fixture subject and native records."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc.rl00bc_errors import invalid

SUBJECTS = {
    "python": (
        "src/subject.py",
        "def value():\n    return 1\n",
        "test_subject.py",
        ("subject.value() == 1",),
    ),
    "php": (
        "subject.php",
        "<?php\nfunction rl00_value(): int { return 1; }\n",
        "SubjectTest.php",
        ("self::assertSame(1, rl00_value())",),
    ),
    "dart": (
        "lib/subject.dart",
        "int subjectValue(bool enabled) => enabled ? 1 : 0;\n",
        "test/resource_a_test.dart",
        ("expect(subjectValue(name.isNotEmpty), 1)", "expect(subjectValue(false), 0)"),
    ),
    "node": (
        "shared.mjs",
        "export const subjectValue = enabled => enabled ? 1 : 0;",
        "resource-a.test.mjs",
        ("expect(subjectValue(name.length > 0)).toBe(1)", "expect(subjectValue(false)).toBe(0)"),
    ),
}


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid(f"coverage {label} is missing or invalid")
    return cast(dict[str, object], value)


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _numbers(value: object, label: str) -> set[int]:
    if not isinstance(value, list):
        invalid(f"coverage {label} is not a list")
    items = cast(list[object], value)
    if any(not _positive_int(item) for item in items):
        invalid(f"coverage {label} contains an invalid line")
    result = {cast(int, item) for item in items}
    if len(result) != len(items):
        invalid(f"coverage {label} repeats a line")
    return result


def _branches(value: object) -> tuple[int, int]:
    if not isinstance(value, list):
        invalid("coverage branch counts are not a pair")
    items = cast(list[object], value)
    if len(items) != 2 or any(not _nonnegative_int(item) for item in items):
        invalid("coverage branch counts are invalid")
    covered, total = cast(int, items[0]), cast(int, items[1])
    if covered > total:
        invalid("coverage branch counts exceed the total")
    return covered, total


@dataclass
class _Lcov:
    hits: dict[int, int] = field(default_factory=dict[int, int])
    branches: dict[tuple[int, str, str], int] = field(
        default_factory=dict[tuple[int, str, str], int]
    )

    def add_line(self, value: str) -> None:
        parts = value.split(",")
        if len(parts) not in (2, 3):
            invalid("invalid native LCOV line record")
        line, hits = int(parts[0]), int(parts[1])
        if line < 1 or hits < 0:
            invalid("invalid native LCOV line count")
        self.hits[line] = self.hits.get(line, 0) + hits

    def add_branch(self, value: str) -> None:
        head = value.split(",", 2)
        if len(head) != 3 or "," not in head[2]:
            invalid("invalid native LCOV branch record")
        branch, raw_count = head[2].rsplit(",", 1)
        line = int(head[0])
        count = 0 if raw_count == "-" else int(raw_count)
        if line < 1 or count < 0:
            invalid("invalid native LCOV branch count")
        key = (line, head[1], branch)
        self.branches[key] = self.branches.get(key, 0) + count


def _matches_source(root: Path, value: str, targets: set[str]) -> bool:
    path = Path(value)
    absolute = path if path.is_absolute() else root / path
    return os.path.normpath(str(absolute)) in targets


def _lcov(root: Path, report: Path, expected: str) -> _Lcov:
    result = _Lcov()
    active = False
    found = False
    targets = {os.path.normpath(str(base / expected)) for base in (root, root.resolve())}
    for raw in report.read_text(encoding="utf-8").splitlines():
        key, _, value = raw.strip().partition(":")
        if key == "SF":
            active = _matches_source(root, value, targets)
            found |= active
        elif raw.strip() == "end_of_record":
            active = False
        elif active and key == "DA":
            result.add_line(value)
        elif active and key == "BRDA":
            result.add_branch(value)
    if not found:
        invalid(f"native LCOV has no record for {expected}")
    return result


def _subject_line(source: str, subject: str, profile: str) -> int:
    if profile == "node":
        lines = source.splitlines()
        positions = [index for index, line in enumerate(lines, 1) if line == subject]
        if len(positions) != 1:
            invalid("Node subject declaration differs from the registered fixture")
        return positions[0]
    if source != subject:
        invalid(f"{profile} subject differs from the registered fixture")
    return 2 if profile == "php" else 1


def _fixture(root: Path, profile: str) -> tuple[str, int]:
    path, subject, test_path, assertions = SUBJECTS[profile]
    source = (root / path).read_text(encoding="utf-8")
    subject_line = _subject_line(source, subject, profile)
    test_paths = [test_path]
    if profile == "node":
        test_paths.append("resource-b.test.mjs")
    elif profile == "dart":
        test_paths.append("test/resource_b_test.dart")
    for name in test_paths:
        test = (root / name).read_text(encoding="utf-8")
        if any(assertion not in test for assertion in assertions):
            invalid(f"{profile} subject assertions are missing in {name}")
    return path, subject_line


def _parsed(coverage: object, expected: str) -> tuple[set[int], set[int], tuple[int, int]]:
    report = _object(coverage, "report")
    if report.get("branches_measured") is not True:
        invalid("native report did not measure branches")
    files = _object(report.get("files"), "files")
    data = _object(files.get(expected), f"file {expected}")
    if data.get("branches_measured") is not True:
        invalid(f"native file {expected} has unmeasured branches")
    executable = _numbers(data.get("executable"), "executable lines")
    covered = _numbers(data.get("covered"), "covered lines")
    if not covered <= executable:
        invalid("covered lines are not a subset of executable lines")
    return executable, covered, _branches(data.get("branches"))


def _subject_hits(raw: _Lcov, subject_line: int) -> list[int]:
    hits = [count for (line, _, _), count in raw.branches.items() if line == subject_line]
    if len(hits) != 2 or any(count <= 0 for count in hits):
        invalid("both registered subject branches must be recorded and covered")
    return hits


def _compare_lcov(
    root: Path,
    native: Path,
    profile: str,
    expected: str,
    subject_line: int,
    executable: set[int],
    covered: set[int],
    branches: tuple[int, int],
) -> list[int]:
    path = native / ("dart.lcov" if profile == "dart" else "coverage/lcov.info")
    raw = _lcov(root, path, expected)
    actual_lines = set(raw.hits)
    actual_covered = {line for line, hits in raw.hits.items() if hits > 0}
    actual_branches = (sum(hits > 0 for hits in raw.branches.values()), len(raw.branches))
    if (actual_lines, actual_covered, actual_branches) != (executable, covered, branches):
        invalid("core coverage differs from native LCOV lines or branch totals")
    return _subject_hits(raw, subject_line)


def verify(profile: str, root: Path, native: Path, coverage: object) -> dict[str, object]:
    """Return exact measured facts, rejecting missing or inconsistent subject evidence."""
    if profile not in SUBJECTS:
        invalid("unknown coverage fixture profile")
    expected, subject_line = _fixture(root, profile)
    executable, covered, branches = _parsed(coverage, expected)
    if subject_line not in covered:
        invalid(f"subject line {subject_line} was not covered")
    subject_branches: list[int] = []
    if profile in ("node", "dart"):
        subject_branches = _compare_lcov(
            root, native, profile, expected, subject_line, executable, covered, branches
        )
    else:
        expected_lines = {1, 2} if profile == "python" else {2}
        if executable != expected_lines or covered != expected_lines or branches != (0, 0):
            invalid(f"{profile} constant subject coverage differs from its registered facts")
    return {
        "source": expected,
        "subject_line": subject_line,
        "executable": sorted(executable),
        "covered": sorted(covered),
        "missed": sorted(executable - covered),
        "line_total": len(executable),
        "line_covered": len(covered),
        "branch_total": branches[1],
        "branch_covered": branches[0],
        "branch_missed": branches[1] - branches[0],
        "subject_branch_hits": subject_branches,
    }
