"""Pinned-core parser program for native compatibility evidence."""

PARSER = r"""
import json, sys, zipfile
from pathlib import Path
from quality.coverage.python import parse_coverage_json
from quality.coverage.lcov import parse_lcov
from quality.coverage.phpunit import JsonlReport, parse_phpunit
from quality.testing import parse_junit, parse_dart_json, parse_playwright
from quality.testing.playwright import read_playwright
from quality.scenarios.manifest import parse_manifest
from quality.scenarios.reconcile import reconcile

profile, root_text, native_text, result_text = sys.argv[1:]
root, native, destination = Path(root_text), Path(native_text), Path(result_text)
result = {"errors": [], "coverage": None, "cases": None, "scenario": None}
def attempt(label, action):
    try:
        return action()
    except Exception as error:
        result["errors"].append(label + ": " + type(error).__name__ + ": " + str(error)[:1000])
        return None

def results():
    if profile == "dart":
        path, parser = native / "dart.json", parse_dart_json
    elif profile == "browser":
        # The gate expects its own reporter format; Playwright's built-in JSON
        # is deliberately not converted into invented adapter evidence.
        path, parser = native / "quality-playwright.json", parse_playwright
    else:
        path, parser = native / "junit.xml", parse_junit
    return parser(path.read_bytes(), str(path))

parsed = attempt("native results", results)
if parsed is not None:
    result["cases"] = [{"id": c.name, "outcome": str(c.outcome)} for c in parsed.cases]
if profile == "browser":
    def browser_projects():
        path = native / "quality-playwright.json"
        report = read_playwright(path.read_bytes(), str(path))
        def valid_trace(path):
            with zipfile.ZipFile(path) as trace:
                return bool(trace.namelist()) and trace.testzip() is None
        return {"projects": list(report.projects), "tests": [
            {"id": t.name, "project": t.project, "outcome": str(t.outcome),
             "traces": [p for p in t.attached("trace") if Path(p).is_file() and valid_trace(p)]}
            for t in report.tests]}
    result["browser_projects"] = attempt("browser projects", browser_projects)

def coverage():
    if profile == "python":
        path = native / "coverage.json"
        return parse_coverage_json(path.read_bytes(), str(path), root=root, cwd=root)
    if profile == "php":
        directory = native / "coverage-jsonl"
        raw = JsonlReport((directory / "meta.json").read_bytes(),
                          (directory / "coverage.jsonl").read_bytes(),
                          (directory / "tests.jsonl").read_bytes())
        return parse_phpunit((native / "clover.xml").read_bytes(), raw, root=root, cwd=root)
    path = native / ("dart.lcov" if profile == "dart" else "coverage/lcov.info")
    return parse_lcov(path.read_bytes(), str(path), root=root, cwd=root, branches_measured=True)

if profile != "browser":
    report = attempt("native coverage", coverage)
    if report is not None:
        result["coverage"] = {"branches_measured": report.branches_measured,
            "files": {name: {"executable": sorted(f.executable), "covered": sorted(f.covered),
                "branches": [f.branches.covered, f.branches.total],
                "branches_measured": f.branches_measured} for name, f in report.files.items()}}

# A provider must create this manifest with its actual native result selectors.
# Never synthesize scenario IDs or populate outcomes from an unrelated probe.
manifest = root / "scenarios.toml"
if manifest.is_file() and parsed is not None:
    def scenario():
        load = parse_manifest(manifest.read_bytes(), str(manifest), "rl00bc")
        if load.manifest is None:
            raise ValueError("invalid scenario manifest: " + str(load.diagnostics))
        findings, summary = reconcile(load.manifest, str(manifest), lambda _: True,
                                      {s.level: parsed for s in load.manifest.scenarios}, ())
        return {"required": summary.required, "passed": summary.passed,
                "suspended": summary.suspended, "findings": [str(f) for f in findings]}
    result["scenario"] = attempt("scenario reconciliation", scenario)
else:
    result["errors"].append("scenario: missing provider manifest or parsed suite results")
destination.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
"""
