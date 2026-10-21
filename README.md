# AI boilerplate

A Git repository template that enforces code, test, documentation, and
repository quality through local Git hooks and a CI-independent Linux
command-line interface. Python, TypeScript, Dart, and PHP components are
supported; see the [profile support matrix](docs/reference/profiles.md).

<!-- maintainer-only:begin -->

This is the template's own repository. Its policy runs in maintainer mode,
with the acceptance harness that tests the template itself, and the
[implementation plan](PLAN.md) records how it was built.

## Starting a project

On Linux with Git 2.34+ and `python3` 3.10+, export a new project from a
clone of the template:

```sh
./quality template export ../my-project
cd ../my-project
```

The export leaves out the maintainer content and makes the new directory a
repository whose root commit, made with your Git identity, names the
template commit it came from
([decision 0016](docs/decisions/0016-template-lifecycle.md)).

<!-- maintainer-only:end -->

## Getting started

On Linux with Git 2.34+ and `python3` 3.10+:

```sh
./quality bootstrap
./quality doctor
```

Bootstrap installs the pinned toolchain and a check-only `pre-commit` hook
that runs `./quality check` on every commit. Only the tools of the profiles
your components use are installed.

Add each component, a directory with a `pyproject.toml`, `package.json`,
`pubspec.yaml`, or `composer.json`, then stage it and bootstrap again so its
tools are ready before the hook checks it:

```sh
./quality component add libs/pricing --no-boundary-reason "Pure price calculations."
git add quality.toml libs/pricing
./quality bootstrap
git commit -m "Add the pricing library"
```

A component with boundaries declares them instead, for example
`--capability http-api`, and proves them with the scenarios of
[decision 0014](docs/decisions/0014-behavioral-scenarios.md).

Local hooks can be bypassed, so CI runs the same gate. Replace the owner in
[`.github/CODEOWNERS`](.github/CODEOWNERS) with your own team, and apply the
hosting protection described in the
[protection guide](docs/guides/protection.md), which also states
[what repository files cannot enforce](docs/guides/protection.md#the-real-boundary).

## Documentation

- [Agent instructions](AGENTS.md): setup, checks, boundaries, exceptions.
- [Documentation index](docs/README.md): decisions, guides, reference.
- [Quality core](tools/quality/README.md): the `quality` command-line tool.
