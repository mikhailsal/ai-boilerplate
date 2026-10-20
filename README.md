# AI boilerplate

A Git repository template that enforces code, test, documentation, and
repository quality through local Git hooks and a CI-independent Linux
command-line interface.

Work in progress: see the [implementation plan](PLAN.md).

## Getting started

On Linux with Git 2.34+ and `python3` 3.10+:

```sh
./quality bootstrap
./quality doctor
```

Bootstrap installs the pinned toolchain and a check-only `pre-commit` hook
that runs `./quality check` on every commit.

## Documentation

- [Agent instructions](AGENTS.md): setup, checks, boundaries, exceptions.
- [Documentation index](docs/README.md): decisions, reference, plan.
- [Quality core](tools/quality/README.md): the `quality` command-line tool.
