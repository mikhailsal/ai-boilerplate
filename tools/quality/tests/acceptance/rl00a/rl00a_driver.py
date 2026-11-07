"""Run the preregistered RL00a proof, serially, outside routine pytest suites."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import platform
import select
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
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


@contextmanager
def cleanup_service(
    manager: str, unit: str, proxy: subprocess.Popen[bytes], *, if_running: bool = False
) -> Generator[None]:
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        try:
            if not if_running or proxy.poll() is None:
                control(manager, "stop", unit)
                proxy.communicate(timeout=3)
        except Exception:
            logging.exception("RL00a cleanup failed for %s", unit)
            if not failed:
                raise


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


def observe_service(root: dict[str, object], until_ns: int, evidence: dict[str, object]) -> None:
    path = Path(str(root["path"]))
    while time.monotonic_ns() < until_ns:
        try:
            if path.stat().st_ino != root["inode"]:
                message = "owned service cgroup inode changed"
                raise RuntimeError(message)
            populated = counters((path / "cgroup.events").read_text())["populated"]
            observed_ns = time.monotonic_ns()
            if (
                populated == 0
                and observed_ns < until_ns
                and evidence["populated_zero_observed_ns"] is None
            ):
                evidence["populated_zero_observed_ns"] = observed_ns
        except FileNotFoundError:
            try:
                if path.stat().st_ino != root["inode"]:
                    message = "owned service cgroup inode changed"
                    raise RuntimeError(message)
            except FileNotFoundError:
                observed_ns = time.monotonic_ns()
                if observed_ns < until_ns:
                    evidence.update(root_removed=True, root_removed_observed_ns=observed_ns)
                break
        time.sleep(0.005)


def service_cleanup(
    root: dict[str, object],
    output: Path,
    original_deadline_ns: int,
    killed_at: float | None,
    proxy_native: int | None,
) -> dict[str, object]:
    initial_ns = time.monotonic_ns()
    start_ns = int(killed_at * 1_000_000_000) if killed_at is not None else initial_ns
    until_ns = min(original_deadline_ns, start_ns + 2_000_000_000)
    evidence: dict[str, object] = {
        "root": root,
        "initial_check_ns": initial_ns,
        "original_deadline_ns": original_deadline_ns,
        "cleanup_deadline_ns": until_ns,
        "proxy_native": proxy_native,
        "populated_zero_observed_ns": None,
        "root_removed": False,
        "root_removed_observed_ns": None,
    }
    try:
        observe_service(root, until_ns, evidence)
    finally:
        evidence["finished_ns"] = time.monotonic_ns()
        failed = sys.exc_info()[0] is not None
        try:
            save(output / "service-cleanup.json", evidence)
        except Exception:
            if not failed:
                raise
            logging.exception("RL00a service cleanup evidence could not be saved")
    return evidence


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
    with cleanup_service(manager, unit, process, if_running=True):
        killed_at = (
            kill_guardian(manager, unit, output, process) if scenario == "guardian-death" else None
        )
        stdout, stderr = process.communicate(timeout=20)
        (output / "service.log").write_bytes(stdout[:65536] + stderr[:65536])
        expected = process.returncode != 0 if killed_at is not None else process.returncode == 0
        assert expected, stderr.decode(errors="replace")[-4096:]
        provider = load(output / "provider.json")
        root = cast(dict[str, object], provider["root"])
        evidence = load(output / ("armed.json" if killed_at is not None else "guardian.json"))
        deadline_key = (
            "effective_ancestor_deadline_ns" if killed_at is not None else "original_deadline_ns"
        )
        deadline_ns = cast(int, evidence[deadline_key])
        cleanup = service_cleanup(root, output, deadline_ns, killed_at, process.returncode)
        assert cleanup["root_removed"] is True, "owned service directory was not removed in time"
        if killed_at is not None:
            evidence = {
                "systemd_cleanup_seconds": (cast(int, cleanup["root_removed_observed_ns"]) / 1e9)
                - killed_at,
                "root_empty_or_removed": True,
                "proxy_native": process.returncode,
                "service_cleanup": cleanup,
            }
            assert evidence["systemd_cleanup_seconds"] < 2
        else:
            evidence["service_cleanup"] = cleanup
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


def record_sentinel(watched: int, proxy: subprocess.Popen[bytes], output: Path) -> bool:
    observation: dict[str, object] = {"observed_ns": time.monotonic_ns(), "survived": None}
    try:
        exited = bool(select.select([watched], [], [], 0)[0])
        native = proxy.poll()
        observation.update(pidfd_readable=exited, proxy_native=native)
        if not exited:
            signal.pidfd_send_signal(watched, 0)
        observation["survived"] = not exited and native is None
    except OSError as error:
        observation["observation_error"] = {"type": type(error).__name__, "message": str(error)}
    save(output / "sentinel.json", observation)
    return observation["survived"] is True


def observed_case(
    manager: str,
    mode: str,
    scenario: str,
    output: Path,
    sentinel: tuple[int, subprocess.Popen[bytes]],
) -> dict[str, object]:
    watched, proxy = sentinel
    try:
        record = run_case(manager, mode, scenario, output)
    except BaseException:
        try:
            record_sentinel(watched, proxy, output)
        except Exception:
            logging.exception("RL00a sentinel evidence unavailable")
        raise
    assert record_sentinel(watched, proxy, output), "unrelated sentinel survival was not proved"
    record["unrelated_sentinel_survived"] = True
    return record


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
    results: list[dict[str, object]] = []
    with ExitStack() as cleanup:
        cleanup.enter_context(cleanup_service(args.manager, unit, sentinel))
        pid = sentinel_pid(args.manager, unit, sentinel)
        watched = os.pidfd_open(pid)
        cleanup.callback(os.close, watched)
        for mode in args.paths:
            for scenario in args.cases:
                signal.pidfd_send_signal(watched, 0)
                assert not select.select([watched], [], [], 0)[0]
                record = observed_case(
                    args.manager, mode, scenario, output / f"{mode}-{scenario}", (watched, sentinel)
                )
                results.append(record)
                save(
                    output / "summary.json",
                    {"identity": identity, "cases": results, "complete": False},
                )
                print(f"PASS {mode}/{scenario}", flush=True)
        save(output / "summary.json", {"identity": identity, "cases": results, "complete": True})
        return 0


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
