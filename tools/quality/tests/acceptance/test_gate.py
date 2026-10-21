"""R09: the merge gate runs on plain Linux, ignores provider variables, and judges the merge."""

import json
from pathlib import Path
from typing import Any

from quality.process import Command, run
from quality.testkit.scratch import TIMEOUT, Project, output

CLAMP = """\
def clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value
"""
CLAMP_TESTS = """\
from app.clamp import clamp


def test_clamp() -> None:
    assert clamp(-1, 0, 9) == 0
    assert clamp(12, 0, 9) == 9
    assert clamp(4, 0, 9) == 4
"""
LENIENT = "cyclomatic_complexity = { error = 10 }"
STRICT = "cyclomatic_complexity = { error = 2 }"
# What GitHub Actions and GitLab CI would set, all describing a different event.
PROVIDER = {
    "CI": "true",
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "push",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_BASE_REF": "main",
    "GITHUB_HEAD_REF": "feature",
    "GITLAB_CI": "true",
    "CI_PIPELINE_SOURCE": "push",
    "CI_DEFAULT_BRANCH": "main",
}


def provider_variables(environ: dict[str, str]) -> list[str]:
    prefixes = ("GITHUB_", "GITLAB_", "CI_", "RUNNER_")
    return sorted(key for key in environ if key == "CI" or key.startswith(prefixes))


def feature(project: Project, files: dict[str, str], *, hooks: bool = True) -> str:
    """Commit `files` on a new branch `feature` and return its head; main stays checked out."""
    project.repo.git("checkout", "-q", "-b", "feature")
    for path, text in files.items():
        project.write(path, text)
    if hooks:
        committed = project.commit("feature")
        assert committed.returncode == 0, output(committed)
    else:
        project.repo.git("add", "-A")
        project.repo.git("commit", "-q", "--no-verify", "-m", "feature")
    head = project.head()
    project.repo.git("checkout", "-q", "main")
    return head


def move_main(project: Project, path: str, text: str) -> str:
    """Commit a change on main through the hooks and return the new tip."""
    project.write(path, text)
    committed = project.commit(f"main changes {path}")
    assert committed.returncode == 0, output(committed)
    return project.head()


def host_merge(project: Project) -> str:
    """Merge `feature` into a detached copy of main, as a host builds its test merge."""
    project.repo.git("checkout", "-q", "--detach", "main")
    project.repo.git("merge", "-q", "--no-ff", "-m", "merge feature", "feature")
    tested = project.head()
    project.repo.git("checkout", "-q", "main")
    return tested


def gate(project: Project, *args: str, env: dict[str, str] | None = None) -> tuple[int, Any]:
    command = ("./quality", "gate", "--stage", "merge", *args, "--json")
    environ = {**project.environ(), **(env or {})}
    result = run(Command(command, cwd=project.path, timeout=TIMEOUT, env=environ))
    assert result.stdout_text(), output(result)
    return result.returncode, json.loads(result.stdout_text())


def rules(report: Any) -> list[str]:
    return [diagnostic["rule"] for diagnostic in report["diagnostics"]]


def test_a_pull_request_passes_on_plain_linux_with_exported_reports(
    hooked: Project, tmp_path: Path
) -> None:
    head = feature(hooked, {"app/src/app/clamp.py": CLAMP, "app/tests/test_clamp.py": CLAMP_TESTS})
    base = move_main(hooked, "README.md", "# Scratch project\n\nSee [agents](AGENTS.md).\n")
    tested = host_merge(hooked)
    assert provider_variables(hooked.environ()) == []
    reports = tmp_path / "reports"
    args = ("--base", base, "--head", head, "--tested", tested, "--reports", str(reports))
    code, report = gate(hooked, *args)
    assert (code, rules(report)) == (0, [])
    assert (report["candidate"]["base"], report["candidate"]["tested"]) == (base, tested)
    assert json.loads((reports / "report.json").read_text()) == report
    junit = (reports / "junit/app/unit.xml").read_text()
    assert "test_clamp" in junit
    lcov = (reports / "coverage/app/unit.lcov").read_text()
    # Exported locations are relative to the repository, not to the component.
    assert "SF:app/src/app/clamp.py" in lcov
    assert (reports / "coverage/app/unit.cobertura.xml").is_file()


def test_provider_variables_do_not_change_the_verdict(hooked: Project) -> None:
    base = hooked.head()
    lint = CLAMP.replace("def clamp", "import os\n\n\ndef clamp")
    files = {"app/src/app/clamp.py": lint, "app/tests/test_clamp.py": CLAMP_TESTS}
    head = feature(hooked, files, hooks=False)
    plain = gate(hooked, "--base", base, "--head", head)
    assert plain[0] == 1
    assert "python.lint" in rules(plain[1])
    pointed = {**PROVIDER, "GITHUB_SHA": base, "CI_COMMIT_SHA": base, "CI_COMMIT_BEFORE_SHA": head}
    disguised = gate(hooked, "--base", base, "--head", head, env=pointed)
    assert disguised[0] == plain[0]
    assert disguised[1]["candidate"] == plain[1]["candidate"]
    assert disguised[1]["diagnostics"] == plain[1]["diagnostics"]


def test_a_stricter_policy_on_main_invalidates_an_earlier_green_result(hooked: Project) -> None:
    head = feature(hooked, {"app/src/app/clamp.py": CLAMP, "app/tests/test_clamp.py": CLAMP_TESTS})
    first = host_merge(hooked)
    code, report = gate(hooked, "--base", hooked.head(), "--head", head, "--tested", first)
    assert (code, rules(report)) == (0, [])
    policy = (hooked.path / "quality.toml").read_text()
    assert LENIENT in policy
    base = move_main(hooked, "quality.toml", policy.replace(LENIENT, STRICT))
    second = host_merge(hooked)
    code, report = gate(hooked, "--base", base, "--head", head, "--tested", second)
    assert (code, rules(report)) == (1, ["structure.complexity"])
    assert report["diagnostics"][0]["path"] == "app/src/app/clamp.py"
