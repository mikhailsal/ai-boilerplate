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
| `src/quality/metrics` | Structure metrics model shared by profile adapters |
| `src/quality/boundedio.py` | Bounded JSON and XML readers for native tool reports |
| `src/quality/adapters` | Native tool adapters: Python structure and imports, Markdown lint, gitleaks, HTTP probes |
| `src/quality/rules` | Common rules: files, configuration, suppressions, docs, links, structure, architecture, exceptions |
| `src/quality/toolchain` | Pinned standalone tool manifest and verified installation |
| `src/quality/engine` | Gate orchestration for `check`, history ranges, and external links |
| `src/quality/catalog.py` | The registry of every rule the core can report |
| `src/quality/cli` | Argument parsing and subcommands (`check`, `explain`, `inventory`, `links`, `policy`, `tools`) |
| `src/quality/testkit` | Test builders shared by unit and contract tests |
| `toolchains.toml` | Versions, URLs, and SHA-256 checksums of standalone tools |
| `tests/unit` | Unit tests; they must keep core coverage at the policy minimum |

Packages depend only on lower layers, as described in
[decision 0003](../../docs/decisions/0003-architecture.md); the layer order is
declared in the root `quality.toml` and enforced by `quality check`. The gates
themselves are described in
[decision 0007](../../docs/decisions/0007-common-gates.md).

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
