"""Verify the external systemd resource and time backstop."""

from __future__ import annotations

import grp
import os
import pwd
import re
import subprocess
import time

from tests.acceptance.rl00bc.rl00bc_errors import invalid

MIB = 1024 * 1024


def _timespan(value: str) -> float:
    units = {"us": 0.000001, "ms": 0.001, "s": 1, "min": 60, "h": 3600}
    pieces = re.findall(r"(\d+(?:\.\d+)?)(us|ms|min|s|h)", value)
    if not pieces or "".join(number + unit for number, unit in pieces) != value.replace(" ", ""):
        invalid(f"unsupported systemd timespan: {value}")
    return sum(float(number) * units[unit] for number, unit in pieces)


def _verify_backstop(values: dict[str, str]) -> None:
    expected = {
        "MemoryMax": str(4096 * MIB),
        "MemorySwapMax": "0",
        "TasksMax": "512",
        "Delegate": "yes",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "OOMPolicy": "continue",
    }
    if any(values.get(key) != value for key, value in expected.items()):
        invalid("systemd backstop properties mismatch")
    if _timespan(values["TimeoutStopUSec"]) > 1 or _timespan(values["RuntimeMaxUSec"]) > 2660:
        invalid("systemd backstop exceeds original deadline")
    user, group = values["User"], values["Group"]
    uid = int(user) if user.isdecimal() else pwd.getpwnam(user).pw_uid
    gid = int(group) if group.isdecimal() else grp.getgrnam(group).gr_gid
    if uid != os.getuid() or gid != os.getgid():
        invalid("systemd unit identity mismatch")


def backstop(unit: str, deadline: int) -> dict[str, str]:
    names = (
        "MemoryMax",
        "MemorySwapMax",
        "TasksMax",
        "Delegate",
        "KillMode",
        "SendSIGKILL",
        "OOMPolicy",
        "TimeoutStopUSec",
        "RuntimeMaxUSec",
        "User",
        "Group",
    )
    if deadline - time.monotonic_ns() < 2670 * 1_000_000_000:
        invalid("unit startup exceeded thirty-second admission window")
    command = [
        "/usr/bin/systemctl",
        "show",
        unit,
        "--no-pager",
        *[f"--property={name}" for name in names],
    ]
    done = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=2,
        check=True,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    if len(done.stdout) > 16384 or len(done.stderr) > 16384:
        invalid("systemd property output too large")
    values = dict(line.split("=", 1) for line in done.stdout.decode().splitlines())
    _verify_backstop(values)
    return values
