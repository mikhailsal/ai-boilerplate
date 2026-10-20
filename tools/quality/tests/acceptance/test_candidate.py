"""R07: the hook checks exactly the staged candidate and never changes it (A06, A07, A14)."""

from quality.testkit.scratch import CORE, Project, output, rules_of

SOURCE = "app/src/app/core.py"
TESTS = "app/tests/test_app.py"
EXTRA = "def plus(value: int) -> int:\n    return value + 1\n"
EXTRA_TEST = """\
from app.extra import plus


def test_plus() -> None:
    assert plus(1) == 2
"""
FAILING = """\
from app.core import sign


def test_sign() -> None:
    assert sign(-1) == -1
    assert sign(4) == 2
"""
PASSING = FAILING.replace("== 2", "== 1")
COMMENTED = "# The sign of a number.\n" + CORE
UNFORMATTED = COMMENTED.replace("(value: int) -> int", "(value:int)->int")


def test_a06_an_untracked_covering_test_does_not_count(hooked: Project) -> None:
    hooked.write("app/src/app/extra.py", EXTRA)
    hooked.write("app/tests/test_extra.py", EXTRA_TEST)
    result = hooked.commit("add extra", "app/src/app/extra.py")
    assert result.returncode != 0
    assert "coverage.new-file" in rules_of(result), output(result)


def test_a06_an_unstaged_covering_test_does_not_count(hooked: Project) -> None:
    hooked.write("app/src/app/extra.py", EXTRA)
    hooked.write("app/tests/test_extra.py", "def test_nothing() -> None:\n    pass\n")
    hooked.repo.git("add", "-A")
    hooked.write("app/tests/test_extra.py", EXTRA_TEST)
    result = hooked.git("commit", "-q", "-m", "add extra")
    assert result.returncode != 0
    assert "coverage.new-file" in rules_of(result), output(result)


def test_a07_an_unstaged_fix_does_not_rescue_a_bad_staged_test(hooked: Project) -> None:
    hooked.write(TESTS, FAILING)
    hooked.repo.git("add", "-A")
    hooked.write(TESTS, PASSING)
    result = hooked.git("commit", "-q", "-m", "change the test")
    assert result.returncode != 0
    assert "tests.failed" in rules_of(result), output(result)
    assert (hooked.path / TESTS).read_text() == PASSING


def test_a07_a_bad_worktree_does_not_block_a_good_staged_tree(hooked: Project) -> None:
    hooked.write(TESTS, PASSING)
    hooked.repo.git("add", "-A")
    hooked.write(SOURCE, "def broken(:\n")
    hooked.write("app/src/app/junk.py", "import os\nx=1\n")
    result = hooked.git("commit", "-q", "-m", "simplify the test")
    assert result.returncode == 0, output(result)
    assert hooked.repo.git("show", f"HEAD:{SOURCE}") == CORE


def test_a14_a_rejected_commit_changes_neither_the_index_nor_the_worktree(
    hooked: Project,
) -> None:
    hooked.write(SOURCE, UNFORMATTED)
    hooked.repo.git("add", "-A")
    staged = hooked.index_tree()
    result = hooked.git("commit", "-q", "-m", "unformatted")
    assert result.returncode != 0
    assert (hooked.index_tree(), (hooked.path / SOURCE).read_text()) == (staged, UNFORMATTED)


def test_a14_fix_changes_only_the_worktree(hooked: Project) -> None:
    hooked.write(SOURCE, UNFORMATTED)
    hooked.repo.git("add", "-A")
    staged = hooked.index_tree()
    fixed = hooked.quality("fix")
    assert fixed.returncode == 0, output(fixed)
    assert "nothing was staged" in output(fixed)
    assert (hooked.path / SOURCE).read_text() == COMMENTED
    assert hooked.index_tree() == staged
    rejected = hooked.git("commit", "-q", "-m", "still unformatted in the index")
    assert "python.format" in rules_of(rejected), output(rejected)
    accepted = hooked.commit("restaged", SOURCE)
    assert accepted.returncode == 0, output(accepted)
