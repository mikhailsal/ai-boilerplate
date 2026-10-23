"""FR06: interrupted browser workers and timed-out detached children are fully reaped."""

import json
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import pytest

from quality.testkit.browserscenarios import SCENARIOS, SCENARIOS_FILE
from quality.testkit.scratch import CORE_SOURCE, Project, shared_caches

GOTO = '  await page.goto("/");\n'
WAIT_LIMIT = 180.0


@dataclass(frozen=True, slots=True)
class Process:
    pid: int
    command: str
    directory: str


def owned(runtime: Path) -> tuple[Process, ...]:
    result: list[Process] = []
    for directory in Path("/proc").glob("[0-9]*"):
        try:
            command = (
                (directory / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            )
            cwd = str((directory / "cwd").readlink())
        except OSError:
            continue
        if str(runtime) in command or cwd.startswith(str(runtime)):
            result.append(Process(int(directory.name), command, cwd))
    return tuple(result)


def ready(marker: Path, runtime: Path, process: subprocess.Popen[bytes]) -> tuple[Process, ...]:
    deadline = time.monotonic() + WAIT_LIMIT
    while time.monotonic() < deadline:
        observed = owned(runtime)
        if marker.exists() and any("browserrun import main" in item.command for item in observed):
            return observed
        assert process.poll() is None, "the suite exited before navigating to its owned document"
        time.sleep(0.05)
    pytest.fail("the browser did not reach its owned document before the readiness deadline")


def remaining(runtime: Path) -> tuple[Process, ...]:
    deadline = time.monotonic() + 5
    while found := owned(runtime):
        if time.monotonic() >= deadline:
            return found
        time.sleep(0.05)
    return ()


def dispose(process: subprocess.Popen[bytes], runtime: Path) -> None:
    for child in owned(runtime):
        with suppress(ProcessLookupError):
            os.kill(child.pid, signal.SIGKILL)
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=15)


@pytest.mark.parametrize("target", ["worker-term", "cli-int"])
def test_interruptions_stop_the_owned_node_and_detached_chromium_processes(
    counter: Project, tmp_path: Path, target: str
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    marker = tmp_path / "ready"
    project = replace(counter, caches={**shared_caches(os.environ), "TMPDIR": str(runtime)})
    source = 'import { appendFileSync } from "node:fs";\n' + SCENARIOS
    source = source.replace("const TAGS", "test.setTimeout(120_000);\n\nconst TAGS")
    source = source.replace(
        GOTO,
        GOTO
        + f'  appendFileSync({json.dumps(str(marker))}, "ready\\n");\n'
        + "  await new Promise(() => {});\n",
    )
    counter.write(f"web/{SCENARIOS_FILE}", source)
    counter.repo.git("add", "-A")
    process = subprocess.Popen(
        ["./quality", "test", "--suite", "e2e", "--component", "web"],
        cwd=project.path,
        env=project.environ(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        before = ready(marker, runtime, process)
        executables = {Path(item.command.partition(" ")[0]).name for item in before}
        assert {"node", "chrome-headless-shell"} <= executables
        if target == "worker-term":
            [worker] = [item for item in before if "browserrun import main" in item.command]
            os.kill(worker.pid, signal.SIGTERM)
        else:
            process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=20)
        (tmp_path / "gate.log").write_bytes(stdout + stderr)
        assert process.returncode != 0
        after = remaining(runtime)
        (tmp_path / "processes.json").write_text(
            json.dumps(
                {"before": [asdict(item) for item in before], "after": [p.pid for p in after]},
                indent=2,
            )
        )
        assert after == (), after
    finally:
        dispose(process, runtime)
        counter.repo.git("reset", "-q", "--hard")
        counter.repo.git("clean", "-fdq")


def test_a_real_timeout_kills_and_reaps_a_detached_sigterm_ignoring_grandchild(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "detached-pid"
    child = (
        "import os, signal\nfrom pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"Path({str(marker)!r}).write_text(str(os.getpid()))\n"
        "while True: signal.pause()\n"
    )
    parent = (
        "import signal, subprocess, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"subprocess.Popen([sys.executable, '-c', {child!r}], start_new_session=True)\n"
        "while True: signal.pause()\n"
    )
    wrapper = (
        "import sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(CORE_SOURCE)!r})\n"
        "from quality.adapters.typescript.ownership import owned_processes\n"
        "from quality.process import Command, run\n"
        "with owned_processes():\n"
        f"    command = Command((sys.executable, '-c', {parent!r}),\n"
        f"                      cwd=Path({str(tmp_path)!r}), timeout=1)\n"
        "    run(command)\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", wrapper], capture_output=True, timeout=20, check=False
        )
        (tmp_path / "timeout.log").write_bytes(result.stdout + result.stderr)
        assert result.returncode != 0
        assert b"timed out after 1s" in result.stderr
        assert marker.is_file(), result.stderr.decode()
        pid = int(marker.read_text())
        assert not Path(f"/proc/{pid}").exists(), f"detached process {pid} was not reaped"
    finally:
        for child in owned(tmp_path):
            with suppress(ProcessLookupError):
                os.kill(child.pid, signal.SIGKILL)
