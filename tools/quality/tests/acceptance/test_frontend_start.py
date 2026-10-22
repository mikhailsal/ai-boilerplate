"""FR02.5, FR10.1, and F07: browser applications in projects made from the template.

Each test exports a project from a copy of the candidate and runs the browser
Quick start of the exported README.md as written, line by line in a shell:
the reference application is copied, registered, staged, bootstrapped, and
committed through the real hook, and then its unit and end-to-end suites run
with `quality test`. A TypeScript Node project bootstraps and commits with a
cache that holds no browser, and later adds a frontend; two frontends from
the same Quick start pass the hook and the browser lane of the gate.
"""

import re
from collections.abc import Callable
from pathlib import Path

from quality.process import Completed
from quality.testkit.scratch import Project, output
from quality.testkit.typescriptproject import typescript_project

type Export = Callable[..., Project]
type Caches = Callable[..., dict[str, str]]

QUICK_START = re.compile(r"### A browser application\n.*?```sh\n(.*?)```", re.DOTALL)
# The tools of the core's common gates and of the TypeScript profile, no browser.
NODE_TOOLS = ("uv", "gitleaks", "actionlint", "osv-scanner", "node")
PURE = "Pure calculations without a boundary."
# The reference application, which no Quick start command may rename.
EXAMPLE = re.compile(r"(?<![/\w-])web\b")


def quick_start(project: Project, name: str = "web") -> dict[str, Completed]:
    """Run each command of the README's browser Quick start for `apps/<name>`.

    The results are keyed by the command's subcommand, such as `commit` or `test`.
    """
    block = QUICK_START.search((project.path / "README.md").read_text(encoding="utf-8"))
    assert block is not None, "the README has no browser Quick start"
    results: dict[str, Completed] = {}
    for line in block.group(1).splitlines():
        command = EXAMPLE.sub(name, line.replace("apps/web", f"apps/{name}"))
        result = project.run("bash", "-euo", "pipefail", "-c", command)
        assert result.returncode == 0, (command, output(result))
        results[command.split()[1]] = result
    return results


def bootstrap(project: Project) -> str:
    result = project.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return output(result)


def test_a_fresh_export_starts_a_browser_application_from_the_quick_start(
    export: Export, tmp_path: Path
) -> None:
    project = export(tmp_path / "project")
    assert "Chromium" not in bootstrap(project)
    results = quick_start(project)
    committed = output(results["commit"])
    assert "unit coverage of web: line 100.00%" in committed, committed
    assert "scenarios of web: 0 of 0 proved, 4 not required by this run" in committed
    tested = output(results["test"])
    assert "scenarios of web: 4 of 4 proved" in tested, tested
    again = bootstrap(project)
    assert "starts and matches the locked Playwright" in again, again
    assert project.repo.git("status", "--porcelain") == ""
    log = project.repo.git("log", "--format=%s")
    assert log == "Add the web application\nStart from the quality template\n"


def test_a_node_project_needs_no_browser_until_it_adds_a_frontend(
    export: Export, limited_cache: Caches, tmp_path: Path
) -> None:
    caches = limited_cache(tmp_path / "caches", NODE_TOOLS, ("npm",))
    node = export(tmp_path / "project", caches)
    bootstrap(node)
    typescript_project(node.path / "apps/api", name="api")
    added = node.quality("component", "add", "apps/api", "--no-boundary-reason", PURE)
    assert added.returncode == 0, output(added)
    node.repo.git("add", "quality.toml", "apps/api")
    assert "Chromium" not in bootstrap(node)
    committed = node.commit("Add the API", "quality.toml", "apps/api")
    assert committed.returncode == 0, output(committed)
    assert "unit coverage of api: line 100.00%" in output(committed)
    doctor = node.quality("doctor")
    assert doctor.returncode == 0, output(doctor)
    assert "Chromium" not in output(doctor)
    toolchains = Path(caches["XDG_CACHE_HOME"]) / "quality" / "toolchains"
    assert not [entry for entry in toolchains.iterdir() if entry.name.startswith("chromium-")]
    mixed = Project(node.repo)
    results = quick_start(mixed)
    text = output(results["commit"])
    for component in ("api", "web"):
        assert f"unit coverage of {component}: line 100.00%" in text, text
    assert "scenarios of web: 4 of 4 proved" in output(results["test"])


def test_two_browser_applications_pass_the_hook_and_the_browser_lane(
    export: Export, tmp_path: Path
) -> None:
    project = export(tmp_path / "project")
    bootstrap(project)
    base = project.head()
    quick_start(project)
    second = quick_start(project, "admin")
    text = output(second["commit"])
    for component in ("web", "admin"):
        assert f"unit coverage of {component}: line 100.00%" in text, text
    lane = project.quality(
        "gate", "--stage", "merge", "--base", base, "--head", "HEAD", "--lane", "browser"
    )
    report = output(lane)
    assert lane.returncode == 0, report
    assert "lane browser: checks web, admin; the main lane" in report, report
    for component in ("web", "admin"):
        assert f"scenarios of {component}: 4 of 4 proved" in report, report
