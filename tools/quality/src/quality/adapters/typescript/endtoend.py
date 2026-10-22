"""The end-to-end suites of a browser component: build, serve, and drive Chromium (decision 0018).

A run first builds the candidate into a new directory of the run; a build
that fails leaves nothing to test, so the suite cannot run. The build's
evidence is kept with the run's reports, and its boundary and output findings
join the suite's. The gate's server then serves that output while Playwright
Test runs the suite in the pinned Chromium, one project per viewport, and
stops when the run ends. The run's results are judged with what the tests
left behind: console and page errors from each trace, the requests the server
could not answer, and each attached accessibility scan. A case has the
`accessibility-scan` evidence only when its test attached a valid scan in
every viewport.
"""

from __future__ import annotations

import json
import posixpath
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from quality.adapters import native
from quality.adapters.native import ToolFailedError
from quality.adapters.settings import load_json_object
from quality.adapters.typescript import scans, traces
from quality.adapters.typescript.browser import browser_sources
from quality.adapters.typescript.build import BuildOutcome, BuildRequest, production_build
from quality.adapters.typescript.bundle import Output
from quality.adapters.typescript.environment import Node, package_directory
from quality.adapters.typescript.playwright import LOG, run_playwright, settings
from quality.adapters.typescript.serve import serve
from quality.boundedio import ReportError, read_bounded
from quality.diagnostics import Diagnostic
from quality.policy import Component
from quality.testing import (
    ACCESSIBILITY_SCAN,
    PlaywrightReport,
    PlaywrightTest,
    ResultsFormat,
    SuiteRequest,
    SuiteRun,
    read_playwright,
)

BUILD_EVIDENCE = "build.json"
AXE_ADAPTER = "@axe-core/playwright"
TOOL = "axe-core"
TRACE = "trace"


@dataclass(frozen=True, slots=True)
class BrowserTools:
    """What a browser run uses: Node, the locked Vite and Playwright, Chromium, and axe-core."""

    node: Node
    vite: Path
    playwright: Path
    browser: Path
    axe: str


def locked_axe(directory: Path, top: Path) -> str:
    """Return the version of the axe-core that the component's `@axe-core/playwright` loads."""
    adapter = package_directory(AXE_ADAPTER, directory, top)
    engine = None if adapter is None else package_directory(scans.ENGINE, adapter, top)
    if engine is None:
        native.fail(TOOL, f"{AXE_ADAPTER} and its {scans.ENGINE} are not installed for {directory}")
    try:
        version = load_json_object(engine / "package.json").get("version")
    except ReportError as error:
        native.fail(TOOL, str(error))
    if not isinstance(version, str):
        native.fail(TOOL, f"{engine} names no version")
    return version


def repository_file(component: Component, file: str) -> str:
    """Return the repository path of a file relative to the component directory."""
    return posixpath.normpath(posixpath.join(component.root, file))


def build(tools: BrowserTools, request: SuiteRequest) -> tuple[BuildOutcome, Output]:
    """Build the candidate; raise ToolFailedError when there is no output to serve."""
    component = request.component
    outcome = production_build(
        tools.node,
        tools.vite,
        BuildRequest(
            component,
            request.snapshot,
            request.output / "build",
            request.files,
            frozenset(browser_sources(component, request.files)),
            request.tree,
        ),
    )
    if outcome.output is None:
        raise ToolFailedError(outcome.diagnostics[0])
    return outcome, outcome.output


def _unique(findings: list[Diagnostic]) -> list[Diagnostic]:
    seen: dict[tuple[object, ...], Diagnostic] = {}
    for found in findings:
        key = (found.rule, found.severity, found.message, found.location, *found.data.items())
        seen.setdefault(key, found)
    return list(seen.values())


@dataclass(slots=True)
class Examination:
    """What the tests of one run left behind, judged test by test."""

    component: Component
    policy: scans.ScanPolicy
    findings: list[Diagnostic]
    requested: dict[str, tuple[str, str]]
    scanned: dict[str, set[str]]

    def test(self, test: PlaywrightTest) -> None:
        """Read one test's traces and judge its scans."""
        component, file = self.component.id, repository_file(self.component, test.file)
        for path in test.attached(TRACE):
            events = traces.read_trace(Path(path), self.policy.origin)
            self.findings += traces.console_findings(component, file, test.name, events)
            for url in events.failed:
                self.requested.setdefault(traces.request_path(url), (file, test.name))
        for path in test.attached(scans.ATTACHMENT):
            scan = scans.judge(
                Path(path), self.policy, component=component, file=file, test=test.name
            )
            if scan.problem is not None:
                self.findings.append(scans.invalid(component, file, test.name, scan.problem))
            else:
                self.findings += scan.findings
                self.scanned.setdefault(test.name, set()).add(test.project)

    def missing(self, paths: tuple[str, ...]) -> Iterator[Diagnostic]:
        """Report each request the server could not answer, with a test that made it."""
        entry = repository_file(self.component, self.component.browser_settings.entries[0])
        for path in paths:
            file, test = self.requested.get(traces.request_path(path), (entry, None))
            yield traces.resource_finding(self.component.id, file, test, path)


def examine(
    component: Component,
    report: PlaywrightReport,
    missing: tuple[str, ...],
    policy: scans.ScanPolicy,
) -> tuple[dict[str, frozenset[str]], list[Diagnostic]]:
    """Return the evidence of each case and the findings of the tests and the server."""
    examination = Examination(component, policy, [], {}, {})
    for test in report.tests:
        examination.test(test)
    findings = [*examination.findings, *examination.missing(missing)]
    projects = set(report.projects)
    evidence = {
        name: frozenset({ACCESSIBILITY_SCAN})
        for name, scanned in examination.scanned.items()
        if scanned >= projects
    }
    return evidence, _unique(findings)


def run_browser_suite(tools: BrowserTools, request: SuiteRequest) -> SuiteRun:
    """Build, serve, and run one end-to-end suite of a browser component."""
    component = request.component
    outcome, output = build(tools, request)
    evidence_file = request.output / BUILD_EVIDENCE
    record = {**output.evidence(), "base": outcome.base}
    evidence_file.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with serve(output, outcome.base, component.browser_settings.entries[0]) as server:
        values = settings(request, server.url, tools.browser)
        status, results = run_playwright(tools.node, tools.playwright, request, values)
    report = read_playwright(read_bounded(results), "test results")
    tags = frozenset(component.browser_settings.accessibility_tags)
    policy = scans.ScanPolicy(tools.axe, tags, server.origin)
    evidence, findings = examine(component, report, server.requests.missing(), policy)
    return SuiteRun(
        status,
        results,
        results_format=ResultsFormat.PLAYWRIGHT,
        unhandled=len(report.errors),
        evidence=evidence,
        findings=(*outcome.diagnostics, *findings),
        reports=(evidence_file, request.output / LOG),
    )
