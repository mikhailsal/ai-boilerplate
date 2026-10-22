"""FR05.1 and FR05.2: the check of a browser component sees exactly the staged candidate.

Each pair of versions differs in one kind of file of the component: a TSX
source, a test, the Vite configuration, a stylesheet, or an asset. The bad
version fails a gate. Whichever version is staged decides the check, the
other one stays in the work tree untouched, and each kind of change runs the
unit suite again. A first commit and the index Git prepares for a commit of
named paths are candidates in the same way.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

from quality.testkit.browserproject import APP, ICON, INDEX, STYLES, TESTS, VITE
from quality.testkit.scratch import Project, browser, create_project, output, rules_of

SOURCE = "web/src/App.tsx"
TEST = "web/tests/App.test.tsx"
WEB = "unit coverage of web: line 100.00% (7/7), branch 100.00% (2/2)"
COUNT = "        Count {count}\n"
LABELLED = APP.replace(COUNT, "        {LABEL} {count}\n")
DECLARED = "declare const LABEL: string;\n"
DEFINED = VITE.replace(
    "export default defineConfig({ plugins: [react()] });",
    'export default defineConfig({\n  define: { LABEL: JSON.stringify("Count") },\n'
    "  plugins: [react()],\n});",
)
ICON_LINK = '    <link rel="icon" href="/icon.svg" />\n'
LINKED = INDEX.replace(
    ICON_LINK, ICON_LINK + '    <link rel="apple-touch-icon" href="/touch.svg" />\n'
)
TOUCH_ICON = ICON.replace('<circle r="1"/>', '<rect width="2" height="2"/>')
FAILING = TESTS.replace('toBe("Count 1")', 'toBe("Count 2")')
RENAMED = APP.replace("<h1>Counter</h1>", "<h1>Clicks</h1>")
STYLESHEET = "web/src/App.module.css"
MISSPELLED = STYLES.replace("  margin", "  colr: red;\n  margin")
Files = Mapping[str, str | None]
# Each pair: the files both versions share, the good and the bad version, and
# the rules the bad one adds. `None` is a file the version does not have.
PAIRS: dict[str, tuple[Files, Files, Files, set[str]]] = {
    "source": (
        {},
        {SOURCE: RENAMED},
        {SOURCE: APP.replace("count + 1", "count + 2")},
        {"tests.failed"},
    ),
    "test": (
        {},
        {TEST: TESTS.replace("its clicks", "every click")},
        {TEST: FAILING},
        {"tests.failed"},
    ),
    # Without the definition, the label is an undefined variable when the test renders it.
    "configuration": (
        {SOURCE: LABELLED, "web/src/globals.d.ts": DECLARED},
        {"web/vite.config.ts": DEFINED},
        {"web/vite.config.ts": VITE},
        {"tests.failed"},
    ),
    "stylesheet": (
        {},
        {STYLESHEET: STYLES.replace("40rem", "48rem")},
        {STYLESHEET: MISSPELLED},
        {"typescript.styles"},
    ),
    "asset": (
        {"web/index.html": LINKED},
        {"web/public/touch.svg": TOUCH_ICON},
        {"web/public/touch.svg": None},
        {"typescript.entries"},
    ),
}


def write(project: Project, files: Files) -> None:
    for path, text in files.items():
        if text is None:
            (project.path / path).unlink(missing_ok=True)
        else:
            project.write(path, text)


def contents(project: Project, files: Files) -> dict[str, str | None]:
    found = {path: project.path / path for path in files}
    return {path: file.read_text() if file.exists() else None for path, file in found.items()}


def check(project: Project) -> tuple[set[str], str]:
    result = project.quality("check")
    rules = rules_of(result)
    assert result.returncode == (1 if rules else 0), output(result)
    return rules, output(result)


@pytest.fixture
def web(tmp_path: Path) -> Project:
    """Return a bootstrapped project with the browser component `web`."""
    created = create_project(tmp_path / "project", browser())
    result = created.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return created


@pytest.mark.parametrize("staged", ["good", "bad"])
@pytest.mark.parametrize("kind", PAIRS)
def test_only_the_staged_version_decides(web: Project, kind: str, staged: str) -> None:
    shared, good, bad, added = PAIRS[kind]
    index, worktree = (good, bad) if staged == "good" else (bad, good)
    write(web, {**shared, **index})
    web.repo.git("add", "-A")
    write(web, worktree)
    rules, printed = check(web)
    if staged == "good":
        assert rules == set(), printed
        assert WEB in printed, printed
    else:
        assert rules == added, printed
    assert contents(web, worktree) == dict(worktree)


def test_a_first_commit_is_checked_from_the_index(web: Project) -> None:
    web.repo.git("update-ref", "-d", "HEAD")
    rules, printed = check(web)
    assert rules == set(), printed
    assert f"{WEB}, changed lines 100.00% (7/7)" in printed
    web.write(TEST, FAILING)
    web.repo.git("add", "-A")
    web.write(TEST, TESTS)
    rules, printed = check(web)
    assert rules == {"tests.failed"}, printed


def staged_paths(project: Project) -> list[str]:
    return project.repo.git("diff", "--cached", "--name-only").split()


def test_a_commit_of_named_paths_checks_the_index_git_prepares(web: Project) -> None:
    before = web.head()
    web.write(TEST, FAILING)
    web.repo.git("add", "-A")
    web.write(SOURCE, RENAMED)
    # The hook checks HEAD plus the named source; the staged failing test is not part of it.
    result = web.git("commit", "-q", "-m", "rename the page", "--", SOURCE)
    assert result.returncode == 0, output(result)
    assert WEB in output(result), output(result)
    assert web.head() != before
    assert staged_paths(web) == [TEST]
    web.repo.git("reset", "-q", "--hard")
    web.write(STYLESHEET, MISSPELLED)
    web.repo.git("add", "-A")
    staged = web.index_tree()
    web.write(TEST, FAILING)
    # Now the named test is part of the candidate, and the staged stylesheet is not.
    result = web.git("commit", "-q", "-m", "change the test", "--", TEST)
    assert result.returncode != 0
    assert rules_of(result) == {"tests.failed"}, output(result)
    assert web.index_tree() == staged
