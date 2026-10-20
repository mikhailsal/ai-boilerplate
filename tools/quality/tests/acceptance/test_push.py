"""R02: the pre-push hook checks every pushed commit, including ones made with --no-verify."""

from quality.testkit.scratch import CORE, Project, output, rules_of

SOURCE = "app/src/app/core.py"


def test_pre_push_checks_the_pushed_commits(project: Project) -> None:
    installed = project.quality("bootstrap", "--pre-push")
    assert installed.returncode == 0, output(installed)
    remote = project.path.parent / "remote.git"
    project.repo.git("init", "-q", "--bare", str(remote))
    project.repo.git("remote", "add", "origin", str(remote))
    pushed = project.git("push", "-q", "origin", "main")
    assert pushed.returncode == 0, output(pushed)
    good = project.head()
    project.write(SOURCE, "import os\n\n\n" + CORE)
    project.repo.git("add", "-A")
    project.repo.git("commit", "-q", "--no-verify", "-m", "skip the local check")
    refused = project.git("push", "-q", "origin", "main")
    assert refused.returncode != 0
    assert "python.lint" in rules_of(refused), output(refused)
    assert project.repo.git("--git-dir", str(remote), "rev-parse", "main").strip() == good
