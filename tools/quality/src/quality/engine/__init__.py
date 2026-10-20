"""Orchestration: run the gates and the test suites over a candidate."""

from quality.engine.check import RULES, Report, Settings, Tools, check_candidate
from quality.engine.history import check_history
from quality.engine.links import check_links
from quality.engine.runs import ProfileTests
from quality.engine.suites import SuiteReport, SuiteSettings, run_suites

__all__ = [
    "RULES",
    "ProfileTests",
    "Report",
    "Settings",
    "SuiteReport",
    "SuiteSettings",
    "Tools",
    "check_candidate",
    "check_history",
    "check_links",
    "run_suites",
]
