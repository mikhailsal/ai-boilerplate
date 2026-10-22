"""Playwright Test against the gate's server, with a configuration the gate writes (decision 0018).

The gate writes `playwright.quality.mjs` into the run's output directory. It
imports the component's `playwright.config.*`, when there is one, and
overrides what decides the verdict:

- test files are the suite's roots with Playwright's default test-file
  pattern, below the component directory; the component's test filters,
  shards, and `webServer` are off, so no development or reused server is
  tested;
- `baseURL` is the gate's server, and every project is Chromium in the
  pinned headless shell, one per declared viewport, replacing the
  component's projects;
- retries are 0, `.only` fails the run, a test that passes only on its own
  retry fails, and snapshots are never written;
- traces record console messages, page errors, and requests, without
  screenshots, snapshots, or sources, in the output directory;
- the reporters are Playwright's list reporter and the gate's own, which
  writes `playwright.json` (see `quality.testing.playwright`) with each
  test's error messages, and saves each attachment the tests attach in memory
  as a file.

Playwright never downloads or looks up a browser of its own: its browser
directory is an empty directory of the run. Tests get a new home, cache, and
temporary directory, and the run's leftover processes are stopped.
"""

from __future__ import annotations

import json
from pathlib import Path

from quality.adapters.native import fail, failure
from quality.adapters.typescript.environment import Node
from quality.boundedio import JsonValue
from quality.process import Command, ProcessError, run
from quality.testing import SuiteRequest

SUITE_TIMEOUT = 3600.0
TOOL = "playwright"
COMMAND = "playwright"
WRAPPER = "playwright.quality.mjs"
REPORTER = "quality-playwright-reporter.mjs"
RESULTS = "playwright.json"
LOG = "playwright.log"
CONFIG_FILES = tuple(f"playwright.config.{ext}" for ext in ("ts", "mts", "cts", "js", "mjs", "cjs"))
TEST_FILES = r"\.(spec|test)\.(c|m)?[jt]sx?$"
TRACE: dict[str, JsonValue] = {
    "mode": "on",
    "screenshots": False,
    "snapshots": False,
    "sources": False,
}
REPORTER_BODY = """\
import { mkdirSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";

export default class QualityReporter {
  onBegin(config, suite) {
    this.suite = suite;
    this.errors = [];
  }

  onError(error) {
    this.errors.push(error.message ?? error.value ?? String(error));
  }

  saved(attachment, index) {
    if (attachment.path !== undefined) return attachment.path;
    const directory = join(settings.output, "attachments");
    mkdirSync(directory, { recursive: true });
    const path = join(directory, `${index}.bin`);
    writeFileSync(path, attachment.body ?? "");
    return path;
  }

  onEnd(result) {
    if (result.status !== "passed" && result.status !== "failed") {
      this.errors.push(`the run ended with status ${result.status}`);
    }
    let index = 0;
    const tests = (this.suite?.allTests() ?? []).map((test) => {
      const last = test.results.at(-1);
      const attachments = (last?.attachments ?? []).map((attachment) => ({
        name: attachment.name,
        path: this.saved(attachment, index++),
      }));
      return {
        file: relative(settings.directory, test.location.file).split(sep).join("/"),
        title: test.titlePath().slice(3),
        project: test.parent.project()?.name ?? "",
        outcome: test.outcome(),
        expected: test.expectedStatus,
        errors: (last?.errors ?? []).map((error) => error.message ?? String(error.value)),
        attachments,
      };
    });
    const projects = settings.projects;
    writeFileSync(settings.results, JSON.stringify({ projects, tests, errors: this.errors }));
  }
}
"""
WRAPPER_BODY = """\
const escape = (text) => text.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&");
const base = (await loaded.default) ?? {};
const use = base.use ?? {};

export default {
  ...base,
  testDir: settings.directory,
  testMatch: settings.roots.map(
    (root) => new RegExp(`^${escape(root)}/.*${settings.files}`),
  ),
  testIgnore: [/[\\\\/]node_modules[\\\\/]/],
  grep: undefined,
  grepInvert: undefined,
  shard: null,
  webServer: undefined,
  retries: 0,
  forbidOnly: true,
  failOnFlakyTests: true,
  updateSnapshots: "none",
  outputDir: settings.artifacts,
  reporter: [["list"], [settings.reporter]],
  use: {
    ...use,
    baseURL: settings.baseURL,
    trace: settings.trace,
    browserName: "chromium",
    headless: true,
    channel: undefined,
    connectOptions: undefined,
    launchOptions: { ...use.launchOptions, executablePath: settings.executable },
  },
  projects: settings.viewports.map(([name, viewport]) => ({ name, use: { viewport } })),
};
"""


