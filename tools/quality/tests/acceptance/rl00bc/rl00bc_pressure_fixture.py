"""Frozen native unittest inputs for the bounded candidate-pressure experiment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc.rl00bc_errors import invalid

SUPPORT = r"""import json, os, time
from pathlib import Path

def emit(case, phase, source, **extra):
    directory = Path(os.environ["PRESSURE_EVENTS"])
    stamp = time.monotonic_ns()
    cgroup = Path("/proc/self/cgroup").read_text()
    group = next(line[3:] for line in cgroup.splitlines() if line.startswith("0::"))
    leaf = Path("/sys/fs/cgroup") / group.lstrip("/")
    counters = {key: int(value) for key, value in
                (line.split() for line in (leaf / "memory.events.local").read_text().splitlines())}
    payload = {"id": case.id(), "phase": phase, "source": str(Path(source).resolve()),
               "pid": os.getpid(), "cgroup": cgroup, "cgroup_inode": leaf.stat().st_ino,
               "memory_events_local": counters,
               "monotonic_ns": stamp, **extra}
    with (directory / (str(os.getpid()) + "-" + str(stamp) + ".json")).open("x") as handle:
        json.dump(payload, handle, sort_keys=True)
"""

PRESSURE_TEST = r"""import hashlib
import unittest
from pathlib import Path
from support import emit

class Pressure(unittest.TestCase):
    def test_input_cost(self):
        data = Path("data.txt").read_bytes()
        mib = int(data)
        if not 1 <= mib <= 96:
            raise ValueError("input allocation outside bound")
        emit(self, "call-start", __file__, input_sha256=hashlib.sha256(data).hexdigest(), mib=mib)
        held = bytearray(mib * 1048576)
        for offset in range(0, len(held), 4096):
            held[offset] = 1
        self.assertEqual(held[0], 1)
        emit(self, "call-end", __file__, input_sha256=hashlib.sha256(data).hexdigest(), mib=mib)
"""

CHEAP_BASE = """import unittest
from support import emit
class Cheap(unittest.TestCase):
    def test_a(self):
        emit(self, "call-start", __file__); self.assertTrue(True); emit(self, "call-end", __file__)
    def test_b(self):
        emit(self, "call-start", __file__); self.assertTrue(True); emit(self, "call-end", __file__)
"""

CHEAP_CHANGED = """import unittest
from support import emit
class Cheap(unittest.TestCase):
    def test_b(self):
        emit(self, "call-start", __file__); self.assertTrue(True); emit(self, "call-end", __file__)
    def test_a(self):
        emit(self, "call-start", __file__); self.assertTrue(True); emit(self, "call-end", __file__)
    def test_c(self):
        emit(self, "call-start", __file__); self.assertTrue(True); emit(self, "call-end", __file__)
    def test_d(self):
        emit(self, "call-start", __file__); self.assertTrue(True); emit(self, "call-end", __file__)
    def test_e(self):
        emit(self, "call-start", __file__); self.assertTrue(True); emit(self, "call-end", __file__)
    def test_f(self):
        emit(self, "call-start", __file__); self.assertTrue(True); emit(self, "call-end", __file__)
"""

RUNNER = r"""import json, sys, unittest
from pathlib import Path
identities = json.loads(sys.argv[1])
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in identities)
result = unittest.TextTestRunner(verbosity=1).run(suite)
Path(sys.argv[2]).write_text(json.dumps({"run": result.testsRun, "success": result.wasSuccessful(),
    "skipped": len(result.skipped), "failures": len(result.failures),
    "errors": len(result.errors)}))
