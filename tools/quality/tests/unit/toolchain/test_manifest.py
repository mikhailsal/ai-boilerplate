from pathlib import Path

import pytest

from quality.toolchain import ManifestError, load_manifest, parse_manifest
from quality.toolchain.manifest import MANIFEST, Architecture, Packaging

SHA = "a" * 64
TOOL = f"""\
schema_version = 1

[tools.demo]
version = "1.2.3"
binary = "demo"

[tools.demo.artifacts.x86_64]
url = "https://example.invalid/demo.tar.gz"
sha256 = "{SHA}"
packaging = "tar"
member = "demo-1.2.3/demo"

[tools.demo.extras."rules.toml"]
url = "https://example.invalid/rules.toml"
sha256 = "{SHA}"
"""


def test_a_valid_manifest_is_parsed() -> None:
    manifest = parse_manifest(TOOL.encode())
    tool = manifest.tools["demo"]
    artifact = tool.artifacts[Architecture.X86_64]
    assert (tool.version, tool.binary) == ("1.2.3", "demo")
    assert (artifact.packaging, artifact.member) == (Packaging.TAR, "demo-1.2.3/demo")
    assert tool.extras["rules.toml"].url == "https://example.invalid/rules.toml"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("schema_version = 1", "schema_version = 2"),
        ('version = "1.2.3"', 'version = "latest"'),
        ('binary = "demo"', 'binary = "../demo"'),
        ("https://example.invalid/demo.tar.gz", "http://example.invalid/demo.tar.gz"),
        ("https://example.invalid/demo.tar.gz", "https://example.invalid/a b"),
        (f'sha256 = "{SHA}"\npackaging', f'sha256 = "{"A" * 64}"\npackaging'),
        (f'sha256 = "{SHA}"\npackaging', f'sha256 = "{SHA[:63]}"\npackaging'),
        ('packaging = "tar"', 'packaging = "rpm"'),
        ('member = "demo-1.2.3/demo"', 'member = "../demo"'),
        ('member = "demo-1.2.3/demo"', 'member = "/demo"'),
        ('member = "demo-1.2.3/demo"', 'member = "demo/./demo"'),
        ('member = "demo-1.2.3/demo"', 'member = "demo/.."'),
        ('member = "demo-1.2.3/demo"', ""),
        ('packaging = "tar"', 'packaging = "binary"'),
        ("[tools.demo.artifacts.x86_64]", "[tools.demo.artifacts.sparc]"),
        ('binary = "demo"', 'binary = "demo"\nchannel = "nightly"'),
        ('[tools.demo.extras."rules.toml"]', '[tools.demo.extras."../rules.toml"]'),
    ],
)
def test_invalid_values_are_rejected(old: str, new: str) -> None:
    assert TOOL.count(old) == 1
    with pytest.raises(ManifestError, match="invalid toolchain manifest"):
        parse_manifest(TOOL.replace(old, new).encode())


def test_binary_downloads_have_no_member() -> None:
    binary = TOOL.replace(
        'packaging = "tar"\nmember = "demo-1.2.3/demo"\n', 'packaging = "binary"\n'
    )
    artifact = parse_manifest(binary.encode()).tools["demo"].artifacts[Architecture.X86_64]
    assert (artifact.packaging, artifact.member) == (Packaging.BINARY, None)


@pytest.mark.parametrize("member", ["...a", "a.b/c+d", "x_y-z/.hidden"])
def test_member_segments_may_contain_dots(member: str) -> None:
    document = TOOL.replace('member = "demo-1.2.3/demo"', f'member = "{member}"')
    artifacts = parse_manifest(document.encode()).tools["demo"].artifacts
    assert artifacts[Architecture.X86_64].member == member


def test_a_tool_needs_an_artifact() -> None:
    document = 'schema_version = 1\n[tools.demo]\nversion = "1.0"\nbinary = "demo"\n'
    document += "artifacts = {}\n"
    with pytest.raises(ManifestError, match="artifacts"):
        parse_manifest(document.encode())


@pytest.mark.parametrize("data", [b"\xff\xfe", b"schema_version = ", b""])
def test_undecodable_or_malformed_documents_are_rejected(data: bytes) -> None:
    with pytest.raises(ManifestError, match="invalid toolchain manifest"):
        parse_manifest(data)


def test_a_missing_manifest_is_reported(tmp_path: Path) -> None:
    missing = tmp_path / "toolchains.toml"
    with pytest.raises(ManifestError, match=f"cannot read toolchain manifest {missing}"):
        load_manifest(missing)


def test_the_committed_manifest_pins_gitleaks_with_its_rules() -> None:
    assert MANIFEST.name == "toolchains.toml"
    manifest = load_manifest()
    gitleaks = manifest.tools["gitleaks"]
    assert gitleaks.version == "8.30.1"
    assert set(gitleaks.artifacts) == {Architecture.X86_64, Architecture.AARCH64}
    assert all(artifact.member == "gitleaks" for artifact in gitleaks.artifacts.values())
    assert list(gitleaks.extras) == ["gitleaks.toml"]
    assert "/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/" in gitleaks.extras["gitleaks.toml"].url
    assert set(manifest.tools) == {"uv", "gitleaks", "osv-scanner", "actionlint"}