def user_config(directory: Path) -> Path | None:
    """Return the configuration file Playwright would load from the component directory."""
    return next((directory / name for name in CONFIG_FILES if (directory / name).is_file()), None)


def settings(request: SuiteRequest, url: str, executable: Path) -> dict[str, JsonValue]:
    """Return the values the configuration and the reporter of one run read."""
    viewports = request.component.browser_settings.viewports
    return {
        "directory": str(request.directory),
        "roots": [str(request.directory / root) for root in request.roots],
        "files": TEST_FILES,
        "baseURL": url,
        "executable": str(executable),
        "trace": TRACE,
        "artifacts": str(request.output / "artifacts"),
        "output": str(request.output),
        "reporter": str(request.output / REPORTER),
        "results": str(request.output / RESULTS),
        "projects": list(viewports),
        "viewports": [
            [name, {"width": size.width, "height": size.height}] for name, size in viewports.items()
        ],
    }


def _settings(values: dict[str, JsonValue]) -> str:
    return f"const settings = {json.dumps(values, indent=2)};\n"


def wrapper(request: SuiteRequest, values: dict[str, JsonValue]) -> str:
    """Return the configuration module that runs one suite."""
    config = user_config(request.directory)
    load = (
        f"import * as loaded from {json.dumps(str(config))};"
        if config is not None
        else "const loaded = {};"
    )
    return f"{load}\n{_settings(values)}{WRAPPER_BODY}"


def reporter(values: dict[str, JsonValue]) -> str:
    """Return the reporter module that writes the run's results."""
    return f"{_settings(values)}\n{REPORTER_BODY}"


def playwright_command(
    node: Node, script: Path, request: SuiteRequest, values: dict[str, JsonValue]
) -> Command:
    """Write the run's configuration and reporter; return the command that runs the suite."""
    config = request.output / WRAPPER
    config.write_text(wrapper(request, values), encoding="utf-8")
    (request.output / REPORTER).write_text(reporter(values), encoding="utf-8")
    home = request.output.parent / f"{request.output.name}-home"
    temporary, cache, browsers = home / "tmp", home / ".cache", home / "browsers"
    for directory in (temporary, cache, browsers):
        directory.mkdir(parents=True)
    extra = {
        "TMPDIR": str(temporary),
        "XDG_CACHE_HOME": str(cache),
        "PLAYWRIGHT_BROWSERS_PATH": str(browsers),
        "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1",
        "CI": "1",
    }
    return Command(
        (str(node.executable), str(script), "test", "--config", str(config)),
        cwd=request.directory,
        timeout=SUITE_TIMEOUT,
        env=node.environ(home, extra),
        reap=True,
    )


def run_playwright(
    node: Node, script: Path, request: SuiteRequest, values: dict[str, JsonValue]
) -> tuple[int, Path]:
    """Run one suite; return its exit status and results. A run without results failed.

    What Playwright printed is kept as `playwright.log` beside the results.
    """
    try:
        completed = run(playwright_command(node, script, request, values))
    except ProcessError as error:
        raise failure(TOOL, str(error)) from error
    log = completed.stdout_text() + completed.stderr_text()
    (request.output / LOG).write_text(log, encoding="utf-8")
    results = request.output / RESULTS
    if not results.exists():
        output = (completed.stderr_text() or completed.stdout_text()).strip()
        fail(TOOL, f"exit status {completed.returncode} without test results: {output}")
    return completed.returncode, results
