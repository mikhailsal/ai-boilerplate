"""FR06.2 and FR06.3: what the Chromium scenarios of a browser component need and leave.

Without the pinned browser the scenarios cannot be verified. A run starts
Node and Chromium and leaves neither a process nor a temporary file, and the
merge gate keeps the native evidence of the build and of every scenario.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from quality.testkit.browserscenarios import BOUNDARY
from quality.testkit.scratch import Project, output, rules_of, shared_caches


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
