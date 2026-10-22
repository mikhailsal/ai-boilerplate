"""FR06.2, FR06.3, and FR08: what the Chromium scenarios of a browser component need and leave.

Without the pinned browser the scenarios cannot be verified. A run starts
Node and Chromium and leaves neither a process nor a temporary file, and the
merge gate keeps the native evidence of the build and of every scenario. It
runs without provider variables, and with this template's workflow and `[ci]`
table the two lanes of the gate and the verdict over their jobs stay red
while a scenario fails.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from quality.process import Completed
from quality.testkit.browserscenarios import BOUNDARY, SCENARIOS, SCENARIOS_FILE
from quality.testkit.scratch import Project, output, rules_of, shared_caches

TEMPLATE = Path(__file__).resolve().parents[4]
CI_FILES = (".github/workflows/quality.yml", ".github/CODEOWNERS")
PROVIDER = ("CI", "GITHUB_", "GITLAB_", "CI_", "RUNNER_")
SKIPPED = SCENARIOS.replace('test("the counter counts', 'test.skip("the counter counts')


def merge_check(project: Project) -> tuple[int, set[str], str]:
    """Check every scenario of the committed project."""
    result = project.quality("check", "--stage", "merge", "--all")
    return result.returncode, rules_of(result), output(result)


def without_browser(root: Path) -> dict[str, str]:
    """Return cache variables that reach every cached tool except the pinned Chromium."""
    shared = shared_caches(os.environ)
    quality = Path(shared["XDG_CACHE_HOME"]) / "quality"
    toolchains = root / "quality" / "toolchains"
    toolchains.mkdir(parents=True)
    for entry in quality.iterdir():
        if entry.name != "toolchains":
            (root / "quality" / entry.name).symlink_to(entry)
    for entry in (quality / "toolchains").iterdir():
        if not entry.name.startswith("chromium-"):
            (toolchains / entry.name).symlink_to(entry)
    return {**shared, "XDG_CACHE_HOME": str(root)}


def test_scenarios_without_their_browser_cannot_be_verified(
    counter: Project, tmp_path: Path
) -> None:
    status, rules, printed = merge_check(replace(counter, caches=without_browser(tmp_path)))
    assert (status, rules) == (3, {"tools.missing", "scenarios.unverified"}), printed
    assert "chromium" in printed, printed


def processes_naming(directory: Path) -> list[str]:
    """Return the command lines of the running processes that name `directory`."""
    found: list[str] = []
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            text = cmdline.read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if str(directory) in text:
            found.append(text)
    return found


def test_a_run_leaves_no_process_or_temporary_file(counter: Project, tmp_path: Path) -> None:
    temporary = tmp_path / "tmp"
    temporary.mkdir()
    project = replace(counter, caches={**shared_caches(os.environ), "TMPDIR": str(temporary)})
    seen: set[str] = set()
    with ThreadPoolExecutor(1) as pool:
        running = pool.submit(merge_check, project)
        while not running.done():
            seen.update(Path(line.split()[0]).name for line in processes_naming(temporary))
            time.sleep(0.1)
        status, rules, printed = running.result()
    assert (status, rules) == (0, set()), printed
    assert {"node", "chrome-headless-shell"} <= seen, seen
    assert processes_naming(temporary) == []
    assert list(temporary.iterdir()) == []


def test_the_gate_keeps_the_native_evidence_of_the_scenarios(
    counter: Project, tmp_path: Path
) -> None:
    base = counter.head()
    counter.repo.git("checkout", "-q", "--detach")
    try:
        counter.write("README.md", "# Scratch project\n\nSee [agents](AGENTS.md).\n")
        counter.repo.git("commit", "-q", "--no-verify", "-am", "describe the project")
        reports = tmp_path / "reports"
        revisions = ("--base", base, "--head", counter.head())
        result = counter.quality("gate", "--stage", "merge", *revisions, "--reports", str(reports))
    finally:
        counter.repo.git("checkout", "-q", "-")
    assert [name for name in counter.environ() if name.startswith(PROVIDER)] == []
    assert result.returncode == 0, output(result)
    native = reports / "native" / "web" / "e2e"
    assert sorted(path.name for path in native.iterdir()) == [
        "build.json",
        "playwright.json",
        "playwright.log",
    ]
    build = json.loads((native / "build.json").read_text())
    assert build["base"] == "/"
    assert "index.html" in build["files"]
    results = json.loads((native / "playwright.json").read_text())
    runs = sorted(
        (test["project"], test["title"][-1], test["outcome"]) for test in results["tests"]
    )
    assert runs == [
        (project, title, "expected")
        for project in ("narrow", "wide")
        for title in ("the counter counts from the keyboard", "the page shows the counter")
    ]
    report = json.loads((reports / "report.json").read_text())
    assert BOUNDARY in json.dumps(report)


def ci_table() -> str:
    """Return the `[ci]` table of this template's policy."""
    policy = (TEMPLATE / "quality.toml").read_text()
    start = policy.index("\n[ci]\n")
    return policy[start : policy.index("\n[", start + 1)] + "\n"


def lanes(project: Project, base: str, needs: Path) -> tuple[Completed, Completed, Completed]:
    """Run both lanes of the merge gate over the new commit, then the verdict over their jobs."""
    revisions = ("--stage", "merge", "--base", base, "--head", project.head())
    main = project.quality("gate", *revisions, "--lane", "main")
    browser = project.quality("gate", *revisions, "--lane", "browser")
    jobs = {"gate": main.returncode, "browser": browser.returncode, "audit": 0}
    results = {job: {"result": "failure" if code else "success"} for job, code in jobs.items()}
    needs.write_text(json.dumps(results))
    return main, browser, project.quality("ci", "verdict", "--needs", str(needs))


def test_the_lanes_and_the_verdict_stay_red_while_a_scenario_fails(
    counter: Project, tmp_path: Path
) -> None:
    base = counter.head()
    needs = tmp_path / "needs.json"
    counter.repo.git("checkout", "-q", "--detach")
    try:
        for path in CI_FILES:
            counter.write(path, (TEMPLATE / path).read_text())
        counter.write("quality.toml", (counter.path / "quality.toml").read_text() + ci_table())
        counter.repo.git("add", "-A")
        counter.repo.git("commit", "-q", "--no-verify", "-m", "add the template's workflow")
        passing = lanes(counter, base, needs)
        counter.write(f"web/{SCENARIOS_FILE}", SKIPPED)
        counter.repo.git("commit", "-q", "--no-verify", "-am", "skip a scenario")
        failing = lanes(counter, base, needs)
    finally:
        counter.repo.git("checkout", "-q", "-")
    main, browser, verdict = passing
    assert [run.returncode for run in passing] == [0, 0, 0], [output(run) for run in passing]
    assert "lane main: the browser lane checks web" in output(main), output(main)
    assert "scenarios of web: 2 of 2 proved" in output(browser), output(browser)
    main, browser, verdict = failing
    assert main.returncode == 0, output(main)
    found = (browser.returncode, rules_of(browser))
    assert found == (1, {"gate.lane", "tests.skipped", "scenarios.skipped"}), output(browser)
    assert (verdict.returncode, rules_of(verdict)) == (1, {"ci.job-failed"}), output(verdict)
    assert "required job 'browser' finished with 'failure'" in output(verdict)
