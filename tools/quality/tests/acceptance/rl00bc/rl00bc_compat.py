"""Native report reconciliation experiment; execution is restricted to CI.

The trial artifacts are the only input to the actual quality parsers. A parsed
report is evidence of adapter compatibility, not proof that the fixture tests a
meaningful source behavior. Missing fixture contracts remain explicit gaps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_kernel, rl00bc_trials

# Executed by the pinned quality Python, not the controller's interpreter.
# Keep the parser's output separate from its bounded kernel stdout.
_PARSER = r'''
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
'''


def _identities(cases: object) -> dict[str, str]:
    if not isinstance(cases, list) or not cases:
        raise ValueError("native suite contains no identities")
    result: dict[str, str] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("invalid native case")
        name, outcome = case.get("id"), case.get("outcome")
        if not isinstance(name, str) or not name or not isinstance(outcome, str) or not outcome:
            raise ValueError("missing native case identity or outcome")
        if name in result:
            raise ValueError(f"duplicate native identity: {name}")
        result[name] = outcome
    return result


def reconcile(work: Group, repo: Path, scratch: Path, output: Path, profile: str,
              environment: dict[str, str], *, ancestor_deadline_ns: int) -> dict[str, object]:
    """Run one canonical trial and compare its reports through quality's parsers.

    Providers may supply ``scenarios.toml`` in their generated root. Its component
    is ``rl00bc`` and selectors must be actual parser case names. To establish
    meaningful parity, providers also need source assertions and (for browser)
    the quality Playwright reporter and attached trace evidence.
    """
    if profile not in rl00bc_trials.PROVIDERS:
        raise ValueError("unknown profile")
    output.mkdir(parents=True, exist_ok=False)
    native_env = {key: value for key, value in environment.items() if key in rl00bc_trials.PATH_KEYS}
    trial = rl00bc_trials.one(work, repo, scratch, output / "canonical", profile, native_env,
                              size="small", coverage=profile != "browser",
                              ancestor_deadline_ns=ancestor_deadline_ns)
    gaps: list[str] = []
    errors: list[str] = []
    try:
        native_ids = _identities(trial.get("native_cases"))
    except ValueError as error:
        native_ids = {}
        errors.append(str(error))
    if trial.get("classification") != "observed-success":
        errors.append("canonical native trial did not pass")
    plan = json.loads(Path(cast(str, trial["native_plan"])).read_text(encoding="utf-8"))
    root = Path(plan["cwd"])
    native = output.absolute() / "canonical" / "native"
    parser_result = output.absolute() / "parsed.json"
    home = root / "home"
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home),
           "TMPDIR": str(root / "tmp"), "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": str(repo.absolute() / "tools/quality/src"), "CI": "1"}
    parser = Path(native_env.get("RL00_PYTHON", ""))
    if not parser.is_absolute() or not parser.is_file():
        raise ValueError("RL00_PYTHON must be the pinned quality Python interpreter")
    formatter: dict[str, object] | None = None
    if profile == "dart":
        dart = Path(native_env.get("RL00_DART", ""))
        if not dart.is_absolute() or not dart.is_file():
            raise ValueError("RL00_DART must name the pinned Dart executable")
        formatter = rl00bc_kernel.execute(work, [str(dart), "run", "coverage:format_coverage",
            "--lcov", f"--in={native / 'coverage'}", f"--out={native / 'dart.lcov'}",
            f"--package={root}", f"--report-on={root / 'lib'}"], root, env,
            output / "formatter", memory_mib=3072, tasks=256, native_seconds=60,
            ancestor_deadline_ns=ancestor_deadline_ns)
        if not formatter.get("success") or not formatter.get("cleanup_complete"):
            errors.append("Dart coverage formatter failed")
    parsed_kernel = rl00bc_kernel.execute(work, [str(parser), "-c", _PARSER, profile,
        str(root), str(native), str(parser_result)], root, env, output / "parser",
        memory_mib=3072, tasks=256, native_seconds=60,
        ancestor_deadline_ns=ancestor_deadline_ns)
    parsed: dict[str, object] = {}
    if parsed_kernel.get("success") and parsed_kernel.get("cleanup_complete") and parser_result.is_file():
        parsed = json.loads(parser_result.read_text(encoding="utf-8"))
        errors.extend(cast(list[str], parsed.get("errors", [])))
    else:
        errors.append("quality parser process failed or left no result")
    try:
        parsed_ids = _identities(parsed.get("cases"))
        if profile in ("python", "php"):
            if native_ids != parsed_ids:
                errors.append("native and adapter identities or outcomes differ")
        elif profile == "browser":
            browser = parsed.get("browser_projects")
            if not isinstance(browser, dict) or set(browser.get("projects", [])) != {"desktop", "mobile"}:
                errors.append("browser project declarations differ")
            else:
                adapted: dict[str, str] = {}
                for item in browser.get("tests", []):
                    name = str(item["id"]).removeprefix("resource.test.mjs::")
                    key = f"{name}[{item['project']}]"
                    if key in adapted or not item.get("traces"):
                        errors.append(f"duplicate browser identity or missing trace: {key}")
                    adapted[key] = str(item["outcome"])
                normalized = {key: "passed" if value == "expected" else value for key, value in native_ids.items()}
                if normalized != adapted:
                    errors.append("browser native project identities or outcomes differ")
        else:
            # Vitest JUnit includes a file/class prefix; Dart may include its
            # test root. Compare exact suffixes and preserve one-to-one mapping.
            unmatched = set(parsed_ids)
            for name, outcome in native_ids.items():
                matches = [value for value in unmatched if value == name or value.endswith("::" + name)]
                normalized_outcome = "passed" if outcome == "success" else outcome
                if len(matches) != 1 or parsed_ids[matches[0]] != normalized_outcome:
                    errors.append(f"native identity/outcome has no unique adapter match: {name}")
                else:
                    unmatched.remove(matches[0])
            if unmatched:
                errors.append("adapter reports additional native identities")
    except ValueError as error:
        errors.append(str(error))
    if profile != "browser":
        coverage = parsed.get("coverage")
        files = coverage.get("files") if isinstance(coverage, dict) else None
        expected = {"python": "src/subject.py", "php": "subject.php", "node": "shared.mjs", "dart": "lib/subject.dart"}[profile]
        if not isinstance(files, dict) or expected not in files:
            errors.append(f"native source coverage is missing {expected}")
        elif not files[expected].get("covered"):
            errors.append(f"native source coverage has no executed lines: {expected}")
        # Fixture source assertions are required independently of raw coverage.
        # They are encoded by each provider, not inferred from coverage counts.
    scenario = parsed.get("scenario")
    if not isinstance(scenario, dict) or not scenario.get("required") or scenario.get("passed") != scenario.get("required") or scenario.get("findings"):
        gaps.append("provider must supply and pass a real scenario manifest mapped to native case IDs")
    result: dict[str, object] = {"profile": profile, "trial": trial, "formatter": formatter,
        "parser_kernel": parsed_kernel, "parsed": parsed, "errors": errors, "gaps": gaps,
        "verdict": "pass" if not errors and not gaps else "unproved"}
    (output / "compatibility.json").write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    return result
