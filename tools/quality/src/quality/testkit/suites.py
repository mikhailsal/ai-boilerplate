"""A scripted profile test runner for engine tests: it writes exactly the reports it is told to."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from quality.coverage import CoverageReport, parse_coverage_json
from quality.testing import Outcome, Suite, SuiteRequest, SuiteRun
from quality.testkit.reports import FileSpec, coverage_json, junit_xml

type Cases = tuple[tuple[str, Outcome], ...]
type Hook = Callable[[SuiteRequest, SuiteRun], SuiteRun]


@dataclass(frozen=True, slots=True)
class Script:
    """What one suite run reports; `files` None writes no coverage report.

    Coverage paths are relative to the component root, where native tools run.
    """

    cases: Cases = (("test_ok", Outcome.PASSED),)
    returncode: int = 0
    files: Mapping[str, FileSpec] | None = None
    branch: bool = True


@dataclass(slots=True)
class ScriptedRunner:
    """Runs no tests; writes each script's reports and records every request.

    `hook` can replace the run after the reports are written, to simulate a
    misbehaving runner.
    """

    scripts: Mapping[tuple[str, Suite], Script]
    hook: Hook | None = None
    requests: list[SuiteRequest] = field(default_factory=list[SuiteRequest])
    parsed: list[tuple[str, Suite]] = field(default_factory=list[tuple[str, Suite]])
    fresh: list[bool] = field(default_factory=list[bool])

    def expected(self, path: str) -> bool:
        """Expect Python source files."""
        return path.endswith(".py")

    def run(self, request: SuiteRequest) -> SuiteRun:
        """Write the scripted reports into the request's output directory."""
        self.requests.append(request)
        self.fresh.append(not any(request.output.iterdir()))
        script = self.scripts.get((request.component.id, request.suite), Script())
        results = request.output / "junit.xml"
        results.write_bytes(junit_xml(script.cases))
        run = SuiteRun(script.returncode, results)
        if script.files is not None:
            report = request.output / "coverage.json"
            report.write_bytes(coverage_json(script.files, branch=script.branch))
            run = SuiteRun(script.returncode, results, report)
        return self.hook(request, run) if self.hook is not None else run

    def coverage(self, data: bytes, request: SuiteRequest) -> CoverageReport:
        """Parse the coverage.py JSON report relative to the component directory."""
        self.parsed.append((request.component.id, request.suite))
        return parse_coverage_json(
            data, "coverage.json", root=request.snapshot, cwd=request.directory
        )
