"""R02/R10: bootstrap installs the managed hooks idempotently and never overwrites others."""

from quality.testkit.scratch import Project, output, rules_of

FOREIGN = '#!/bin/sh\ntouch "$(git rev-parse --git-dir)/local-ran"\n'
ENVIRONMENT = 3


def test_bootstrap_is_idempotent_and_satisfies_doctor(hooked: Project) -> None:
    installed = hooked.hook("pre-commit").read_bytes()
    again = hooked.quality("bootstrap")
    assert again.returncode == 0, output(again)
    assert hooked.hook("pre-commit").read_bytes() == installed
    assert not hooked.hook("pre-push").exists()
    doctor = hooked.quality("doctor")
    assert doctor.returncode == 0, output(doctor)
    assert "pre-commit hook: current" in output(doctor)


def test_doctor_reports_a_missing_hook(project: Project) -> None:
    doctor = project.quality("doctor")
    assert doctor.returncode == ENVIRONMENT
    assert "hooks.missing" in rules_of(doctor), output(doctor)


def test_a_foreign_hook_is_kept_until_renamed(project: Project) -> None:
    hook = project.hook("pre-commit")
    hook.write_text(FOREIGN)
    hook.chmod(0o755)
    refused = project.quality("bootstrap")
    assert refused.returncode == ENVIRONMENT
    assert "hooks.conflict" in rules_of(refused), output(refused)
    assert hook.read_text() == FOREIGN
    hook.rename(project.hook("pre-commit.local"))
    installed = project.quality("bootstrap")
    assert installed.returncode == 0, output(installed)
    assert project.hook("pre-commit.local").read_text() == FOREIGN
    project.write("README.md", "# Scratch project\n\nRead [the agent guide](AGENTS.md).\n")
    result = project.commit("reword the readme")
    assert result.returncode == 0, output(result)
    assert (project.path / ".git" / "local-ran").exists()


def test_a_failing_local_hook_blocks_the_commit(project: Project) -> None:
    local = project.hook("pre-commit.local")
    local.write_text("#!/bin/sh\nexit 7\n")
    local.chmod(0o755)
    assert project.quality("bootstrap").returncode == 0
    before = project.head()
    project.write("README.md", "# Scratch project\n\nRead [the agent guide](AGENTS.md).\n")
    assert project.commit("reword the readme").returncode != 0
    assert project.head() == before


def test_core_hooks_path_is_a_conflict(project: Project) -> None:
    project.repo.git("config", "core.hooksPath", ".githooks")
    refused = project.quality("bootstrap")
    assert refused.returncode == ENVIRONMENT
    assert "hooks.conflict" in rules_of(refused), output(refused)
    assert not (project.path / ".githooks").exists()
    assert not project.hook("pre-commit").exists()
