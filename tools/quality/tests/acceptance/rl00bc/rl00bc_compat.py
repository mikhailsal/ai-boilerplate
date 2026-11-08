"""Native report reconciliation experiment; execution is restricted to CI.

The trial artifacts are the only input to the actual quality parsers. A parsed
report is evidence of adapter compatibility, not proof that the fixture tests a
meaningful source behavior. Missing fixture contracts remain explicit gaps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_kernel, rl00bc_trials
from tests.acceptance.rl00bc.rl00bc_compat_parser import PARSER
from tests.acceptance.rl00bc.rl00bc_errors import invalid, wrong_type

def _identities(cases: object) -> dict[str, str]:
    if not isinstance(cases, list) or not cases:
        invalid("native suite contains no identities")
    result: dict[str, str] = {}
    for item in cast(list[object], cases):
        if not isinstance(item, dict):
            wrong_type("invalid native case")
        case = cast(dict[str, object], item)
        name, outcome = case.get("id"), case.get("outcome")
        if not isinstance(name, str) or not name or not isinstance(outcome, str) or not outcome:
            invalid("missing native case identity or outcome")
        if name in result:
            invalid(f"duplicate native identity: {name}")
        result[name] = outcome
    return result


def _browser_tests(tests: list[object], errors: list[str]) -> dict[str, str]:
    adapted: dict[str, str] = {}
    for value in tests:
        if not isinstance(value, dict):
            errors.append("invalid browser test declaration")
            continue
        item = cast(dict[str, object], value)
        name = str(item["id"]).removeprefix("resource.test.mjs::")
        key = f"{name}[{item['project']}]"
        if key in adapted or not item.get("traces"):
            errors.append(f"duplicate browser identity or missing trace: {key}")
        adapted[key] = str(item["outcome"])
    return adapted


def _browser_ids(browser: object, native_ids: dict[str, str], errors: list[str]) -> None:
    if not isinstance(browser, dict):
        errors.append("browser project declarations differ")
        return
    data = cast(dict[str, object], browser)
    projects = data.get("projects")
    if not isinstance(projects, list) or set(cast(list[str], projects)) != {"desktop", "mobile"}:
        errors.append("browser project declarations differ")
        return
    tests = data.get("tests")
    if not isinstance(tests, list):
        errors.append("browser test declarations missing")
        return
    adapted = _browser_tests(cast(list[object], tests), errors)
    normalized = {key: "passed" if value == "expected" else value
                  for key, value in native_ids.items()}
    if normalized != adapted:
        errors.append("browser native project identities or outcomes differ")


def _compare_dart_or_node(
    native_ids: dict[str, str], parsed_ids: dict[str, str], errors: list[str]
) -> None:
    unmatched = set(parsed_ids)
    for name, outcome in native_ids.items():
        matches = [value for value in unmatched if value == name or value.endswith("::" + name)]
        normalized = "passed" if outcome == "success" else outcome
        if len(matches) != 1 or parsed_ids[matches[0]] != normalized:
            errors.append(f"native identity/outcome has no unique adapter match: {name}")
        else:
            unmatched.remove(matches[0])
    if unmatched:
        errors.append("adapter reports additional native identities")


def _compare_ids(profile: str, native_ids: dict[str, str], parsed: dict[str, object],
                 errors: list[str]) -> None:
    try:
        parsed_ids = _identities(parsed.get("cases"))
        if profile in ("python", "php"):
            if native_ids != parsed_ids:
                errors.append("native and adapter identities or outcomes differ")
        elif profile == "browser":
            _browser_ids(parsed.get("browser_projects"), native_ids, errors)
        else:
            _compare_dart_or_node(native_ids, parsed_ids, errors)
    except ValueError, TypeError as error:
        errors.append(str(error))


@dataclass
class _Reconciliation:
    work: Group
    repo: Path
    output: Path
    profile: str
    environment: dict[str, str]
    ancestor_deadline_ns: int
    trial: dict[str, object]
    errors: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    native_ids: dict[str, str] = field(default_factory=dict)
    root: Path = field(init=False)
    native: Path = field(init=False)
    parser_result: Path = field(init=False)
    env: dict[str, str] = field(init=False)

    def initialize(self) -> None:
        try:
            self.native_ids = _identities(self.trial.get("native_cases"))
        except (ValueError, TypeError) as error:
            self.errors.append(str(error))
        if self.trial.get("classification") != "observed-success":
            self.errors.append("canonical native trial did not pass")
        plan_path = Path(cast(str, self.trial["native_plan"]))
        plan = cast(dict[str, object], json.loads(plan_path.read_text(encoding="utf-8")))
        self.root = Path(cast(str, plan["cwd"]))
        self.native = self.output.absolute() / "canonical" / "native"
        self.parser_result = self.output.absolute() / "parsed.json"
        self.env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.root / "home"),
            "TMPDIR": str(self.root / "tmp"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(self.repo.absolute() / "tools/quality/src"),
            "CI": "1",
        }

    def executable(self, key: str, message: str) -> Path:
        path = Path(self.environment.get(key, ""))
        if not path.is_absolute() or not path.is_file():
            invalid(message)
        return path

    def format_dart(self) -> dict[str, object] | None:
        if self.profile != "dart":
            return None
        dart = self.executable("RL00_DART", "RL00_DART must name the pinned Dart executable")
        result = rl00bc_kernel.execute(
            self.work,
            [
                str(dart), "run", "coverage:format_coverage", "--lcov",
                f"--in={self.native / 'coverage'}", f"--out={self.native / 'dart.lcov'}",
                f"--package={self.root}", f"--report-on={self.root / 'lib'}",
            ],
            self.root, self.env, self.output / "formatter", memory_mib=3072, tasks=256,
            native_seconds=60, ancestor_deadline_ns=self.ancestor_deadline_ns,
        )
        if not result.get("success") or not result.get("cleanup_complete"):
            self.errors.append("Dart coverage formatter failed")
        return result

    def parse(self) -> tuple[dict[str, object], dict[str, object]]:
        parser = self.executable(
            "RL00_PYTHON", "RL00_PYTHON must be the pinned quality Python interpreter"
        )
        kernel = rl00bc_kernel.execute(
            self.work,
            [str(parser), "-c", PARSER, self.profile, str(self.root), str(self.native),
             str(self.parser_result)],
            self.root, self.env, self.output / "parser", memory_mib=3072, tasks=256,
            native_seconds=60, ancestor_deadline_ns=self.ancestor_deadline_ns,
        )
        if not kernel.get("success") or not kernel.get("cleanup_complete"):
            self.errors.append("quality parser process failed or left no result")
            return kernel, {}
        if not self.parser_result.is_file():
            self.errors.append("quality parser process failed or left no result")
            return kernel, {}
        parsed = cast(dict[str, object], json.loads(self.parser_result.read_text(encoding="utf-8")))
        self.errors.extend(cast(list[str], parsed.get("errors", [])))
        return kernel, parsed

    def coverage(self, parsed: dict[str, object]) -> None:
        if self.profile == "browser":
            return
        coverage = parsed.get("coverage")
        files = (
            cast(dict[str, object], coverage).get("files") if isinstance(coverage, dict) else None
        )
        expected = {
            "python": "src/subject.py", "php": "subject.php", "node": "shared.mjs",
            "dart": "lib/subject.dart",
        }[self.profile]
        if not isinstance(files, dict) or expected not in files:
            self.errors.append(f"native source coverage is missing {expected}")
            return
        file_data = cast(dict[str, object], files).get(expected)
        if not isinstance(file_data, dict) or not cast(dict[str, object], file_data).get("covered"):
            self.errors.append(f"native source coverage has no executed lines: {expected}")

    def scenario(self, parsed: dict[str, object]) -> None:
        scenario = parsed.get("scenario")
        data = cast(dict[str, object], scenario) if isinstance(scenario, dict) else {}
        if (
            not data.get("required")
            or data.get("passed") != data.get("required")
            or data.get("findings")
        ):
            self.gaps.append(
                "provider must supply and pass a real scenario manifest mapped to native case IDs"
            )

    def run(self) -> dict[str, object]:
        self.initialize()
        self.executable("RL00_PYTHON", "RL00_PYTHON must be the pinned quality Python interpreter")
        formatter = self.format_dart()
        kernel, parsed = self.parse()
        _compare_ids(self.profile, self.native_ids, parsed, self.errors)
        self.coverage(parsed)
        self.scenario(parsed)
        result: dict[str, object] = {
            "profile": self.profile, "trial": self.trial, "formatter": formatter,
            "parser_kernel": kernel, "parsed": parsed, "errors": self.errors, "gaps": self.gaps,
            "verdict": "pass" if not self.errors and not self.gaps else "unproved",
        }
        (self.output / "compatibility.json").write_text(
            json.dumps(result, sort_keys=True) + "\n", encoding="utf-8"
        )
        return result


def reconcile(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    profile: str,
    environment: dict[str, str],
    *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Run one canonical trial and compare its reports through quality's parsers."""
    if profile not in rl00bc_trials.PROVIDERS:
        invalid("unknown profile")
    output.mkdir(parents=True, exist_ok=False)
    native_env = {
        key: value for key, value in environment.items() if key in rl00bc_trials.PATH_KEYS
    }
    trial = rl00bc_trials.one(
        work, repo, scratch, output / "canonical", profile, native_env, size="small",
        coverage=profile != "browser", ancestor_deadline_ns=ancestor_deadline_ns,
    )
    return _Reconciliation(
        work, repo, output, profile, native_env, ancestor_deadline_ns, trial
    ).run()
