"""Place an owned process in its leaf and resolve its bounded exec handshake."""

from __future__ import annotations

import os
import select
import subprocess
import sys
import time
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import SHIM, Group
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid, unavailable


def launch(
    leaf: Group, argv: list[str], cwd: Path, env: dict[str, str],
) -> tuple[subprocess.Popen[bytes], int]:
    fd = os.open("cgroup.procs", os.O_WRONLY | os.O_NOFOLLOW, dir_fd=leaf.fd)
    try:
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    except BaseException:
        os.close(fd)
        raise
    placement = SHIM.replace("shift; exec", 'eval "exec $1>&-"; shift; exec')
    try:
        process = subprocess.Popen(
            [
                "/bin/bash", "-c", placement, "rl00bc-placement", str(fd), sys.executable,
                str(Path(__file__).with_name("rl00bc_exec.py")), str(write_fd),
                str(cwd.absolute()), *argv,
            ],
            cwd=Path(__file__).resolve().parents[5], env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(fd, write_fd),
        )
    except BaseException:
        os.close(read_fd)
        raise
    finally:
        os.close(fd)
        os.close(write_fd)
    return process, read_fd


def handshake(process: subprocess.Popen[bytes], read_fd: int, stop: int) -> None:
    data = bytearray()
    try:
        while True:
            remaining = (stop - time.monotonic_ns()) / 1_000_000_000
            if remaining <= 0:
                expired("native exec handshake deadline")
            if not select.select([read_fd], [], [], min(remaining, 0.02))[0]:
                continue
            chunk = os.read(read_fd, 4097)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > 4096:
                invalid("native exec handshake too large")
        if bytes(data) != b"ready\n":
            unavailable("native exec handshake failed")
        if process.poll() is not None:
            unavailable("native exited before exec handshake could be verified")
    finally:
        os.close(read_fd)
