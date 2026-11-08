"""Materialize the Python RL00b/c corpus; experimental, not product enforcement."""

from __future__ import annotations

import json
import os
from pathlib import Path

from defusedxml import ElementTree

from tests.acceptance.rl00bc.rl00bc_child_fixture import CHILD
from tests.acceptance.rl00bc.rl00bc_errors import invalid

# The parent invokes these commands inside its finite cgroup and deadline.
CORPUS = r"""import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import subject

NAMES = ["ordinary", "setup", "teardown", "child"]
if os.environ.get("RL00_SIZE") == "large":
    NAMES += ["allocation", "retained", "parameter-cheap", "parameter-heavy", "slow",
              "justified", "cheap-01", "cheap-02", "cheap-03", "cheap-04", "cheap-05", "cheap-06"]

def resource_observation():
    result = {"cgroup": None, "cgroup_inode": None, "memory_events_local": None}
    try:
        text = Path("/proc/self/cgroup").read_text()
        result["cgroup"] = text
        line = next(line for line in text.splitlines() if line.startswith("0::"))
        group = Path("/sys/fs/cgroup") / line[3:].lstrip("/")
        try: result["cgroup_inode"] = group.stat().st_ino
        except OSError: pass
        rows = (group / "memory.events.local").read_text().splitlines()
        counters = {key: int(value) for key, value in (row.split() for row in rows)}
        if any(value < 0 for value in counters.values()): raise ValueError("invalid counter")
        result["memory_events_local"] = counters
    except (OSError, ValueError, StopIteration):
        pass
    return result

def event(label, phase, **detail):
    if os.environ.get("RL00_INSTRUMENT") != "1":
        return
    directory = Path(os.environ["RL00_EVENT_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.monotonic_ns()
    (directory / (str(os.getpid()) + "-" + str(stamp) + ".json")).write_text(json.dumps({
        "label": label, "variant": label, "phase": phase, "pid": os.getpid(),
        "fixture_context": "test_subject.py::retained",
        "monotonic_ns": stamp, "resource_observation": resource_observation(), **detail,
    }))

def active(label):
    return os.environ.get("RL00_MODE") == "correctness" and os.environ.get("RL00_TARGET") == label

def touched(value):
    for offset in range(0, len(value), 4096):
        value[offset] = 1
    return value

def allocate(label):
    if not active(label):
        return bytearray(4096)
    mib = int(os.environ["RL00_ALLOC_MIB"])
    if not 1 <= mib <= 1536:
        raise ValueError("allocation outside experiment bound")
    return touched(bytearray(mib * 1024 * 1024))

def worker_barrier():
    if not Path("worker-sync.json").exists():
        return
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker not in ("gw0", "gw1"):
        raise ValueError("missing native xdist worker identity")
    part = int(worker[-1]); directory = Path(os.environ["RL00_EVENT_DIR"])
    ready = directory / f"python-ready-{part}"; peer = directory / f"python-ready-{1-part}"
    seen = directory / f"python-seen-{part}"; other = directory / f"python-seen-{1-part}"
    deadline = time.monotonic() + 10
    event(worker, "worker-ready")
    temporary = directory / f"python-ready-{part}.tmp"
    temporary.write_text(str(os.getpid())); temporary.replace(ready)
    peer_pid = 0
    while peer_pid <= 0 and time.monotonic() < deadline:
        if peer.exists():
            text = peer.read_text()
            if text: peer_pid = int(text)
        time.sleep(.01)
    if peer_pid <= 0 or peer_pid == os.getpid():
        raise ValueError("worker readiness or identity mismatch")
    event(worker, "worker-peer-observed", peer_pid=peer_pid)
    seen.write_text(str(os.getpid()))
    while not other.exists() and time.monotonic() < deadline: time.sleep(.01)
    if not other.exists(): raise ValueError("worker acknowledgment timeout")
    event(worker, "worker-overlap-complete", peer_pid=peer_pid)

@pytest.fixture(scope="session")
def retained():
    # A session allocation belongs to the shared subject, never to its first case.
    worker_barrier()
    mib = int(os.environ["RL00_SHARED_MIB"])
    if not 0 <= mib <= 128:
        raise ValueError("shared allocation outside experiment bound")
    event("retained", "session-setup-start")
    if active("retained"):
        value = allocate("retained")
    else:
        value = touched(bytearray(mib * 1024 * 1024))
    event("retained", "session-setup")
    yield value
    event("retained", "session-teardown")

@pytest.fixture
def phases(request):
    label = request.param
    native_id = request.node.nodeid
    event(label, "setup-start", native_id=native_id)
    value = allocate(label) if label == "setup" else bytearray(4096)
    event(label, "setup-end", native_id=native_id)
    yield value
    event(label, "teardown-start", native_id=native_id)
    if label == "teardown":
        value = allocate(label)
    event(label, "teardown-end", native_id=native_id)

@pytest.mark.parametrize("phases", NAMES, ids=NAMES, indirect=True)
def test_subject(phases, retained, request):
    label = request.node.callspec.id
    native_id = request.node.nodeid
    event(label, "call-start", native_id=native_id)
    value = phases
    if label in ("allocation", "parameter-heavy", "justified"):
        value = allocate(label)
    if label == "child" and active(label):
        mib = int(os.environ["RL00_ALLOC_MIB"])
        if not 1 <= mib <= 1536:
            raise ValueError("allocation outside experiment bound")
        child = subprocess.Popen(
            [os.environ["RL00_CHILD_PYTHON"], "owned_child.py", str(mib)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            assert child.stdout.readline() == b"ready\n"
            cgroup = Path(f"/proc/{child.pid}/cgroup").read_text()
            event(label, "child-ready", native_id=native_id,
                  child_pid=child.pid, child_cgroup=cgroup)
            event(label, "child-allocation-start", native_id=native_id, child_pid=child.pid)
            child.stdin.write(b"a"); child.stdin.flush()
            assert child.stdout.readline() == b"allocated\n"
            event(label, "child-allocation-end", native_id=native_id, child_pid=child.pid)
            child.stdin.write(b"x"); child.stdin.flush()
            assert child.wait(timeout=8) == 0
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=8)
    if label == "slow" and active(label):
        delay = float(os.environ["RL00_SLOW_SECONDS"])
        if not 0 <= delay <= 30:
            raise ValueError("delay outside experiment bound")
        time.sleep(delay)
    assert value is not None and retained is not None and subject.value() == 1
    event(label, "call-end", native_id=native_id)
"""

