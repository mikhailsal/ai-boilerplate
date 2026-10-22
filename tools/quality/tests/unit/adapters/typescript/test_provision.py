import json
from pathlib import Path

from quality.adapters.typescript.lockfile import Lock
from quality.adapters.typescript.provision import TypeScriptSetup, copy_manifests
from quality.testkit.nodefakes import (
    PINS,
    FakeNode,
    browser_component,
    typescript_component,
    write_component,
)

APP = typescript_component()


def setup(fake: FakeNode, calls: list[str]) -> TypeScriptSetup:
    def locate() -> Path:
        calls.append("locate")
        return fake.node.executable

    def install() -> Path:
        calls.append("install")
        return fake.node.executable

    return TypeScriptSetup(locate, install, fake.node.cache, PINS)


def test_only_the_lock_and_package_manifests_are_copied(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "packages" / "app").mkdir(parents=True)
    for name in ("package.json", "package-lock.json", ".npmrc", "packages/app/package.json"):
        (root / name).write_text("{}")
    packages: dict[str, dict[str, object]] = {
        name: {} for name in ("", "packages/app", "packages/gone", "node_modules/x")
    }
    target = tmp_path / "copy"
    assert copy_manifests(Lock(root, packages), root, target) == target
    copied = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    assert copied == ["package-lock.json", "package.json", "packages/app/package.json"]
    nested = copy_manifests(Lock(root / "packages" / "app", {"": {}}), root, tmp_path / "other")
    assert nested == tmp_path / "other" / "packages" / "app"


def test_bootstrap_installs_node_and_downloads_each_lock_once(
    fake_node: FakeNode, snapshot: Path
) -> None:
    write_component(snapshot / "app")
    (snapshot / "app" / ".npmrc").write_text("//registry/:_authToken=x\n")
    calls: list[str] = []
    provisioner = setup(fake_node, calls)
    assert provisioner.provision(APP, snapshot) == []
    assert provisioner.provision(APP, snapshot) == []
    assert calls == ["install", "install"]
    [[cwd, command, *flags]] = fake_node.calls()
    assert command == "ci"
    assert "--offline" not in flags
    assert Path(cwd).name == "app"
    assert Path(cwd) != snapshot / "app"
    assert not (snapshot / "app" / "node_modules").exists()


def test_doctor_locates_node_and_installs_offline(fake_node: FakeNode, snapshot: Path) -> None:
    write_component(snapshot / "app")
    fake_node.npm(f"ls -A > '{fake_node.root / 'listing'}'\n")
    calls: list[str] = []
    assert setup(fake_node, calls).probe(APP, snapshot) == []
    assert calls == ["locate"]
    [[_, _, *flags]] = fake_node.calls()
    assert "--offline" in flags
    listing = (fake_node.root / "listing").read_text().split()
    assert listing == ["package-lock.json", "package.json"]


def test_a_browser_component_is_reported_instead_of_set_up(
    fake_node: FakeNode, snapshot: Path
) -> None:
    write_component(snapshot / "web")
    calls: list[str] = []
    provisioner = setup(fake_node, calls)
    for step in (provisioner.provision, provisioner.probe):
        (found,) = step(browser_component(), snapshot)
        assert (found.rule, found.component) == ("typescript.browser-incomplete", "web")
    assert calls == []
    assert fake_node.calls() == []


def test_a_rejected_configuration_installs_nothing(fake_node: FakeNode, snapshot: Path) -> None:
    directory = write_component(snapshot / "app")
    (directory / "package-lock.json").write_text(json.dumps({"lockfileVersion": 1}))
    calls: list[str] = []
    found = setup(fake_node, calls).provision(APP, snapshot)
    assert [d.rule for d in found] == ["typescript.config"]
    assert calls == []
    assert fake_node.calls() == []
