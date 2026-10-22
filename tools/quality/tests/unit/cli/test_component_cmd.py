import json
from pathlib import Path

import pytest

from quality.cli.main import main
from quality.policy import Bundler, Capability, Component, ExecutionTarget, Framework, load_policy
from quality.testkit.gitrepo import GitRepo
from quality.testkit.policies import ComponentSpec, policy_toml

POLICY = policy_toml(ComponentSpec(root="app"))


@pytest.fixture
def project(repo: GitRepo, monkeypatch: pytest.MonkeyPatch) -> GitRepo:
    repo.write("quality.toml", POLICY)
    repo.write("app/pyproject.toml", '[project]\nname = "app"\n')
    repo.write("app/src/app/__init__.py", "")
    repo.write("app/tests/test_app.py", "")
    repo.commit_all("base")
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(repo.home))
    monkeypatch.chdir(repo.path)
    return repo


def native(repo: GitRepo, root: str, manifest: str, *directories: str) -> None:
    repo.write(f"{root}/{manifest}", "{}\n" if manifest.endswith(".json") else "name: x\n")
    for directory in directories:
        repo.write(f"{root}/{directory}/.keep", "")


def added(repo: GitRepo) -> list[tuple[str, str, str, list[str], list[str]]]:
    policy = load_policy(repo.path).policy
    assert policy is not None
    return [
        (c.id, c.profile, c.root, c.source, c.tests.unit)
        for c in policy.components
        if c.id != "app"
    ]


@pytest.mark.parametrize(
    ("manifest", "directories", "expected"),
    [
        ("pyproject.toml", ("src", "tests"), ("python", ["src"], ["tests"])),
        ("package.json", ("src", "tests"), ("typescript", ["src"], ["tests"])),
        ("pubspec.yaml", ("lib", "test"), ("dart", ["lib"], ["test"])),
        ("pubspec.yaml", ("lib", "bin", "test"), ("dart", ["lib", "bin"], ["test"])),
        ("composer.json", ("src", "tests"), ("php", ["src"], ["tests"])),
    ],
)
def test_the_profile_and_directories_follow_from_the_native_project(
    project: GitRepo,
    capsys: pytest.CaptureFixture[str],
    manifest: str,
    directories: tuple[str, ...],
    expected: tuple[str, list[str], list[str]],
) -> None:
    native(project, "services/web", manifest, *directories)
    assert main(["component", "add", "services/web", "--capability", "cli"]) == 0
    profile, source, unit = expected
    assert added(project) == [("web", profile, "services/web", source, unit)]
    out = capsys.readouterr().out
    assert out.startswith('added to quality.toml:\n\n[[components]]\nid = "web"\n')
    assert out.endswith(
        "next: stage the component and quality.toml, run ./quality bootstrap, then commit\n"
    )
    assert project.git("diff", "--cached", "--name-only").strip() == ""


def test_options_name_what_the_conventions_cannot(
    project: GitRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    project.write("services/tool/cli/main.py", "")
    project.write("services/tool/checks/check_main.py", "")
    monkeypatch.chdir(project.path / "services")
    arguments = ["tool", "--id", "cli-tool", "--profile", "python", "--source", "cli"]
    reason = ["--unit", "checks", "--no-boundary-reason", "prints only"]
    assert main(["component", "add", *arguments, *reason]) == 0
    assert added(project) == [("cli-tool", "python", "services/tool", ["cli"], ["checks"])]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["../outside"], "'../outside' is not a directory of this repository"),
        (["quality.toml"], "'quality.toml' is not a directory of this repository"),
        (["empty"], "cannot tell the profile from the manifests"),
        (["both"], "cannot tell the profile from the manifests"),
        (["bare"], "none of src exists in the component"),
        (["web", "--unit", "tests"], "none of src exists in the component"),
        (["listed"], "declare --capability, or explain with --no-boundary-reason"),
    ],
)
def test_arguments_that_cannot_describe_a_component_exit_with_status_2(
    project: GitRepo, capsys: pytest.CaptureFixture[str], arguments: list[str], message: str
) -> None:
    (project.path.parent / "outside").mkdir(exist_ok=True)
    (project.path / "empty").mkdir()
    native(project, "both", "package.json", "src", "tests")
    native(project, "both", "composer.json")
    native(project, "bare", "composer.json")
    native(project, "web", "package.json")
    native(project, "listed", "package.json", "src", "tests")
    reason = [] if arguments == ["listed"] else ["--no-boundary-reason", "pure"]
    assert main(["component", "add", *arguments, *reason]) == 2
    assert capsys.readouterr().err.startswith(f"component add: {message}")
    assert (project.path / "quality.toml").read_text() == POLICY


def test_a_repository_without_a_policy_is_refused(
    project: GitRepo, capsys: pytest.CaptureFixture[str]
) -> None:
    (project.path / "quality.toml").unlink()
    assert main(["component", "add", "app", "--capability", "cli"]) == 2
    assert "there is no quality.toml at the repository root" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("arguments", "finding"),
    [
        (["web", "--capability", "teleport"], "(policy.invalid)"),
        (["web", "--id", "app", "--capability", "cli"], "duplicate component id 'app'"),
        (["app", "--id", "again", "--capability", "cli"], "several components share the root"),
    ],
)
def test_a_component_the_policy_rejects_is_not_written(
    project: GitRepo, capsys: pytest.CaptureFixture[str], arguments: list[str], finding: str
) -> None:
    native(project, "web", "package.json", "src", "tests")
    assert main(["component", "add", *arguments]) == 2
    assert finding in capsys.readouterr().out
    assert (project.path / "quality.toml").read_text() == POLICY


