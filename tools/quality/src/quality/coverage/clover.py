"""Clover XML reports, as written by PHPUnit with Xdebug branch coverage."""

from __future__ import annotations

import re
from pathlib import Path
from types import MappingProxyType
from xml.etree.ElementTree import Element

from quality.boundedio import ReportError, parse_xml
from quality.coverage.model import Counter, CoverageReport, FileCoverage
from quality.coverage.paths import repository_path

NUMBER = re.compile(r"[0-9]+")


def _attribute(element: Element, name: str, where: str) -> int:
    value = element.get(name)
    if value is None or NUMBER.fullmatch(value) is None:
        msg = f"{where}: <{element.tag}> needs a non-negative integer '{name}'"
        raise ReportError(msg)
    return int(value)


def _statements(element: Element, where: str) -> tuple[frozenset[int], frozenset[int]]:
    executable: set[int] = set()
    covered: set[int] = set()
    for line in element.findall("line"):
        if line.get("type") != "stmt":
            continue
        number = _attribute(line, "num", where)
        if number == 0 or number in executable:
            msg = f"{where}: statement line {number} is invalid or repeated"
            raise ReportError(msg)
        executable.add(number)
        if _attribute(line, "count", where):
            covered.add(number)
    return frozenset(executable), frozenset(covered)


def _file(path: str, element: Element, where: str) -> FileCoverage:
    executable, covered = _statements(element, where)
    metrics = element.find("metrics")
    if metrics is None:
        msg = f"{where}: <file> has no <metrics>"
        raise ReportError(msg)
    declared = (
        _attribute(metrics, "coveredstatements", where),
        _attribute(metrics, "statements", where),
    )
    if declared != (len(covered), len(executable)):
        msg = f"{where}: statement metrics disagree with the <line> records"
        raise ReportError(msg)
    taken = _attribute(metrics, "coveredconditionals", where)
    possible = _attribute(metrics, "conditionals", where)
    if taken > possible:
        msg = f"{where}: more covered conditionals than conditionals"
        raise ReportError(msg)
    return FileCoverage(path, executable, covered, Counter(taken, possible))


def parse_clover(
    data: bytes, origin: str, *, root: Path, cwd: Path, branches_measured: bool
) -> CoverageReport:
    """Parse and cross-check a Clover report; branch counts are per-file conditionals."""
    document = parse_xml(data, origin)
    project = document.find("project") if document.tag == "coverage" else None
    if project is None:
        msg = f"{origin}: not a Clover report (<coverage><project>)"
        raise ReportError(msg)
    files: dict[str, FileCoverage] = {}
    for element in project.iter("file"):
        name = element.get("name")
        if not name:
            msg = f"{origin}: <file> without a name"
            raise ReportError(msg)
        path = repository_path(name, root=root, cwd=cwd)
        if path in files:
            msg = f"{origin}: {path} is reported twice"
            raise ReportError(msg)
        files[path] = _file(path, element, f"{origin} [{path}]")
    return CoverageReport(MappingProxyType(files), branches_measured)
