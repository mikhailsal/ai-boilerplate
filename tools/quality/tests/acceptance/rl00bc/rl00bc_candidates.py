"""CI-only candidate and conservative selection experiment, not a verdict cache."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_kernel
from tests.acceptance.rl00bc.rl00bc_errors import invalid

# This source is persisted before execution so the executed experiment is reviewable.
CHILD = r"""from __future__ import annotations
import hashlib, json, os, subprocess, sys, traceback, unittest
from pathlib import Path

repo, root, out = map(Path, sys.argv[1:])
sys.path[:0] = [str(repo / "tools/quality/src"), str(repo / "tools/quality"), str(root)]
from quality.gitio.candidate import staged, revision
from quality.gitio.revisions import push_candidate, merge_candidate
from quality.gitio.repo import Repository
from quality.gitio.errors import GitioError
from tests.acceptance.rl00bc import rl00bc_selection as selection
from tests.acceptance.rl00bc import rl00bc_candidate_changes as actual_changes

progress = {"completed": [], "success": False,
            "claim_limit": "Finite fixture and conservative fallback only; "
                           "neither arbitrary dependency soundness nor "
                           "strict execution success is proved."}
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

def native_cases(candidate, label):
    collections = progress.setdefault("native_collections", [])
    directory = out / ("native-collection-" + str(len(collections)).zfill(3))
    rows = actual_changes.collect(repository, candidate, directory)
    collections.append({"label": label, "directory": str(directory),
                        "tree": candidate.tree, "base": candidate.base_tree})
    save()
    return rows

def main():
    global repository
    root.mkdir(parents=True)
    templates = root.parent / "empty-templates"
    templates.mkdir()
    git("init", "--quiet", "--initial-branch=main", "--template", str(templates))
    git("config", "user.name", "RL00 fixture")
    git("config", "user.email", "rl00@example.invalid")
    write("test_alpha.py", "import unittest\nclass Alpha(unittest.TestCase):\n"
          " def test_one(self): pass\n def test_two(self): pass\n")
    write("test_beta.py", "import unittest\nclass Beta(unittest.TestCase):\n"
          " def test_one(self): pass\n")
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
    cases = native_cases(revision(repository, base), "base")
    require({case["file"] for case in cases} == {"test_alpha.py", "test_beta.py"},
            "native file mapping differs")
    require(len(cases) == 3 and len({case["id"] for case in cases}) == 3,
            "collector identity mismatch")
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
        require(candidate.tree == tree and candidate.base_tree == repository.tree_of(base),
                "candidate comparison mismatch")
        candidate.verify_unchanged()
    require(push.lines is not None and merge.lines is not None and queue.lines is not None,
            "missing comparisons")
    mark("candidate-identities", {"base_tree": rev.base_tree, "tested_tree": tree,
                                  "staged_tree": index_candidate.tree, "head": head})
    context = {"candidate": head, "base": rev.base_tree, "tested_tree": tree,
               "policy": digest(repo / "quality.toml"),
               "runtime": hashlib.sha256((sys.version + "\n" +
                   digest(Path(sys.executable))).encode()).hexdigest(),
               "source": hashlib.sha256((
                   digest(repo / "tools/quality/src/quality/gitio/candidate.py") +
                   digest(repo / "tools/quality/src/quality/gitio/revisions.py") +
                   digest(repo / "tools/quality/src/quality/gitio/repo.py") +
                   digest(repo / "tools/quality/tests/acceptance/rl00bc/rl00bc_selection.py") +
                   digest(repo / "tools/quality/tests/acceptance/rl00bc/rl00bc_errors.py") +
                   digest(repo / "tools/quality/tests/acceptance/rl00bc" /
                          "rl00bc_candidate_changes.py") +
                   digest(out / "candidate-child.py")).encode()).hexdigest(),
               "native_file_mapping_complete": True, "comparison_trusted": True}
    all_ids = sorted(case["id"] for case in cases)
    def check(change, expected, first=False, candidate=None):
        bound = dict(context)
        if candidate is not None:
            bound.update(candidate=candidate.tree, base=candidate.base_tree,
                         tested_tree=candidate.tree)
        scope = selection.build(bound, cases, [change], first_adoption=first)
        require(scope["selected"] == expected, "wrong selection for " + str(change))
        selection.verify(scope, bound, cases, expected)
        require(scope["canonical_success"] is None and not scope["selection_soundness_proved"],
                "invalid claim")
        return scope
    def check_actual(candidate, expected, *, first=False, trusted=True, label="mutation"):
        current_cases = native_cases(candidate, label)
        actual = actual_changes.read(
            repository, candidate, current_cases, comparison_trusted=trusted,
            independent_fixture_files=frozenset({"test_alpha.py", "test_beta.py"}),
        )
        bound = {**context, "candidate": candidate.tree, "base": candidate.base_tree,
                 "tested_tree": candidate.tree, "comparison_trusted": trusted,
                 "native_file_mapping_complete": actual["native_file_mapping_complete"],
                 "independent_fixture_files": actual["independent_fixture_files"]}
        scope = selection.build(bound, current_cases, actual["changes"], first_adoption=first)
        require(scope["selected"] == expected, "actual candidate selection differs: " + label)
        selection.verify(scope, bound, current_cases, expected)
        progress.setdefault("actual_scopes", []).append({
            "label": label, "actual": actual, "selected": scope["selected"],
            "reason": scope["reason"], "scope_sha256": scope["scope_sha256"],
            "strict_execution": "unproved; this observation tests scope binding only",
        })
        save()
        return scope
    # Each change corresponds to an actual new Git candidate in this fixture.
    edits = [("test", "test_alpha.py"), ("source", "source.py"), ("fixture", "fixture.txt"),
             ("data", "data.txt"), ("parameter", "params.txt"), ("dependency", "dependency.txt"),
             ("runtime", "runtime.txt"), ("config", "config.txt"), ("unknown", "unknown.txt"),
             ("volatile", "volatile.txt")]
    selected = sorted(case["id"] for case in cases if case["file"] == "test_alpha.py")
    for kind, path in edits:
        write(path, (root / path).read_text() + "\n# mutation\n"
              if (root / path).exists() else "mutation\n")
        git("add", path)
        changed = staged(repository)
        require(changed.tree != tree and changed.base_tree == tree,
                "mutation did not change candidate")
        check_actual(changed, selected if kind == "test" else all_ids, label=kind)
        if kind == "test":
            check_actual(changed, all_ids, first=True, label="first-adoption")
            mark("actual-first-adoption")
            check_actual(changed, all_ids, trusted=False, label="untrusted")
            mark("untrusted-comparison")
        git("reset", "--quiet", "HEAD", "--", path)
        if path in ("unknown.txt", "volatile.txt"): (root / path).unlink()
        else: git("restore", "--worktree", "--", path)
        mark("mutation-" + kind, changed.tree)
    check({"kind": "test", "path": "test_alpha.py", "shared": "false", "dynamic": "false"},
          all_ids, True)
    check({"kind": "test", "path": "absent.py", "shared": "false", "dynamic": "false"}, all_ids)
    for attribute in ("shared", "dynamic"):
        change = {"kind": "test", "path": "test_alpha.py", "shared": "false", "dynamic": "false"}
        change[attribute] = "true"
        check(change, all_ids)
    git("mv", "test_alpha.py", "test_renamed.py")
    renamed = staged(repository)
    require(renamed.tree != tree, "rename did not change candidate")
    renamed_ids = sorted(identity.replace("test_alpha.", "test_renamed.") for identity in all_ids)
    check_actual(renamed, renamed_ids, label="rename")
    git("reset", "--quiet", "HEAD")
    git("restore", "--worktree", "test_alpha.py")
    (root / "test_renamed.py").unlink()
    mark("fallback-and-rename", renamed.tree)
    git("rm", "--quiet", "test_beta.py")
    deleted = staged(repository)
    check_actual(deleted, selected, label="delete")
    git("reset", "--quiet", "HEAD", "--", "test_beta.py")
    git("restore", "--worktree", "--", "test_beta.py")
    mark("deleted-case-fallback", deleted.tree)
    mark("native-snapshot-candidate-selection", {
        "collections": len(progress["native_collections"]),
        "scope_count": len(progress["actual_scopes"]),
        "claim_limit": "Real candidate snapshots and Git diff; independent finite fixture only",
    })
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
    require(not diagnostic["automatic_selection"] and diagnostic["canonical_success"] is None,
            "diagnostic promoted")
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


