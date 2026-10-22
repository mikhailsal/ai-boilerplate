import json
from collections.abc import Callable
from pathlib import Path

import pytest

from quality.testkit import browserproject, scratch, typescriptproject
from quality.testkit.browserfakes import ALL_PINS
from quality.testkit.browserproject import SEED, browser_packages, browser_project
from quality.testkit.nodefakes import FakeNode
from quality.testkit.policies import browser_spec
from quality.testkit.scratch import create_project, typescript


def test_a_browser_component_locks_the_browser_and_node_pins() -> None:
    assert browser_packages() == ALL_PINS


def test_the_seed_resolves_every_pinned_package() -> None:
    packages = json.loads(SEED.read_text())["packages"]
    root = packages[""]
    assert {**root["dependencies"], **root["devDependencies"]} == ALL_PINS
    assert {name: packages[f"node_modules/{name}"]["version"] for name in ALL_PINS} == ALL_PINS


def test_components_start_from_the_seed(tmp_path: Path) -> None:
    fake = FakeNode.create(tmp_path / "fake-node", tmp_path / "npm-cache")
    fake.npm('cp package-lock.json start.json\necho "{}" > package-lock.json\n')
    web = browser_project(tmp_path / "web", node=fake.node)
    assert (web / "start.json").read_text() == SEED.read_text()
    written = sorted(path.relative_to(web).as_posix() for path in web.rglob("*.*"))
    assert written == sorted(
        [
            "eslint.config.js",
            "package-lock.json",
            "package.json",
            "start.json",
            "tsconfig.json",
            "vite.config.ts",
            *browserproject.FILES,
        ]
    )
    manifest = json.loads((web / "package.json").read_text())
    assert manifest["dependencies"] == {"react": "19.3.1", "react-dom": "19.3.1"}
    assert {**manifest["dependencies"], **manifest["devDependencies"]} == ALL_PINS
    other = browser_project(tmp_path / "other", {"src/a.ts": ""}, name="other", node=fake.node)
    assert json.loads((other / "package.json").read_text())["name"] == "other"
    assert not (other / "src/App.tsx").exists()


def test_scratch_projects_hold_browser_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written: list[tuple[str, str]] = []

    def record(kind: str) -> Callable[..., Path]:
        def writer(directory: Path, *, name: str) -> Path:
            written.append((kind, name))
            typescriptproject.write(directory, {"package.json": "{}\n"})
            return directory

        return writer

    monkeypatch.setattr(scratch, "browser_project", record("browser"))
    monkeypatch.setattr(scratch, "typescript_project", record("node"))
    create_project(tmp_path / "project", browser_spec(), typescript("api"))
    assert written == [("browser", "web"), ("node", "api")]
