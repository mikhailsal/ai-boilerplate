"""`toolchains.toml`: pinned versions, download URLs, and SHA-256 checksums."""

from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

MANIFEST = Path(__file__).resolve().parents[3] / "toolchains.toml"

type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type HttpsUrl = Annotated[str, StringConstraints(pattern=r"^https://[^\s]+$")]
type Name = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]*$")]
# Relative paths whose segments are not "." or "..": every segment has a non-dot character.
type Member = Annotated[
    str, StringConstraints(pattern=r"^[\w.+-]*[\w+-][\w.+-]*(?:/[\w.+-]*[\w+-][\w.+-]*)*$")
]


class Packaging(StrEnum):
    """How a download holds the executable."""

    BINARY = "binary"
    TAR = "tar"
    ZIP = "zip"


class Architecture(StrEnum):
    """Supported Linux machine architectures."""

    X86_64 = "x86_64"
    AARCH64 = "aarch64"


class Strict(BaseModel):
    """Models reject unknown keys and are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Artifact(Strict):
    """One platform download and the archive member that is the executable."""

    url: HttpsUrl
    sha256: Sha256
    packaging: Packaging
    member: Member | None = None

    @model_validator(mode="after")
    def _member_matches_packaging(self) -> Self:
        if (self.packaging is Packaging.BINARY) != (self.member is None):
            msg = "'member' is required for archives and not allowed for binary downloads"
            raise ValueError(msg)
        return self


class Extra(Strict):
    """A verified data file installed next to the executable, such as a rule set."""

    url: HttpsUrl
    sha256: Sha256


class Tool(Strict):
    """A pinned tool with one artifact per machine architecture and optional data files."""

    version: Annotated[str, StringConstraints(pattern=r"^\d+(?:\.\d+)+$")]
    binary: Name
    artifacts: dict[Architecture, Artifact] = Field(min_length=1)
    extras: dict[Member, Extra] = Field(default_factory=dict[Member, Extra])


class Manifest(Strict):
    """The complete toolchain manifest."""

    schema_version: Literal[1]
    tools: dict[Name, Tool]


class ManifestError(Exception):
    """The manifest is missing or invalid."""


def parse_manifest(data: bytes) -> Manifest:
    """Parse and validate a manifest document."""
    try:
        return Manifest.model_validate(tomllib.loads(data.decode("utf-8")))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError, ValidationError) as error:
        msg = f"invalid toolchain manifest: {error}"
        raise ManifestError(msg) from error


def load_manifest(path: Path = MANIFEST) -> Manifest:
    """Load the manifest shipped next to the core."""
    try:
        return parse_manifest(path.read_bytes())
    except OSError as error:
        msg = f"cannot read toolchain manifest {path}: {error.strerror}"
        raise ManifestError(msg) from error
