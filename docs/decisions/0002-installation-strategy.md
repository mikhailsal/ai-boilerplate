# 0002 Installation strategy

Status: accepted (P00); amended in P03, P05, P06, and P08.

Commands that are not implemented yet are named in plain text with the phase
that delivers them; `quality check` fails documentation that presents a
missing command as runnable.

## Prerequisites (documented, not promised away)

- Linux on x86_64 or aarch64 with glibc.
- Git 2.34 or newer (Ubuntu 22.04); `quality doctor` reports an older Git as
  `git.version`. P05 lowered the minimum from 2.40 after the core proved to
  need no newer plumbing ([decision 0006](0006-discovery-and-classification.md#git-version)).
- `python3` 3.10 or newer from the distribution. It runs only the stdlib
  launcher `./quality`; the core itself runs on the pinned CPython 3.14.8.
- Network access while bootstrapping (`./quality bootstrap`, or
  `quality tools install` for the standalone tools) and while updating pins
  (P11).
- For the PHP profile only: PHP 8.4 CLI with the `dom`, `mbstring`, `xml`,
  `xmlwriter`, and `tokenizer` extensions, the `zip` extension or the `unzip`
  command for Composer's archives, plus Xdebug 3.5 installed but not
  necessarily enabled (Debian/Ubuntu: `php8.4-cli php8.4-xml php8.4-mbstring
  php8.4-zip php8.4-xdebug`, from the distribution or the ondrej PPA). The
  gate loads Xdebug itself when the system does not; PCOV and phpdbg cannot
  replace it. The core's own acceptance suite also needs PCOV
  (`php8.4-pcov`) to prove that a machine with only PCOV cannot pass
  ([decision 0013](0013-php-profile.md#runtime)).

## Managed downloads

`./quality bootstrap` downloads pinned artifacts into a declared cache
(`$XDG_CACHE_HOME/quality`, default `~/.cache/quality`) and verifies each
SHA-256 against `tools/quality/toolchains.toml` before extraction. Since P03,
`quality tools install` performs the download and verification for the
standalone tools:

- always: uv, then the uv-managed CPython 3.14.8 and the locked core
  environment, gitleaks;
- TypeScript profile active: Node.js (npm is bundled), installed by
  `quality bootstrap` only when a TypeScript component exists, or explicitly
  with `quality tools install node` (since P06);
- Dart profile active: the Dart SDK, installed by `quality bootstrap` only
  when a Dart component exists, or explicitly with `quality tools install
  dart` (since P07);
- PHP profile active: `composer.phar`, installed by `quality bootstrap` only
  when a PHP component exists, or explicitly with `quality tools install
  composer` (since P08);
- merge CI and maintainers: osv-scanner and actionlint.

The PHP runtime is the one toolchain not downloaded: portable PHP builds with
Xdebug are not a maintained upstream artifact. Its minor version and the
Xdebug minor version are pinned under `[runtimes]` in
`tools/quality/toolchains.toml` and verified by `quality bootstrap`,
`quality doctor`, and every check that runs a PHP tool. This is the honest
gap: patch versions of PHP and Xdebug follow the system packages.

## Project dependencies

- Python components: `uv sync --frozen` from each component's `uv.lock`.
- TypeScript components: `npm ci --ignore-scripts` from `package-lock.json`,
  with the shared npm cache `$XDG_CACHE_HOME/quality/npm`
  ([decision 0011](0011-typescript-profile.md#environments)).
- Dart components: `dart pub get --enforce-lockfile` from `pubspec.lock`,
  with the shared pub cache `$XDG_CACHE_HOME/quality/pub`
  ([decision 0012](0012-dart-profile.md#environments)).
- PHP components: `composer install --no-scripts --no-plugins` from
  `composer.lock`, with the shared Composer cache
  `$XDG_CACHE_HOME/quality/composer`
  ([decision 0013](0013-php-profile.md#environments)).

Bootstrap fills the package caches. Ordinary checks run the same commands in
offline mode (`--offline`, `COMPOSER_DISABLE_NETWORK=1`), so a check never
fetches floating tools or rules; a cache miss is an actionable error that
names the install command.

## Clean-environment proof

P11 runs a fresh template export in a pinned `ubuntu` container image
(referenced by digest) with only the prerequisites above, then runs the
bootstrap, doctor, and whole-repository check commands.

## Updates

A tools update command (P11) rewrites pins and checksums in
`tools/quality/toolchains.toml` from vendor checksum files, producing a
reviewable diff. It never runs during checks.
