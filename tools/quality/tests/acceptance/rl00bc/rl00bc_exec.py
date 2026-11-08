"""Exec handshake helper: the error pipe closes atomically on successful exec.

EOF following the ready marker resolves the launch as exec or helper death.
A native producer must separately establish that the payload executed.
"""

from __future__ import annotations

import fcntl
import os
import sys


def main() -> int:
    fd = int(sys.argv[1])
    cwd = sys.argv[2]
    argv = sys.argv[3:]
    try:
        if not argv or not os.path.isabs(cwd):
            raise ValueError("invalid native command or working directory")
        fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.fcntl(fd, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)
        os.chdir(cwd)
        os.write(fd, b"ready\n")
        os.execvpe(argv[0], argv, os.environ)
    except BaseException as error:
        message = f"error: {type(error).__name__}: {error}\n".encode("utf-8", "replace")[:4000]
        try:
            os.write(fd, message)
        except OSError:
            pass
        return 127
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
