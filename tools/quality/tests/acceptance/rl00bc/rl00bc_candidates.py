"""CI-only candidate and conservative selection experiment, not a verdict cache."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_kernel

# This source is persisted before execution so the executed experiment is reviewable.
CHILD = r"""from __future__ import annotations
import hashlib, json, os, subprocess, sys, traceback, unittest
from pathlib import Path

repo, root, out = map(Path, sys.argv[1:])
sys.path[:0] = [str(repo / "tools/quality/src"), str(repo), str(root)]
from quality.gitio.candidate import staged, revision
from quality.gitio.revisions import push_candidate, merge_candidate
from quality.gitio.repo import Repository
from quality.gitio.errors import GitioError
from tests.acceptance.rl00bc import rl00bc_selection as selection

progress = {"completed": [], "success": False, "claim_limit": "Finite fixture and conservative fallback only; neither arbitrary dependency soundness nor strict execution success is proved."}
def save():
    (out / "candidate-evidence.json").write_text(json.dumps(progress, sort_keys=True) + "\n")
def mark(name, value=True):
    if name in progress["completed"]: raise ValueError("duplicate observation")
    progress["completed"].append(name)
    progress.setdefault("observations", {})[name] = value
    save()
def require(condition, message):
    if not condition: raise AssertionError(message)
def rejects(fn):
    try: fn()
    except (ValueError, GitioError): return
    raise AssertionError("expected rejection")
