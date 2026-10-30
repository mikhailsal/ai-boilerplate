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

The template is available under the [MIT License](LICENSE). An export leaves
the root license out, so the new project chooses its own.

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
tools are ready before the hook checks it.

For Python, registration creates a missing `.python-version` from the core's
pinned interpreter and preserves an existing pin; stage that file with the
component. The [Python contract](docs/decisions/0009-python-profile.md#component-contract)
lists the other required settings and lockfile.

```sh
./quality component add libs/pricing --no-boundary-reason "Pure price calculations."
git add quality.toml libs/pricing
./quality bootstrap
git commit -m "Add the pricing library"
```

A component with boundaries declares them instead, for example
`--capability http-api`, and proves them with the scenarios of
[decision 0014](docs/decisions/0014-behavioral-scenarios.md).

### A browser application

A React + Vite application is a TypeScript component with the browser target.
To start from the [reference application](examples/web/README.md), copy its
tracked files, name your component in its scenario manifest, and register it;
registration also finds its `e2e/` suite and `scenarios.toml`:

```sh
git archive --prefix=apps/web/ HEAD:examples/web | tar -x
rm apps/web/README.md
sed -i 's/^component = "example-web"$/component = "web"/' apps/web/scenarios.toml
./quality component add apps/web --target browser
git add quality.toml apps/web
./quality bootstrap
git commit -m "Add the web application"
./quality test --component web --suite unit --suite e2e
```

Bootstrap installs the pinned Chromium, which needs the system libraries
listed in the
[prerequisites](docs/decisions/0002-installation-strategy.md#prerequisites-documented-not-promised-away).
The commit runs the static checks and the unit suites with their coverage
floors; the last command, like the merge stage, also builds the application
and proves its scenarios in Chromium. Then replace the pages, tests, and
scenarios with your own. The `audit` job of CI matches the copied lockfile
against current advisories; one without a fixed release needs a dated
exception for your copy too, like those in [`quality.toml`](quality.toml)
for the reference application ([exceptions guide](docs/guides/exceptions.md)).

The same commands add a frontend to a project that already has components,
such as a TypeScript Node service registered like the library above, and
they add a second application under another directory and name. Until a
browser component is staged, no bootstrap, hook, or gate needs Chromium.
The supported variants are in the
[profile matrix](docs/reference/profiles.md#browser-applications).

Local hooks can be bypassed, so CI runs the same gate. Replace the owner in
[`.github/CODEOWNERS`](.github/CODEOWNERS) with your own team, and apply the
hosting protection described in the
[protection guide](docs/guides/protection.md), which also states
[what repository files cannot enforce](docs/guides/protection.md#the-real-boundary).

## Documentation

- [Agent instructions](AGENTS.md): setup, checks, boundaries, exceptions.
- [Documentation index](docs/README.md): decisions, guides, reference.
- [Quality core](tools/quality/README.md): the `quality` command-line tool,
  under the MIT License in [`tools/quality/LICENSE`](tools/quality/LICENSE);
  keep that file when you copy or change the core.
