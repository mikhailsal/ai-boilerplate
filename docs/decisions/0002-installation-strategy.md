# 0002 Installation strategy

Status: accepted (P00); amended in P03.

Commands that are not implemented yet are named in plain text with the phase
that delivers them; `quality check` fails documentation that presents a
missing command as runnable.

## Prerequisites (documented, not promised away)

- Linux on x86_64 or aarch64 with glibc.
- Git 2.40 or newer.
- `python3` 3.10 or newer from the distribution. It runs only the stdlib
  launcher `./quality`; the core itself runs on the pinned CPython 3.14.8.
- Network access while installing tools (`quality tools install`, and the
  bootstrap command from P05) and while updating pins (P11).
- For the PHP profile only: PHP 8.4 CLI with the `dom`, `mbstring`, `xml`,
  `xmlwriter`, and `tokenizer` extensions, plus Xdebug 3.5 installed but not
  necessarily enabled (Debian/Ubuntu: `php8.4-cli php8.4-xml php8.4-mbstring
  php8.4-xdebug`, from the distribution or the ondrej PPA).

## Managed downloads

The bootstrap command (P05) downloads pinned artifacts into a declared cache
(`$XDG_CACHE_HOME/quality`, default `~/.cache/quality`) and verifies each
SHA-256 against `tools/quality/toolchains.toml` before extraction. Since P03,
`quality tools install` performs the download and verification for the
standalone tools:

- always: uv, then the uv-managed CPython 3.14.8 and the locked core
  environment, gitleaks;
- TypeScript profile active: Node.js (npm is bundled);
- Dart profile active: the Dart SDK;
- PHP profile active: `composer.phar`;
- merge CI and maintainers: osv-scanner and actionlint.

The PHP runtime is the one toolchain not downloaded: portable PHP builds with
Xdebug are not a maintained upstream artifact. Its minor version and the
Xdebug minor version are pinned and verified by the doctor command (P05). This is the
honest gap: patch versions of PHP and Xdebug follow the system packages.

## Project dependencies

- Python components: `uv sync --frozen` from each component's `uv.lock`.
- TypeScript components: `npm ci` from `package-lock.json`.
- Dart components: `dart pub get --enforce-lockfile` from `pubspec.lock`.
- PHP components: `composer install` from `composer.lock`.

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