def git(*args):
    return subprocess.run(["git", *args], cwd=root, env=os.environ, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
def write(name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite): yield from flatten(item)
        else: yield item

def main():
    root.mkdir(parents=True)
    templates = root.parent / "empty-templates"
    templates.mkdir()
    git("init", "--quiet", "--initial-branch=main", "--template", str(templates))
    git("config", "user.name", "RL00 fixture")
    git("config", "user.email", "rl00@example.invalid")
    write("test_alpha.py", "import unittest\nclass Alpha(unittest.TestCase):\n def test_one(self): pass\n def test_two(self): pass\n")
    write("test_beta.py", "import unittest\nclass Beta(unittest.TestCase):\n def test_one(self): pass\n")
    write("source.py", "VALUE = 1\n")
    write("fixture.txt", "fixture\n")
    write("data.txt", "data\n")
    write("params.txt", "one\n")
    write("dependency.txt", "v1\n")
    write("runtime.txt", "v1\n")
    write("config.txt", "v1\n")
    git("add", ".")
    git("commit", "--quiet", "-m", "base")
    base = git("rev-parse", "HEAD")
    repository = Repository.discover(root, os.environ)
    cases = []
    for case in flatten(unittest.TestLoader().discover(str(root), pattern="test_*.py")):
        identity = case.id()
        module = identity.split(".", 1)[0]
        require(module in {"test_alpha", "test_beta"}, "unexpected collector module")
        cases.append({"id": identity, "variant": identity, "file": module + ".py"})
    cases.sort(key=lambda case: case["id"])
    require(len(cases) == 3 and len({case["id"] for case in cases}) == 3, "collector identity mismatch")
    mark("native-discovery", cases)
    write("source.py", "VALUE = 2\n")
    git("add", "source.py")
    index_candidate = staged(repository)
    require(index_candidate.base_tree == repository.tree_of(base), "staged base mismatch")
    index_candidate.verify_unchanged()
    write("source.py", "VALUE = 3\n")
    git("add", "source.py")
    rejects(index_candidate.verify_unchanged)
    git("commit", "--quiet", "-m", "head")
    head = git("rev-parse", "HEAD")
    tree = repository.tree_of(head)
    rev = revision(repository, "HEAD")
    push = push_candidate(repository, base, head)
    merge = merge_candidate(repository, base, head, head)
    queue = merge_candidate(repository, base, head, head, queue=True)
    for candidate in (rev, push, merge, queue):
        require(candidate.tree == tree and candidate.base_tree == repository.tree_of(base), "candidate comparison mismatch")
        candidate.verify_unchanged()
    require(push.lines is not None and merge.lines is not None and queue.lines is not None, "missing comparisons")
    mark("candidate-identities", {"base_tree": rev.base_tree, "tested_tree": tree,
                                  "staged_tree": index_candidate.tree, "head": head})
    context = {"candidate": head, "base": rev.base_tree, "tested_tree": tree,
               "policy": digest(repo / "quality.toml"),
               "runtime": hashlib.sha256((sys.version + "\n" + digest(Path(sys.executable))).encode()).hexdigest(),
               "source": hashlib.sha256((digest(repo / "tools/quality/src/quality/gitio/candidate.py") +
                   digest(repo / "tools/quality/src/quality/gitio/revisions.py") +
                   digest(repo / "tools/quality/src/quality/gitio/repo.py") +
                   digest(repo / "tools/quality/tests/acceptance/rl00bc/rl00bc_selection.py") +
                   digest(out / "candidate-child.py")).encode()).hexdigest(),
               "native_file_mapping_complete": True}
    all_ids = sorted(case["id"] for case in cases)
    def check(change, expected, first=False, candidate=None):
        bound = dict(context)
        if candidate is not None:
            bound.update(candidate=candidate.tree, base=candidate.base_tree, tested_tree=candidate.tree)
        scope = selection.build(bound, cases, [change], first_adoption=first)
        require(scope["selected"] == expected, "wrong selection for " + str(change))
        selection.verify(scope, bound, cases, expected)
        require(scope["canonical_success"] is None and not scope["selection_soundness_proved"], "invalid claim")
        return scope
    # Each change corresponds to an actual new Git candidate in this fixture.
    edits = [("test", "test_alpha.py"), ("source", "source.py"), ("fixture", "fixture.txt"),
             ("data", "data.txt"), ("parameter", "params.txt"), ("dependency", "dependency.txt"),
             ("runtime", "runtime.txt"), ("config", "config.txt"), ("unknown", "unknown.txt"),
             ("volatile", "volatile.txt")]
    selected = sorted(case["id"] for case in cases if case["file"] == "test_alpha.py")
    for kind, path in edits:
        write(path, (root / path).read_text() + "\n# mutation\n" if (root / path).exists() else "mutation\n")
        git("add", path)
        changed = staged(repository)
        require(changed.tree != tree and changed.base_tree == tree, "mutation did not change candidate")
        change = {"kind": kind, "path": path, "shared": "false", "dynamic": "false"}
        check(change, selected if kind == "test" else all_ids, candidate=changed)
        git("reset", "--quiet", "HEAD", "--", path)
        if path in ("unknown.txt", "volatile.txt"): (root / path).unlink()
        else: git("restore", "--worktree", "--", path)
        mark("mutation-" + kind, changed.tree)
    check({"kind": "test", "path": "test_alpha.py", "shared": "false", "dynamic": "false"}, all_ids, True)
    check({"kind": "test", "path": "absent.py", "shared": "false", "dynamic": "false"}, all_ids)
    for attribute in ("shared", "dynamic"):
        change = {"kind": "test", "path": "test_alpha.py", "shared": "false", "dynamic": "false"}
        change[attribute] = "true"
        check(change, all_ids)
    git("mv", "test_alpha.py", "test_renamed.py")
    renamed = staged(repository)
    require(renamed.tree != tree, "rename did not change candidate")
    check({"kind": "test", "path": "test_renamed.py", "shared": "false", "dynamic": "false"}, all_ids, candidate=renamed)
    git("reset", "--quiet", "HEAD")
    git("restore", "--worktree", "test_alpha.py")
    (root / "test_renamed.py").unlink()
    mark("fallback-and-rename", renamed.tree)
    scope = selection.build(context, cases, [{"kind": "source"}])
    for key in ("candidate", "base", "tested_tree", "policy", "runtime", "source"):
        rejects(lambda: selection.verify(scope, {**context, key: "stale"}, cases, all_ids))
    rejects(lambda: selection.verify(scope, context, cases, all_ids[:-1]))
    rejects(lambda: selection.verify(scope, context, cases, all_ids + [all_ids[0]]))
    rejects(lambda: selection.verify(scope, context, cases, all_ids + ["unexpected-variant"]))
    rejects(lambda: selection.build(context, cases + [cases[0]], [{"kind": "source"}]))
    changed_cases = [dict(case) for case in cases]
    changed_cases[0]["variant"] = "unexpected"
    rejects(lambda: selection.verify(scope, context, changed_cases, all_ids))
    diagnostic = selection.build(context, cases, [], explicit_ids=[all_ids[0]])
    require(not diagnostic["automatic_selection"] and diagnostic["canonical_success"] is None, "diagnostic promoted")
    selection.verify(diagnostic, context, cases, [all_ids[0]])
    mark("strict-evidence-rejections", {"scope_sha256": scope["scope_sha256"], "context": context})
    # A symbolic revision must notice a subsequent commit; fixed commit IDs remain stable.
    symbolic = revision(repository, "HEAD")
    write("source.py", "VALUE = 4\n")
    git("add", "source.py")
    git("commit", "--quiet", "-m", "advance")
    rejects(symbolic.verify_unchanged)
    revision(repository, head).verify_unchanged()
    mark("revision-drift")
    progress["success"] = True
    save()

try:
    save()
    main()
except BaseException as error:
    progress["error"] = type(error).__name__ + ": " + str(error)[:1000]
    progress["traceback"] = traceback.format_exc(limit=8)[-4000:]
    save()
    raise
"""


def prove(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    environment: dict[str, str],
    *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Run the frozen experiment in one resource-bound child, preserving nonpasses."""
    repo, scratch, output = repo.absolute(), scratch.absolute(), output.absolute()
    python = Path(environment["RL00_PYTHON"])
    if not python.is_absolute() or not python.is_file():
        raise ValueError("RL00_PYTHON must be an absolute executable file")
    output.mkdir(parents=True, exist_ok=False)
    scratch.mkdir(parents=True, exist_ok=True)
    root = scratch / "candidate-fixture"
    if root.exists():
        raise ValueError("candidate fixture must be fresh")
    source = output / "candidate-child.py"
    source.write_text(CHILD, encoding="utf-8")
    (output / "kernel").mkdir()
    home = scratch / "candidate-home"
    home.mkdir(exist_ok=False)
    env = {
        "PATH": f"{python.parent}:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "CI": "1",
    }
    deadline = min(ancestor_deadline_ns - 3_000_000_000, time.monotonic_ns() + 90_000_000_000)
    raw = rl00bc_kernel.execute(
        work,
        [str(python), str(source), str(repo), str(root), str(output)],
        scratch,
        env,
        output / "kernel",
        memory_mib=3072,
        tasks=256,
        native_seconds=90.0,
        ancestor_deadline_ns=ancestor_deadline_ns,
        payload_deadline_ns=deadline,
    )
    evidence: dict[str, object] = {}
    try:
        value = json.loads((output / "candidate-evidence.json").read_text(encoding="utf-8"))
        if isinstance(value, dict):
            evidence = value
    except OSError, ValueError:
        pass
    required = {
        "native-discovery",
        "candidate-identities",
        "fallback-and-rename",
        "strict-evidence-rejections",
        "revision-drift",
    } | {
        "mutation-" + kind
        for kind in (
            "test",
            "source",
            "fixture",
            "data",
            "parameter",
            "dependency",
            "runtime",
            "config",
            "unknown",
            "volatile",
        )
    }
    completed = evidence.get("completed")
    valid = (
        isinstance(completed, list)
        and len(completed) == len(set(completed))
        and set(completed) == required
    )
    return {
        "success": bool(
            raw.get("success")
            and raw.get("cleanup_complete")
            and evidence.get("success") is True
            and valid
        ),
        "classification": "observed-success"
        if raw.get("success")
        and raw.get("cleanup_complete")
        and evidence.get("success") is True
        and valid
        else "nonpass",
        "completed": completed if isinstance(completed, list) else [],
        "child_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "kernel_cause": raw.get("cause"),
        "cleanup_complete": raw.get("cleanup_complete"),
        "claim_limit": "Finite fixture and conservative fallback only; no selection soundness, strict execution success, or cached verdict is claimed.",
    }
