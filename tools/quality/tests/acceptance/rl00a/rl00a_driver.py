"""Run the preregistered RL00a proof, serially, outside routine pytest suites."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import select
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import cast

from rl00a_cases import CASES, DEATH_CASES
from rl00a_cgroup import HERE, counters, load, save

SCENARIOS = (*CASES, *DEATH_CASES)
REPOSITORY = HERE.parents[4]


def manager_command(manager: str, command: str) -> list[str]:
    return [command, "--user"] if manager == "user" else ["sudo", "-n", command]


def unit_command(manager: str, unit: str, argv: list[str], *, sentinel: bool = False) -> list[str]:
    properties = {
        "MemoryMax": "32M" if sentinel else "256M",
        "MemorySwapMax": "0",
        "TasksMax": "8" if sentinel else "64",
        "RuntimeMaxSec": "300s" if sentinel else "16s",
        "TimeoutStopSec": "1s",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "OOMPolicy": "continue",
        "LimitCORE": "0",
    }
    if not sentinel:
        properties["Delegate"] = "yes"
    if manager == "system":
        properties.update(User=str(os.getuid()), Group=str(os.getgid()))
    return [
        *manager_command(manager, "systemd-run"),
        "--quiet",
        "--wait",
        "--pipe",
        "--collect",
        f"--unit={unit}",
        *[f"--property={key}={value}" for key, value in properties.items()],
        *argv,
    ]


def control(manager: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*manager_command(manager, "systemctl"), *args],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def available_memory() -> int:
    memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    return int(memory["MemAvailable"].split()[0]) * 1024


def source_identity(output: Path) -> dict[str, object]:
    files = [
        *HERE.glob("*.py"),
        REPOSITORY / ".github/workflows/resource-proof.yml",
        REPOSITORY / "docs/plan/test-resource-limits/rl00a-protocol.md",
    ]
    hashes: dict[str, str] = {}
    for path in sorted(files):
        if path.exists():
            relative = str(path.relative_to(REPOSITORY))
            content = path.read_bytes()
            hashes[relative] = hashlib.sha256(content).hexdigest()
            captured = output / "source" / relative
            captured.parent.mkdir(parents=True, exist_ok=True)
            captured.write_bytes(content)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=True,
        timeout=3,
    ).stdout.strip()
    return {
        "source_sha256": hashes,
        "git_head": revision,
        "python": sys.version,
        "kernel": platform.release(),
        "machine": platform.machine(),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }


def sentinel_pid(manager: str, unit: str, process: subprocess.Popen[bytes]) -> int:
    until = time.monotonic() + 3
    while process.poll() is None and time.monotonic() < until:
        value = control(manager, "show", unit, "--property=MainPID", "--value").stdout.strip()
        if value.isdecimal() and int(value):
            return int(value)
        time.sleep(0.02)
    message = "independent sentinel did not start"
    raise AssertionError(message)


def kill_guardian(manager: str, unit: str, output: Path, process: subprocess.Popen[bytes]) -> float:
    until = time.monotonic() + 3
    ready = output / "outer-ready.json"
    while not ready.exists() and process.poll() is None and time.monotonic() < until:
        time.sleep(0.005)
    assert ready.exists(), "guardian-death payload was not armed"
    record = load(ready)
    assert Path(str(record["root"])).name == f"{unit}.service"
    current = control(manager, "show", unit, "--property=MainPID", "--value")
    assert int(current.stdout.strip()) == record["pid"]
    started = time.monotonic()
    killed = control(manager, "kill", unit, "--kill-who=main", "--signal=KILL")
    assert killed.returncode == 0, killed.stderr
    return started


def service_empty(path: Path, until: float) -> bool:
    while path.exists() and time.monotonic() < until:
        try:
            if counters((path / "cgroup.events").read_text())["populated"] == 0:
                return True
        except FileNotFoundError:
            return True
        time.sleep(0.005)
    return not path.exists()


def run_case(manager: str, mode: str, scenario: str, output: Path) -> dict[str, object]:
    output.mkdir(mode=0o700)
    assert available_memory() >= 512 * 1024 * 1024, "insufficient host memory before payload"
    unit = f"quality-rl00a-{uuid.uuid4().hex}"
    argv = [sys.executable, str(HERE / "rl00a_service.py"), mode, scenario, str(output)]
    process = subprocess.Popen(
        unit_command(manager, unit, argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )
    started = time.monotonic()
    try:
        killed_at = (
            kill_guardian(manager, unit, output, process) if scenario == "guardian-death" else None
        )
        stdout, stderr = process.communicate(timeout=20)
        (output / "service.log").write_bytes(stdout[:65536] + stderr[:65536])
        expected = process.returncode != 0 if killed_at else process.returncode == 0
        assert expected, stderr.decode(errors="replace")[-4096:]
        provider = load(output / "provider.json")
        root = Path(str(cast(dict[str, object], provider["root"])["path"]))
        assert service_empty(root, (killed_at or time.monotonic()) + 2), (
            "owned service remained populated"
        )
        if killed_at:
            evidence = {
                "systemd_cleanup_seconds": time.monotonic() - killed_at,
                "root_empty_or_removed": True,
                "proxy_native": process.returncode,
            }
            assert evidence["systemd_cleanup_seconds"] < 2
        else:
            evidence = load(output / "guardian.json")
        record: dict[str, object] = {
            "path": mode,
            "case": scenario,
            "unit": unit,
            "passed": True,
            "elapsed_seconds": time.monotonic() - started,
            "evidence": evidence,
        }
        save(output / "result.json", record)
        return record
    finally:
        if process.poll() is None:
            control(manager, "stop", unit)
            process.communicate(timeout=3)


def run(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    identity = source_identity(output)
    save(output / "identity.json", identity)
    unit = f"quality-rl00a-sentinel-{uuid.uuid4().hex}"
    sentinel = subprocess.Popen(
        unit_command(args.manager, unit, ["/bin/sleep", "300"], sentinel=True),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    watched: int | None = None
    results: list[dict[str, object]] = []
    try:
        pid = sentinel_pid(args.manager, unit, sentinel)
        watched = os.pidfd_open(pid)
        for mode in args.paths:
            for scenario in args.cases:
                signal.pidfd_send_signal(watched, 0)
                assert not select.select([watched], [], [], 0)[0]
                record = run_case(args.manager, mode, scenario, output / f"{mode}-{scenario}")
                signal.pidfd_send_signal(watched, 0)
                assert not select.select([watched], [], [], 0)[0]
                assert sentinel.poll() is None, "unrelated invocation was stopped"
                record["unrelated_sentinel_survived"] = True
                results.append(record)
                save(
                    output / "summary.json",
                    {"identity": identity, "cases": results, "complete": False},
                )
                print(f"PASS {mode}/{scenario}", flush=True)
        save(output / "summary.json", {"identity": identity, "cases": results, "complete": True})
        return 0
    finally:
        if watched is not None:
            os.close(watched)
        control(args.manager, "stop", unit)
        sentinel.communicate(timeout=3)


def main() -> int:
    if sys.flags.optimize:
        message = "RL00a safety assertions require unoptimized Python"
        raise RuntimeError(message)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manager", choices=("user", "system"), default="user")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--paths", nargs="+", choices=("host", "prepared"), default=["host", "prepared"]
    )
    parser.add_argument("--cases", nargs="+", choices=SCENARIOS, default=list(SCENARIOS))
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
