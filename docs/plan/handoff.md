# Implementation handoff

This page closes the build of the quality boilerplate, phases P00–P12 of the
[implementation plan](../../PLAN.md). It is a bounded summary: the phase
records, the [traceability matrix](traceability.md), and the
[adversarial checklist](adversarial.md) hold the evidence behind each line.

## Status

- Phases P00–P12 are `DONE`; their records list the implementation commits,
  checks, and limitations.
- Requirements R01–R10: every row of the matrix
  ([R01–R05](traceability.md), [R06–R10](traceability-r06-r10.md)) is
  `DONE` with its proof.
- Adversarial checks A01–A16: each negative case and its passing control
  case ran again in P12 ([P12 record](phases/P12.md#acceptance)).
- Final implementation commit:
  `701b24c1d6fdfe2a7349a928f65a54bd4628918b` on `build/v1`. The commit that
  adds this page records the completion and changes no code.
- Hosting is prepared, not live: see [Hosting](#hosting).

## Start

On Linux (x86_64 or aarch64, glibc) with Git 2.34 or newer and `python3`
3.10 or newer, from a clone of the template:

```sh
./quality bootstrap
./quality doctor
```

A new project starts with `./quality template export ../my-project` and the
same two commands inside it; the [README](../../README.md#getting-started)
continues from there. The prerequisites, including PHP 8.4 with Xdebug 3.5
for PHP components, are in
[decision 0002](../decisions/0002-installation-strategy.md).

## Versions

The pins and their primary sources are in
[decision 0001](../decisions/0001-toolchain-pins.md),
`tools/quality/toolchains.toml`, and the lockfiles. The versions that ran in
P12:

| Group | Versions |
| --- | --- |
| Host | Linux 5.15 x86_64, eight CPUs, unprivileged user namespaces; Git 2.34.1; system `python3` 3.10.12 for the launcher |
| Downloaded with verified checksums (CPython through uv) | uv 0.12.24, CPython 3.14.8, gitleaks 8.30.1, actionlint 1.7.12, osv-scanner 2.7.0, Node.js 24.22.0, Dart SDK 3.13.6, Composer 2.10.3 |
| System runtime, pinned to minor versions | PHP 8.4.14 with Xdebug 3.5.3; PCOV 1.0.12 for the acceptance suite only |
| Core (`tools/quality/uv.lock`) | Ruff 0.17.1, Pyright 1.1.414, pytest 9.1.1, coverage.py 7.16.2, pytest-cov 7.1.0, pytest-xdist 3.8.0, pydantic 2.14.1, markdown-it-py 4.2.0, PyMarkdown 0.9.41, PyYAML 6.0.3, defusedxml 0.7.1 |
| TypeScript helper | TypeScript 6.0.3, ESLint 10.13.0, typescript-eslint 8.72.0, Prettier 3.9.10, Vitest and `@vitest/coverage-v8` 5.0.5 |
| Dart helper | analyzer 14.5.0, test 1.33.0, coverage 1.16.0, lints 6.1.0 |
| PHP helper | nikic/php-parser 5.9.0, PHP CS Fixer 3.95.27, PHPStan 2.3.1, PHPUnit 13.4.3 |

## Verification

These ran in P12 against `701b24c` on the host above, with no result cache:
the core keeps none, and pytest runs without its cache provider. Details
and timings are in the [P12 record](phases/P12.md#checks-run).

| Command | Result |
| --- | --- |
| `./quality gate --stage merge --base main --head 701b24c` | Passed in 26m35s: 0 errors, the 4 warnings of P11; every unit suite at 100% line and branch coverage (quality-core 12200/12200 lines and 2746/2746 branches), changed lines 100% over the whole branch; scenarios of quality-core 6 of 6 and of quality-launcher 2 of 2 proved; 604 files; 2 findings covered by exceptions |
| The suites of that gate | quality-core 2511 unit, 6 end-to-end, and 143 acceptance cases; the launcher's and the three helpers' suites; no failure, error, or skip |
| Each case of the adversarial checklist and its control, in that run's JUnit reports | All passed; none absent |
| `./quality audit --rev 701b24c` | Five lockfiles, 0 findings |
| `./quality links` | 44 pages, 0 errors, 0 warnings |
| `./quality policy validate`, `policy schema --check`, `doctor`, `scenarios` | exit 0 |
| Native Ruff, Pyright, and pytest of the core | Clean; 2511 unit and 6 end-to-end tests passed at 100% line and branch coverage |
| `git commit` and `git push` of `701b24c` through the hooks | Accepted in 4m11s and 4m27s |

## Hosting

| Item | Status |
| --- | --- |
| Repository | `mikhailsal/ai-boilerplate` (public); branch `build/v1`, draft pull request #1 into `main` |
| GitHub Actions workflow | Live on GitHub-hosted `ubuntu-24.04` runners for `pull_request` events; `merge_group` and `push` to `main` have not run there |
| Required status `required` and the ruleset `.github/rulesets/main.json` | Prepared, not applied: the repository's settings and branch protection were never changed, so nothing on the host enforces them |
| Code owners | `.github/CODEOWNERS` prepared; not enforced without the ruleset |
| GitLab wrapper `ci/gitlab/quality.gitlab-ci.yml` | Validated locally only; never run on GitLab |

Of the six hosted runs on pull request #1, the last success is
[39588146798](https://github.com/mikhailsal/ai-boilerplate/actions/runs/39588146798)
on `f3dc0f2`, the P10 record. The runs on `f49801d` and `701b24c` stopped
before any check, when the ondrej PPA answered 503 while installing PHP, so
no hosted run has judged the code of P11 and P12 yet; their merge gates
passed locally ([P12 record](phases/P12.md#hosted-status)).

Applying and confirming the protection is the owner's step, described in the
[protection guide](../guides/protection.md#confirming-the-protection). Until
it is observed, a direct push or a failing pull request is not blocked by
the host. The owner applied it on 2026-10-28; the
[frontend handoff](frontend/handoff.md#merge-and-protection-2026-10-28)
records the ruleset and its probes.

## Known limitations

- Trust boundary: local hooks are bypassable (`--no-verify`, a removed hook,
  `core.hooksPath`), and repository files cannot constrain an equally
  privileged administrator. CI is the boundary only once the ruleset is
  applied. The gate runs the candidate's own core, so a pull request can
  change its validator; code-owner review of the control files is the
  protection, and a trusted external validator is a future option
  ([protection guide](../guides/protection.md#the-real-boundary)).
- PHP and Xdebug come from the system, pinned to minor versions only; patch
  versions can differ between machines, and the hosted jobs install them
  from the ondrej PPA, which was unavailable for one run (see above).
- Network isolation of unit suites needs unprivileged user namespaces;
  without them the check warns with `tests.network`, and the maintainer
  acceptance suite, which compares hook output exactly, fails.
- Native coverage semantics differ by language and are not averaged: Dart
  measures no `&&`, `??`, or conditional-expression branches, an Xdebug
  branch is a basic block, and V8 decides lines and branches for TypeScript
  ([decision 0005](../decisions/0005-coverage-measurement.md)).
- Configuration files of TypeScript tools run code during the check; the
  gate overrides what decides the verdict, and the rest is reviewed with the
  change. A test can forge a report inside its own output directory
  ([decision 0008](../decisions/0008-test-and-coverage-engine.md)).
- Scenario selectors are runner case names, so renaming a test is a
  manifest change; mutation testing is refused until a profile runs a
  tested mutation tool; property and performance profiles check that a
  tagged scenario passes, not its quality.
- `quality audit` needs the osv.dev API or a downloaded database, so it runs
  in merge CI, not in `check`. External links are probed by `quality links`
  only.
- Merge queues are unavailable to a repository owned by a user, and a sole
  maintainer cannot approve their own code-owner review.
- Cost: a change to `quality.toml` or `tools/quality` reruns the core's
  suites in every affected project. On the reference machine a commit of
  the core takes about four minutes through the hook, and the merge-stage
  gate with the acceptance suite about twenty-five; a Python suite may run
  for two hours before it times out.
- Each revision check runs gitleaks twice, over the tree and the history.
- Earlier phases left a `python3.14` link in this machine's `~/.local/bin`;
  it is outside the repository and was left for the user to remove.

## Review entry points

- [README](../../README.md) and [agent instructions](../../AGENTS.md): what
  the template does and the everyday commands.
- The [documentation index](../README.md): decisions 0001–0016, the guides,
  the [command-line reference](../reference/cli.md), and the
  [profile support matrix](../reference/profiles.md).
- The policy [`quality.toml`](../../quality.toml) and the core's layers in
  it; the core under `tools/quality/src/quality`, starting at `cli/main.py`,
  `engine/check.py`, `gitio/candidate.py`, and `rules/coverage.py`.
- The [workflow](../../.github/workflows/quality.yml) and the
  [protection guide](../guides/protection.md).
- To reproduce: `./quality gate --stage merge --base main --head HEAD`
  (every gate, every suite including the acceptance harness, and the new
  history), `./quality self-test --level acceptance`, and
  `./quality audit --rev HEAD`.
