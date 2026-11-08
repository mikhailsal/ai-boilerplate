"""Exec handshake helper: the error pipe closes atomically on successful exec.

EOF following the ready marker resolves the launch as exec or helper death.
A native producer must separately establish that the payload executed.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import shutil
import sys
from pathlib import Path
from types import TracebackType
from typing import NoReturn


def _invalid(message: str) -> NoReturn:
    raise ValueError(message)


class ErrorPipe:
    """Report any helper failure to the owner before terminating."""

    def __init__(self, fd: int) -> None:
        self.fd = fd

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if error is None:
            return False
        message = f"error: {type(error).__name__}: {error}\n".encode("utf-8", "replace")[:4000]
        with contextlib.suppress(OSError):
            os.write(self.fd, message)
        return True


def _executable(argv: list[str], cwd: str) -> str:
    if not argv or not Path(cwd).is_absolute():
        _invalid("invalid native command or working directory")
    resolved = shutil.which(argv[0], path=os.environ.get("PATH", os.defpath))
    if resolved is None:
        _invalid("native executable not found")
    return str(Path(resolved).resolve())


def main() -> int:
    fd = int(sys.argv[1])
    cwd = sys.argv[2]
    argv = sys.argv[3:]
    with ErrorPipe(fd):
        fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.fcntl(fd, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)
        os.chdir(cwd)
        executable = _executable(argv, cwd)
        os.write(fd, b"ready\n")
        os.execve(executable, argv, os.environ)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
