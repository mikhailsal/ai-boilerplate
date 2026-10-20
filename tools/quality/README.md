# Quality core

The `quality` command-line tool decides whether a candidate change passes.
Git hooks and CI only call it. This directory holds its typed Python source,
unit tests, and locked development tooling.

## Layout

| Path | Contents |
| --- | --- |
| `src/quality/diagnostics` | Finding model, rule registry, text and JSON renderers |
| `src/quality/process` | Subprocess runner and allowlisted child environments |
| `src/quality/policy` | `quality.toml` models, loading, cross-validation, schema export |
| `src/quality/gitio` | Candidate trees, isolated snapshots, and changed-line diffs from Git plumbing |
| `src/quality/discovery` | File types, manifests, classification, component ownership, helper activation |
| `src/quality/boundedio.py` | Bounded JSON and XML readers for native tool reports |
| `src/quality/cli` | Argument parsing and subcommands (`explain`, `inventory`, `policy`) |
| `src/quality/testkit` | Test builders shared by unit and contract tests |
| `tests/unit` | Unit tests; they must keep core coverage at the policy minimum |

Packages depend only on lower layers, as described in
[decision 0003](../../docs/decisions/0003-architecture.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Passed |
| 1 | Violations found |
| 2 | Usage or policy error |
| 3 | Environment or tool error |
| 4 | Internal error |

## Native development commands

The tool versions are locked in `pyproject.toml` and `uv.lock`
([decision 0001](../../docs/decisions/0001-toolchain-pins.md)). Run these from
this directory:

```sh
uv sync --frozen --python 3.14.8
.venv/bin/ruff format --check src tests
.venv/bin/ruff check src tests
.venv/bin/pyright
.venv/bin/python -m pytest --cov=src --cov-branch
```

After changing a policy model, regenerate the committed schema from the
repository root:

```sh
PYTHONPATH=tools/quality/src tools/quality/.venv/bin/python -m quality policy schema --write
```
