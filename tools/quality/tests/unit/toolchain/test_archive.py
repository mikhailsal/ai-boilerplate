import hashlib
import io
import os
import platform
import tarfile
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Literal

import pytest

from quality.toolchain import install
from quality.toolchain.archive import place
from quality.toolchain.manifest import Architecture, Artifact, ManifestError, Packaging, Tool

BINARY = b"#!/bin/sh\necho demo\n"
TREE_FILES = {"top/bin/demo": BINARY, "top/lib/tool.js": b"tool"}


def tree_bytes(
    *members: tarfile.TarInfo, data: Mapping[str, bytes], mode: Literal["w:xz", "w:gz"] = "w:xz"
) -> bytes:
    """Build a tree archive: regular files from `data`, then the given special members."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as tar:
        for name, content in data.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o755 if "/bin/" in name else 0o644
            tar.addfile(info, io.BytesIO(content))
        for info in members:
            tar.addfile(info)
    return buffer.getvalue()


def link(name: str, target: str, kind: bytes = tarfile.SYMTYPE) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = target
    return info


def directory(name: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    return info


def tree_tool(download: bytes, executable: str | None = "bin/demo") -> Tool:
    artifact = Artifact(
        url="https://example.invalid/demo",
        sha256=hashlib.sha256(download).hexdigest(),
        packaging=Packaging.TREE,
        member="top",
    )
    artifacts = dict.fromkeys(Architecture, artifact)
    return Tool(version="1.2.3", binary="demo", executable=executable, artifacts=artifacts)


def placed(tmp_path: Path, download: bytes, executable: str | None = "bin/demo") -> Path:
    """Place a tree download into a fresh staging area and return the install directory."""
    staging = tmp_path / "staging"
    staging.mkdir()
    archive = staging / "download"
    archive.write_bytes(download)
    tool = tree_tool(download, executable)
    final = staging / "demo-1.2.3"
    place(tool.artifacts[Architecture.X86_64], archive, final, tool)
    return final


@pytest.mark.parametrize("mode", ["w:xz", "w:gz"])
def test_a_tree_is_extracted_whole_below_its_top_directory(
    tmp_path: Path, mode: Literal["w:xz", "w:gz"]
) -> None:
    download = tree_bytes(
        directory("./top"),
        link("top/bin/tool", "../lib/tool.js"),
        link("top/lib/copy.js", "top/lib/tool.js", tarfile.LNKTYPE),
        data=TREE_FILES,
        mode=mode,
    )
    final = placed(tmp_path, download)
    assert os.access(final / "bin" / "demo", os.X_OK)
    assert (final / "bin" / "tool").readlink() == Path("../lib/tool.js")
    assert (final / "bin" / "tool").read_bytes() == b"tool"
    assert (final / "lib" / "copy.js").read_bytes() == b"tool"


def test_a_tree_tool_installs_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    download = tree_bytes(data=TREE_FILES)

    def opener(url: str) -> IO[bytes]:
        assert url == "https://example.invalid/demo"
        return io.BytesIO(download)

    root = tmp_path / "cache"
    path = install("demo", tree_tool(download), root, opener=opener)
    assert path == root / "demo-1.2.3" / "bin" / "demo"
    assert sorted(item.name for item in root.iterdir()) == ["demo-1.2.3"]

    def refuse(url: str) -> IO[bytes]:
        raise AssertionError(url)

    assert install("demo", tree_tool(download), root, opener=refuse) == path


@pytest.mark.parametrize(
    ("members", "data", "fragment"),
    [
        ((link("top/bin/out", "../../outside"),), TREE_FILES, "top/bin/out points outside top/"),
        ((link("top/bin/abs", "/etc/passwd"),), TREE_FILES, "top/bin/abs points outside top/"),
        ((link("top/hard", "other/x", tarfile.LNKTYPE),), TREE_FILES, "top/hard points outside"),
        ((), {**TREE_FILES, "top/../escape": b"x"}, "top/../escape is outside top/"),
        ((), {**TREE_FILES, "other/file": b"x"}, "other/file is outside top/"),
        ((), {**TREE_FILES, "/abs": b"x"}, "/abs is outside top/"),
        ((directory("top"),), {}, "archive has no executable bin/demo"),
        ((), {"other/bin/demo": BINARY}, "is outside top/"),
        ((directory("top/bin/demo"),), {}, "archive has no executable bin/demo"),
        ((), {"top/bin/demo-not": BINARY}, "archive has no executable bin/demo"),
        ((), {}, "archive has no top directory top/"),
    ],
    ids=[
        "escaping-symlink",
        "absolute-symlink",
        "escaping-hardlink",
        "dot-dot-member",
        "wrong-top-directory",
        "absolute-member",
        "no-executable",
        "only-another-top",
        "executable-is-a-directory",
        "missing-executable",
        "empty",
    ],
)
def test_unsafe_or_incomplete_trees_are_refused(
    tmp_path: Path,
    members: tuple[tarfile.TarInfo, ...],
    data: Mapping[str, bytes],
    fragment: str,
) -> None:
    with pytest.raises(ManifestError, match="archive") as raised:
        placed(tmp_path, tree_bytes(*members, data=data))
    assert fragment in str(raised.value)
    assert not (tmp_path.parent / "outside").exists()


def test_a_tree_executable_defaults_to_the_binary_name(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="archive has no executable demo"):
        placed(tmp_path, tree_bytes(data={"top/demo-not": BINARY}), executable=None)
