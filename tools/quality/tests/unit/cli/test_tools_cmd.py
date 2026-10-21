from pathlib import Path

import pytest

from quality.cli import tools_cmd
from quality.cli.main import main
from quality.toolchain import ManifestError, Tool, ToolchainError
from quality.toolchain.install import INSTALL_FAILED


class FakeInstaller:
    def __init__(self, failing: frozenset[str] = frozenset()) -> None:
        self.failing = failing
        self.calls: list[tuple[str, str, Path]] = []

    def __call__(self, name: str, tool: Tool, root: Path) -> Path:
        self.calls.append((name, tool.version, root))
        if name in self.failing:
            message = f"cannot install {name} {tool.version}: checksum mismatch"
            raise ToolchainError(INSTALL_FAILED.diagnostic(message))
        return root / f"{name}-{tool.version}" / name


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(tools_cmd, "cache_root", lambda: tmp_path)
    return tmp_path


def use(monkeypatch: pytest.MonkeyPatch, installer: FakeInstaller) -> FakeInstaller:
    monkeypatch.setattr(tools_cmd, "install", installer)
    return installer


def test_the_default_installs_what_checks_and_the_core_tests_need(
    cache: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installer = use(monkeypatch, FakeInstaller())
    assert main(["tools", "install"]) == 0
    assert installer.calls == [
        ("gitleaks", "8.30.1", cache),
        ("actionlint", "1.7.12", cache),
        ("osv-scanner", "2.7.0", cache),
    ]
    assert capsys.readouterr().out.splitlines() == [
        f"gitleaks 8.30.1: {cache}/gitleaks-8.30.1/gitleaks",
        f"actionlint 1.7.12: {cache}/actionlint-1.7.12/actionlint",
        f"osv-scanner 2.7.0: {cache}/osv-scanner-2.7.0/osv-scanner",
    ]


def test_named_tools_are_installed_in_order(
    cache: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installer = use(monkeypatch, FakeInstaller())
    assert main(["tools", "install", "osv-scanner", "actionlint"]) == 0
    assert [call[0] for call in installer.calls] == ["osv-scanner", "actionlint"]
    assert capsys.readouterr().out.splitlines() == [
        f"osv-scanner 2.7.0: {cache}/osv-scanner-2.7.0/osv-scanner",
        f"actionlint 1.7.12: {cache}/actionlint-1.7.12/actionlint",
    ]


def test_unknown_tools_are_a_usage_error(
    cache: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installer = use(monkeypatch, FakeInstaller())
    assert main(["tools", "install", "gitleaks", "nmap", "curl"]) == 2
    assert installer.calls == []
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "unknown tools: nmap, curl\n")


def test_failed_installs_are_environment_errors(
    cache: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use(monkeypatch, FakeInstaller(frozenset({"uv"})))
    assert main(["tools", "install", "uv", "gitleaks"]) == 3
    assert capsys.readouterr().out.splitlines() == [
        f"gitleaks 8.30.1: {cache}/gitleaks-8.30.1/gitleaks",
        "error: cannot install uv 0.12.24: checksum mismatch (tools.install-failed)",
        "  hint: Check the network and the manifest entry, then retry.",
        "FAILED: 1 error(s), 0 warning(s)",
    ]


def test_an_invalid_manifest_is_an_environment_error(
    cache: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installer = use(monkeypatch, FakeInstaller())

    def broken() -> None:
        msg = "invalid toolchain manifest: bad"
        raise ManifestError(msg)

    monkeypatch.setattr(tools_cmd, "load_manifest", broken)
    assert main(["tools", "install"]) == 3
    assert installer.calls == []
    assert capsys.readouterr().out.splitlines() == [
        "error: invalid toolchain manifest: bad (tools.install-failed)",
        "  hint: Check the network and the manifest entry, then retry.",
        "FAILED: 1 error(s), 0 warning(s)",
    ]


def test_an_action_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["tools"])
    assert raised.value.code == 2
    assert "usage: quality tools" in capsys.readouterr().err
