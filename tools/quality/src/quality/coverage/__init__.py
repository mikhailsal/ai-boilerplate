"""Coverage: the normalized model and parsers of native coverage reports (no subprocesses)."""

from quality.coverage.clover import parse_clover
from quality.coverage.lcov import parse_lcov
from quality.coverage.model import EMPTY, Counter, CoverageReport, FileCoverage, total
from quality.coverage.paths import repository_path
from quality.coverage.python import parse_coverage_json

__all__ = [
    "EMPTY",
    "Counter",
    "CoverageReport",
    "FileCoverage",
    "parse_clover",
    "parse_coverage_json",
    "parse_lcov",
    "repository_path",
    "total",
]
