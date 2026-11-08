"""Capture exact, bounded source inputs for a committed CI experiment."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import save
from tests.acceptance.rl00bc.rl00bc_errors import invalid

INPUTS = (
    "tools/quality/tests/acceptance/rl00a/rl00a_cgroup.py",
    "docs/plan/test-resource-limits/rl00bc-protocol.md",
    ".github/workflows/resource-methods.yml",
    ".github/workflows/resource-methods-job.yml",
    "quality.toml",
    "tools/quality/toolchains.toml",
    "tools/quality/uv.lock",
    "tools/quality/helpers/dart/pubspec.yaml",
    "tools/quality/helpers/dart/pubspec.lock",
    "tools/quality/helpers/php/composer.json",
    "tools/quality/helpers/php/composer.lock",
    "tools/quality/src/quality/testkit/browserseed/package-lock.json",
)


def git(repo: Path, *args: str) -> str:
    """Read one bounded Git metadata response without shell interpolation."""
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=5
    )
    return result.stdout.strip()


def _capture(repo: Path, output: Path, path: Path) -> tuple[str, str]:
    if path.stat().st_size > 2 * 1024 * 1024:
        invalid("source input exceeds the declared capture bound")
    relative = str(path.relative_to(repo))
    content = path.read_bytes()
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"], cwd=repo, check=True, capture_output=True, timeout=5
    ).stdout
    if content != committed:
        invalid(f"source does not match the candidate: {relative}")
    target = output / "source" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return relative, hashlib.sha256(content).hexdigest()


def capture(repo: Path, here: Path, output: Path) -> dict[str, object]:
    """Bind captured bytes to the clean candidate and record actual host metadata."""
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        invalid("experiment source must be a clean committed candidate")
    paths = [*here.glob("*.py"), *(repo / name for name in INPUTS)]
    hashes = dict(_capture(repo, output, path) for path in sorted(paths))
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    result: dict[str, object] = {
        "commit": git(repo, "rev-parse", "HEAD"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "base": git(repo, "rev-parse", "HEAD^"),
        "source_sha256": hashes,
        "source_digest": digest,
        "kernel": platform.release(),
        "machine": platform.machine(),
        "libc": platform.libc_ver(),
        "controller_python": sys.version,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }
    save(output / "identity.json", result)
    return result