def _valid_completed(completed: object) -> bool:
    required = {
        "native-discovery",
        "candidate-identities",
        "fallback-and-rename",
        "strict-evidence-rejections",
        "revision-drift",
        "actual-first-adoption",
        "untrusted-comparison",
        "deleted-case-fallback",
        "native-snapshot-candidate-selection",
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
    items = cast(list[object], completed) if isinstance(completed, list) else []
    valid = all(isinstance(item, str) for item in items)
    names = cast(list[str], items) if valid else []
    return valid and len(names) == len(set(names)) and set(names) == required


def _read_evidence(path: Path) -> tuple[dict[str, object], str | None]:
    try:
        if path.stat().st_size > 1_048_576:
            invalid("candidate evidence exceeds its finite byte bound")
        value: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            invalid("candidate evidence must be an object")
    except (OSError, ValueError) as error:
        return {}, f"{type(error).__name__}: {error}"[:1024]
    return cast(dict[str, object], value), None


def _evaluate(output: Path, source: Path, raw: dict[str, object]) -> dict[str, object]:
    evidence, parse_error = _read_evidence(output / "candidate-evidence.json")
    completed = evidence.get("completed")
    success = bool(
        raw.get("success")
        and raw.get("cleanup_complete")
        and evidence.get("success") is True
        and _valid_completed(completed)
    )
    return {
        "success": success,
        "classification": "observed-success" if success else "nonpass",
        "completed": completed if isinstance(completed, list) else [],
        "evidence_error": parse_error,
        "child_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "kernel_cause": raw.get("cause"),
        "cleanup_complete": raw.get("cleanup_complete"),
        "claim_limit": (
            "Finite fixture and conservative fallback only; no selection soundness, "
            "strict execution success, or cached verdict is claimed."
        ),
    }


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
        invalid("RL00_PYTHON must be an absolute executable file")
    output.mkdir(parents=True, exist_ok=False)
    scratch.mkdir(parents=True, exist_ok=True)
    root = scratch / "candidate-fixture"
    if root.exists():
        invalid("candidate fixture must be fresh")
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
    return _evaluate(output, source, raw)
