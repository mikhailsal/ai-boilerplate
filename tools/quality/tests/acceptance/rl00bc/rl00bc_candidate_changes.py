"""Bind conservative fixture selection to actual Git changes and native discovery.

Only explicitly declared independent files of this finite experiment may narrow
selection. This is not a general dependency analysis or a persisted impact map.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import cast

from quality.gitio import Candidate, FileChange, Repository, materialize, tree_changes
from quality.process import Command, run, sanitized
from tests.acceptance.rl00bc.rl00bc_errors import invalid

COLLECT = r"""import json,os,sys,unittest
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
def flatten(suite):
 for item in suite:
  if isinstance(item,unittest.TestSuite): yield from flatten(item)
  else: yield item
cases=[]
for case in flatten(unittest.TestLoader().discover(str(root),pattern='test_*.py')):
 module=sys.modules[case.__class__.__module__]
 source=Path(module.__file__).resolve()
 if not source.is_relative_to(root): raise ValueError('collector module outside candidate')
 identity=case.id()
 cases.append({'id':identity,'variant':identity,'file':str(source.relative_to(root))})
cases.sort(key=lambda item:item['id'])
print(json.dumps({'cases':cases,'pid':os.getpid(),'uid':os.getuid(),
                  'cgroup':Path('/proc/self/cgroup').read_text()}))
"""


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid("native discovery did not return an object")
    return cast(dict[str, object], value)


def collect(repo: Repository, candidate: Candidate, output: Path) -> list[dict[str, object]]:
    """Discover each candidate in a fresh process and actual isolated core snapshot."""
    candidate.verify_unchanged()
    output.mkdir(parents=True, exist_ok=False)
    with materialize(repo, candidate.tree) as snapshot:
        result = run(Command(
            (sys.executable, "-c", COLLECT, str(snapshot.root)),
            cwd=snapshot.root, timeout=20,
            env=sanitized(extra={"PYTHONDONTWRITEBYTECODE": "1"}),
            output_limit=65_536, reap=True,
        ))
    (output / "stdout.json").write_bytes(result.stdout)
    (output / "stderr.log").write_bytes(result.stderr)
    if not result.ok or result.stdout_truncated or result.stderr_truncated:
        invalid("bounded native candidate discovery did not complete")
    data = _object(json.loads(result.stdout))
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        invalid("candidate native discovery returned no cases")
    rows = [_object(value) for value in cast(list[object], cases)]
    candidate.verify_unchanged()
    receipt = {
        "candidate_tree": candidate.tree, "base_tree": candidate.base_tree,
        "producer": "unittest discovery in a fresh candidate snapshot",
        "source_sha256": hashlib.sha256(COLLECT.encode()).hexdigest(),
        "duration_seconds": result.duration, "native": data,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    return rows


def _native_files(cases: list[dict[str, object]]) -> set[str]:
    files: set[str] = set()
    for case in cases:
        value = case.get("file")
        if not isinstance(value, str) or not value:
            return set()
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            return set()
        files.add(value)
    return files


def _change(change: FileChange, independent: set[str]) -> list[dict[str, str]]:
    narrow = change.status == "M" and change.old_is_file and change.new_is_file
    narrow = narrow and change.path in independent
    flag = "false" if narrow else "true"
    records = [{
        "kind": "test" if narrow else "unknown", "path": change.path,
        "shared": flag, "dynamic": flag, "status": change.status,
        "old_oid": change.old_oid, "new_oid": change.new_oid,
    }]
    if change.old_path is not None:
        records.append({"kind": "unknown", "path": change.old_path,
                        "shared": "true", "dynamic": "true", "status": change.status})
    return records


def read(
    repo: Repository, candidate: Candidate, cases: list[dict[str, object]], *,
    comparison_trusted: bool,
    independent_fixture_files: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """Derive every selected path from Git; unknown comparisons force full fallback."""
    candidate.verify_unchanged()
    files = _native_files(cases)
    changes = tree_changes(repo, candidate.base_tree, candidate.tree)
    trusted = comparison_trusted is True
    independent: set[str] = files & independent_fixture_files if trusted else set()
    records = [record for change in changes for record in _change(change, independent)]
    raw_changes = list(records)
    if not trusted:
        records = [{"kind": "unknown", "path": "untrusted-comparison"}]
    candidate.verify_unchanged()
    return {
        "candidate_tree": candidate.tree, "base_tree": candidate.base_tree,
        "comparison_trusted": trusted,
        "native_file_mapping_complete": bool(files),
        "independent_fixture_files": sorted(independent), "changes": records,
        "actual_git_changes": raw_changes,
        "claim_limit": "explicit independent fixture files only; no general influence proof",
    }
