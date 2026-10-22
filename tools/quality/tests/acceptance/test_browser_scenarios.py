"""FR06 and FR07: the Chromium scenarios of a browser component, with the real tools.

`check --stage merge --all` builds the staged candidate, serves the build, and
runs the scenarios in the pinned Chromium in both viewports. The counter
passes and proves its scenarios, whatever stale output, server, or browser
the work tree and the component's own configuration name. Each other case
breaks one thing and finds exactly what that breaks.
"""

import threading
from collections.abc import Generator, Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import NamedTuple

import pytest

from quality.testkit.browserproject import APP, INDEX, STYLES
from quality.testkit.browserscenarios import BOUNDARY, SCENARIOS, SCENARIOS_FILE
from quality.testkit.scratch import Project, output, rules_of

COUNTER = "e2e/counter.spec.ts::the page shows the counter"
KEYBOARD = 'test("the counter counts from the keyboard", async ({ page }) => {\n'
SCANNED = "  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();\n"
SHOWN = '  await expect(page.getByRole("button", { name: "Count 0" })).toBeVisible();\n'
PROVOKED = SCENARIOS.replace(
    SHOWN, SHOWN + '  await page.evaluate(() => {\n    console.error("a provoked error");\n  });\n'
)
EXCEPTION = f"""
[[exceptions]]
rule = "typescript.browser-console"
path = "web/{SCENARIOS_FILE}"
symbol = "a provoked error"
reason = "The scenario provokes the error to show that it is reported."
owner = "the scratch maintainers"
review = 2999-01-01
"""
# What a stale build in the work tree and an unrelated server would show.
STALE = "<!doctype html>\n<title>Stale</title>\n<p>an old build</p>\n"
# The component's own configuration: a filter, retries, another browser, and a server.
CONFIG = """\
import { defineConfig } from "@playwright/test";

export default defineConfig({
  retries: 2,
  grep: /keyboard/,
  use: { baseURL: "{url}" },
  projects: [{ name: "firefox", use: { browserName: "firefox" } }],
  webServer: {
    command: "node -e 'process.exit(1)'",
    url: "{url}",
    reuseExistingServer: true,
  },
});
"""
SKIPPED = SCENARIOS.replace(KEYBOARD, KEYBOARD.replace("test(", "test.skip("))
NARROW = SCENARIOS.replace(
    KEYBOARD,
    KEYBOARD.replace("{ page }", "{ page }, testInfo")
    + '  test.skip(testInfo.project.name === "narrow", "not on a phone");\n',
)
BROKEN = 'throw new Error("the configuration is broken");\n'


class Case(NamedTuple):
    """The files of `web` a case changes, the rules it finds, and a line of their output."""

    files: Mapping[str, str]
    rules: set[str]
    text: str
    policy: str = ""
    status: int = 1


CASES = {
    "the-page-cannot-start": Case(
        {"index.html": INDEX.replace('id="root"', 'id="app"')},
        {"typescript.browser-console", "tests.failed", "scenarios.failed"},
        f"{COUNTER}: uncaught Error: the page has no #root element",
    ),
    "broken-asset": Case(
        {
            "src/App.tsx": APP.replace(
                "<h1>Counter</h1>", '<h1>Counter</h1>\n      <img src="/logo.svg" alt="" />'
            )
        },
        {"typescript.browser-resource"},
        f"{COUNTER} requested /logo.svg, which the production build does not have",
    ),
    "missing-response": Case(
        {
            SCENARIOS_FILE: SCENARIOS.replace(
                SHOWN, SHOWN + '  await page.evaluate(() => fetch("/data/counts.json"));\n'
            )
        },
        {"typescript.browser-resource"},
        f"{COUNTER} requested /data/counts.json, which the production build does not have",
    ),
    "scan-of-an-empty-page": Case(
        {
            SCENARIOS_FILE: SCENARIOS.replace(
                SCANNED,
                "  await page.evaluate(() => {\n    document.body.replaceChildren();\n  });\n"
                + SCANNED,
            )
        },
        {"typescript.accessibility-scan", "scenarios.evidence"},
        f"{COUNTER}: the scanned page had no content",
    ),
    "low-contrast": Case(
        {"src/App.module.css": STYLES.replace("  margin", "  color: #999;\n  margin")},
        {"typescript.accessibility"},
        f"{COUNTER}: color-contrast (serious) at h1",
    ),
    "provoked-console-error": Case(
        {SCENARIOS_FILE: PROVOKED}, {"typescript.browser-console"}, f"{COUNTER}: a provoked error"
    ),
    "excepted-console-error": Case(
        {SCENARIOS_FILE: PROVOKED}, set(), "1 findings covered by exceptions", EXCEPTION, 0
    ),
    "skipped-scenario": Case(
        {SCENARIOS_FILE: SKIPPED},
        {"tests.skipped", "scenarios.skipped"},
        "'e2e/counter.spec.ts::the counter counts from the keyboard' was skipped",
    ),
    "skipped-in-one-viewport": Case(
        {SCENARIOS_FILE: NARROW},
        {"tests.skipped", "scenarios.skipped"},
        "'e2e/counter.spec.ts::the counter counts from the keyboard' was skipped",
    ),
    "focused-scenario": Case(
        {SCENARIOS_FILE: SCENARIOS.replace(KEYBOARD, KEYBOARD.replace("test(", "test.only("))},
        {"tests.focused", "tests.none", "scenarios.absent"},
        "focused",
    ),
    "configuration-cannot-load": Case(
        {"playwright.config.ts": BROKEN},
        {"tools.failed", "scenarios.unverified"},
        "the configuration is broken",
        status=3,
    ),
}


def check(
    project: Project, files: Mapping[str, str], policy: str = ""
) -> tuple[int, set[str], str]:
    """Stage the changes, check every scenario, and restore the commit."""
    for path, text in files.items():
        project.write(f"web/{path}", text)
    if policy:
        project.write("quality.toml", (project.path / "quality.toml").read_text() + policy)
    project.repo.git("add", "-A")
    try:
        result = project.quality("check", "--stage", "merge", "--all")
    finally:
        project.repo.git("reset", "-q", "--hard")
        project.repo.git("clean", "-fdq")
    return result.returncode, rules_of(result), output(result)


class Stale(BaseHTTPRequestHandler):
    """An unrelated server, which answers every request with a stale page."""

    def do_GET(self) -> None:  # the name `http.server` dispatches to
        body = STALE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def unrelated() -> Generator[str]:
    """Serve the stale page on loopback while the test runs; yield its URL."""
    server = HTTPServer(("127.0.0.1", 0), Stale)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_the_built_counter_proves_its_scenarios_in_every_viewport(
    counter: Project, unrelated: str
) -> None:
    (counter.path / "web/dist").mkdir()
    (counter.path / "web/dist/index.html").write_text(STALE)
    config = CONFIG.replace("{url}", unrelated)
    status, rules, printed = check(counter, {"playwright.config.ts": config})
    assert (status, rules) == (0, set()), printed
    assert f"scenarios of web: 2 of 2 proved; tested boundaries: {BOUNDARY}" in printed, printed


@pytest.mark.parametrize("name", CASES)
def test_each_broken_scenario_is_found_for_its_own_reason(counter: Project, name: str) -> None:
    case = CASES[name]
    status, rules, printed = check(counter, case.files, case.policy)
    assert (status, rules) == (case.status, case.rules), printed
    assert case.text in printed, printed