raise SystemExit(0 if result.wasSuccessful() and result.testsRun == len(identities) else 1)
"""


def object_value(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid("pressure evidence is not an object")
    return cast(dict[str, object], value)


def discovered_ids(cases: list[dict[str, object]]) -> list[str]:
    result: list[str] = []
    for case in cases:
        identity = case.get("id")
        if not isinstance(identity, str) or not identity:
            invalid("native discovery returned an invalid identity")
        result.append(identity)
    if len(set(result)) != len(result):
        invalid("native discovery returned duplicate identities")
    return sorted(result)


def pressure_target(cases: list[dict[str, object]]) -> str:
    matches = [case.get("id") for case in cases if case.get("file") == "test_pressure.py"]
    if len(matches) != 1 or not isinstance(matches[0], str):
        invalid("discovery did not identify exactly one pressure case")
    return matches[0]


def _member(event: dict[str, object], kernel: dict[str, object]) -> bool:
    before = object_value(kernel.get("before"))
    path = before.get("path")
    text = event.get("cgroup")
    if not isinstance(path, str) or not isinstance(text, str):
        return False
    prefix = "/sys/fs/cgroup"
    lines = [line[3:] for line in text.splitlines() if line.startswith("0::")]
    return path.startswith(prefix + "/") and lines == [path.removeprefix(prefix)]


def collect_events(
    directory: Path, root: Path, kernel: dict[str, object]
) -> list[dict[str, object]]:
    files = sorted(directory.glob("*.json"))
    if len(files) > 32:
        invalid("native pressure event count exceeds its bound")
    result: list[dict[str, object]] = []
    for path in files:
        if path.stat().st_size > 16384:
            invalid("native pressure event exceeds its bound")
        event = object_value(json.loads(path.read_text(encoding="utf-8")))
        source = event.get("source")
        pid = event.get("pid")
        if not isinstance(source, str) or not Path(source).is_relative_to(root):
            invalid("native event source is outside the candidate snapshot")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            invalid("native event has no actual process identity")
        if not _member(event, kernel):
            invalid("native event is outside the charged subject leaf")
        result.append({**event, "event_path": str(path)})
    return sorted(result, key=lambda row: cast(int, row["monotonic_ns"]))


def _case_sources(starts: list[dict[str, object]], target: str) -> None:
    for event in starts:
        name = "test_pressure.py" if event.get("id") == target else "test_cheap.py"
        source = event.get("source")
        if not isinstance(source, str) or Path(source).name != name:
            invalid("native case source differs from the discovered fixture file")


def _validate_target(
    starts: list[dict[str, object]], target: str, digest: str, mib: int
) -> None:
    target_rows = [event for event in starts if event.get("id") == target]
    if (
        len(target_rows) != 1
        or target_rows[0].get("input_sha256") != digest
        or target_rows[0].get("mib") != mib
    ):
        invalid("pressure case did not start against the bound input")


def validate_events(
    events: list[dict[str, object]],
    expected: list[str],
    target: str,
    digest: str,
    mib: int,
    *,
    complete: bool,
) -> None:
    starts = [event for event in events if event.get("phase") == "call-start"]
    ids = [event.get("id") for event in starts]
    if ids != expected:
        invalid("observed native case start order differs from the bound discovery")
    _case_sources(starts, target)
    _validate_target(starts, target, digest, mib)
    if complete:
        ends = [event.get("id") for event in events if event.get("phase") == "call-end"]
        if ends != expected:
            invalid("canonical native case completion differs from its start order")


def kernel_success(raw: dict[str, object]) -> bool:
    return (
        raw.get("success") is True
        and raw.get("native_status") == 0
        and raw.get("cleanup_complete") is True
        and raw.get("resource_violation") is None
    )


def validate_limits(raw: dict[str, object], memory: int, tasks: int) -> None:
    before = object_value(raw.get("before"))
    if (
        before.get("memory.max") != str(memory * 1048576)
        or before.get("memory.swap.max") != "0"
        or before.get("pids.max") != str(tasks)
    ):
        invalid("observed kernel leaf limits differ from the requested envelope")


def _counter(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        invalid("required kernel memory event counter is unavailable")
    return value


def _strict_start(events: list[dict[str, object]], target: str) -> dict[str, object]:
    starts = [
        event
        for event in events
        if event.get("id") == target and event.get("phase") == "call-start"
    ]
    if len(starts) != 1 or any(event.get("phase") == "call-end" for event in events):
        invalid("strict pressure case start or interruption was not observed")
    return starts[0]


def verify_own_oom(raw: dict[str, object], events: list[dict[str, object]], target: str) -> None:
    if raw.get("resource_violation") != "own-memory" or raw.get("cleanup_complete") is not True:
        invalid("changed strict case did not prove its own memory violation and cleanup")
    start = _strict_start(events, target)
    before, after = object_value(raw.get("before")), object_value(raw.get("after"))
    inode = before.get("inode")
    if isinstance(inode, bool) or not isinstance(inode, int) or inode <= 0:
        invalid("strict leaf inode is unavailable")
    if start.get("cgroup_inode") != inode or inode != after.get("inode"):
        invalid("strict case event is not bound to a stable leaf inode")
    entry = object_value(start.get("memory_events_local"))
    final = object_value(after.get("memory.events.local"))
    initial = object_value(before.get("memory.events.local"))
    if not any(
        _counter(initial, key) <= _counter(entry, key) < _counter(final, key)
        for key in ("oom", "oom_kill")
    ):
        invalid("no own-leaf OOM counter grew after the native case started")