def test_outside_a_repository_the_git_error_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    (tmp_path / "loose").mkdir()
    monkeypatch.chdir(tmp_path / "loose")
    assert main(["component", "add", ".", "--capability", "cli"]) == 3
    assert "(git." in capsys.readouterr().out


STACK = {
    "dependencies": {"react": "19.3.1", "react-dom": "19.3.1"},
    "devDependencies": {"vite": "8.3.5", "@vitejs/plugin-react": "6.1.2"},
}
APP_FILES = ("vite.config.ts", "index.html")


def react_app(
    repo: GitRepo, root: str, manifest: object = STACK, files: tuple[str, ...] = APP_FILES
) -> None:
    repo.write(f"{root}/package.json", json.dumps(manifest))
    for name in (*files, "src/.keep", "tests/.keep"):
        repo.write(f"{root}/{name}", "// user file\n")


def last(repo: GitRepo) -> Component:
    policy = load_policy(repo.path).policy
    assert policy is not None
    return policy.components[-1]


def test_a_react_vite_application_registers_as_a_browser_component(
    project: GitRepo, capsys: pytest.CaptureFixture[str]
) -> None:
    react_app(project, "apps/web")
    assert main(["component", "add", "apps/web", "--target", "browser"]) == 0
    web = last(project)
    assert (web.id, web.target, web.framework, web.bundler, web.capabilities) == (
        "web",
        ExecutionTarget.BROWSER,
        Framework.REACT,
        Bundler.VITE,
        [Capability.UI],
    )
    out = capsys.readouterr().out
    assert (
        'profile = "typescript"\ntarget = "browser"\nframework = "react"\nbundler = "vite"\n' in out
    )
    assert (project.path / "apps/web/vite.config.ts").read_text() == "// user file\n"
    assert json.loads((project.path / "apps/web/package.json").read_text()) == STACK


def test_the_ui_capability_comes_first_and_is_not_repeated(project: GitRepo) -> None:
    react_app(project, "web")
    arguments = ["--capability", "http-api", "--capability", "ui"]
    assert main(["component", "add", "web", "--target", "browser", *arguments]) == 0
    assert last(project).capabilities == [Capability.HTTP_API, Capability.UI]
    react_app(project, "admin")
    assert (
        main(["component", "add", "admin", "--target", "browser", "--capability", "http-api"]) == 0
    )
    assert last(project).capabilities == [Capability.UI, Capability.HTTP_API]


def test_an_explicit_node_target_is_recorded_whatever_the_evidence(project: GitRepo) -> None:
    react_app(project, "ssr")
    assert main(["component", "add", "ssr", "--target", "node", "--capability", "http-api"]) == 0
    node = last(project)
    assert (node.target, node.framework, node.in_browser) == (ExecutionTarget.NODE, None, False)


@pytest.mark.parametrize(
    ("manifest", "files", "target", "message"),
    [
        (
            STACK,
            APP_FILES,
            [],
            (
                "found react, react-dom, vite, @vitejs/plugin-react, vite.config.ts, index.html, "
                "so the target is ambiguous; name it with --target browser or --target node"
            ),
        ),
        ({"devDependencies": {"vite": "8"}}, (), [], "found vite, so the target is ambiguous"),
        ({"dependencies": {"vue": "3"}}, (), [], "found Vue, so the target is ambiguous"),
        (
            {"dependencies": {"react": "19.3.1"}},
            ("index.html",),
            ["--target", "browser"],
            (
                "a React + Vite application needs the react-dom package, the vite package, the "
                "@vitejs/plugin-react package, a vite.config.* file"
            ),
        ),
        (
            {"dependencies": {"react": "19.3.1"}},
            ("vite.config.ts",),
            ["--target", "browser"],
            (
                "a React + Vite application needs the react-dom package, the vite package, the "
                "@vitejs/plugin-react package, an index.html entry point"
            ),
        ),
        (
            {**STACK, "optionalDependencies": {"next": "16.0.0"}},
            APP_FILES,
            ["--target", "browser"],
            "Next.js is not supported; the browser target supports React with Vite",
        ),
        ("{", APP_FILES, ["--target", "browser"], "package.json is not valid JSON"),
    ],
)
def test_a_target_that_the_evidence_does_not_support_is_refused(
    project: GitRepo,
    capsys: pytest.CaptureFixture[str],
    manifest: object,
    files: tuple[str, ...],
    target: list[str],
    message: str,
) -> None:
    react_app(project, "web", manifest, files)
    if isinstance(manifest, str):
        project.write("web/package.json", manifest)
    assert main(["component", "add", "web", *target, "--capability", "cli"]) == 2
    assert capsys.readouterr().err.startswith(f"component add: {message}")
    assert (project.path / "quality.toml").read_text() == POLICY


def test_a_target_applies_only_to_typescript(
    project: GitRepo, capsys: pytest.CaptureFixture[str]
) -> None:
    native(project, "svc", "composer.json", "src", "tests")
    assert main(["component", "add", "svc", "--target", "node", "--capability", "cli"]) == 2
    assert (
        capsys.readouterr().err
        == "component add: --target applies only to the typescript profile\n"
    )