PLUGIN = r"""import json
import os
import time
from pathlib import Path

def pytest_collection_finish(session):
    if os.environ.get("RL00_INSTRUMENT") != "1":
        return
    directory = Path(os.environ["RL00_EVENT_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.monotonic_ns()
    payload = {"phase": "collection", "pid": os.getpid(), "monotonic_ns": stamp,
               "native_ids": [item.nodeid for item in session.items]}
    (directory / (str(os.getpid()) + "-" + str(stamp) + ".json")).write_text(json.dumps(payload))
"""


def prepare(root: Path, repo: Path, profile: str) -> None:
    """Create only the experimental fixture in the caller's scratch root."""
    if profile != "python":
        invalid("expected python profile")
    root.mkdir(parents=True, exist_ok=True)
    (root / "owned_child.py").write_text(CHILD, encoding="utf-8")
    (root / "test_subject.py").write_text(CORPUS, encoding="utf-8")
    (root / "conftest.py").write_text(PLUGIN, encoding="utf-8")
    (root / "pytest.ini").write_text("[pytest]\npythonpath = src\n", encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "src/subject.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (root / "scenarios.toml").write_text(
        'schema_version = 1\ncomponent = "rl00bc"\n[[scenarios]]\n'
        'id = "subject-value"\nsummary = "The subject produces its expected value"\n'
        'capability = "library"\nlevel = "unit"\nstage = "commit"\n'
        'tests = ["test_subject::test_subject[ordinary]"]\n',
        encoding="utf-8",
    )
    python = Path(os.environ["RL00_PYTHON"])
    if not python.is_absolute() or not python.is_file():
        invalid("RL00_PYTHON must name the bootstrapped absolute interpreter")


def command(
    root: Path,
    repo: Path,
    output: Path,
    selected: str | None,
    *,
    profile: str,
    workers: int,
    coverage: bool,
) -> list[str]:
    """Construct pytest execution; selection is one discovered parameter ID."""
    if profile != "python" or workers not in (1, 2):
        invalid("unsupported profile or worker count")
    if selected is not None and (
        not selected or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in selected)
    ):
        invalid("invalid opaque parameter identity")
    output.mkdir(parents=True, exist_ok=True)
    if workers == 2 and selected is None and os.environ.get("RL00_INSTRUMENT") == "1":
        (root / "worker-sync.json").write_text("{}\n", encoding="utf-8")
    (output / "selection.json").write_text(json.dumps({"selected": selected}), encoding="utf-8")
    rc = output / "coveragerc"
    rc.write_text(f"[run]\nbranch = True\ndata_file = {output / '.coverage'}\n", encoding="utf-8")
    argv = [
        os.environ["RL00_PYTHON"],
        "-m",
        "pytest",
        "-c",
        str(root / "pytest.ini"),
        f"--rootdir={root}",
        "-p",
        "no:cacheprovider",
        "-q",
        f"--junitxml={output / 'junit.xml'}",
        "-o",
        "xfail_strict=true",
        "-p",
        "no:rerunfailures",
        "-p",
        "no:flaky",
    ]
    if workers == 2:
        argv += ["-n", "2"]
    if coverage:
        argv += [
            f"--cov={root / 'src'}",
            "--cov-branch",
            f"--cov-config={rc}",
            f"--cov-report=json:{output / 'coverage.json'}",
        ]
    target = str(root / "test_subject.py")
    argv.append(target if selected is None else f"{target}::test_subject[{selected}]")
    return argv


def _check_identities(cases: list[dict[str, object]], selected: object) -> None:
    ids = [str(case["id"]) for case in cases]
    if not cases or len(ids) != len(set(ids)):
        invalid("native result identity mismatch")
    if selected is not None and (len(cases) != 1 or cases[0]["variant"] != selected):
        invalid("native result identity mismatch")


def results(root: Path, output: Path, *, profile: str) -> list[dict[str, object]]:
    """Parse native JUnit and reject missing, duplicate or unexpected selections."""
    if profile != "python":
        invalid("expected python profile")
    document = ElementTree.parse(output / "junit.xml")
    cases: list[dict[str, object]] = []
    for case in document.iter("testcase"):
        name = case.get("name", "")
        identity = f"{case.get('classname', '')}::{name}"
        variant = name.removeprefix("test_subject[").removesuffix("]")
        outcome = next(
            (tag for tag in ("error", "failure", "skipped") if case.find(tag) is not None), "passed"
        )
        cases.append(
            {
                "id": identity,
                "variant": variant,
                "outcome": outcome,
                "coverage": str(output / "coverage.json")
                if (output / "coverage.json").is_file()
                else None,
            }
        )
    selected = json.loads((output / "selection.json").read_text(encoding="utf-8"))["selected"]
    _check_identities(cases, selected)
    return cases
