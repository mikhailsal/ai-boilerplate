"""AUD-001: component configuration cannot substitute the gate's production server."""

import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from quality.testkit.scratch import Project, output, rules_of


class Rogue(BaseHTTPRequestHandler):
    """Answer a forward proxy request with content absent from the candidate."""

    calls: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        self.calls.append(self.path)
        body = b"<!doctype html><title>Rogue</title><h1>Rogue welcome</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def rogue() -> Generator[str]:
    Rogue.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Rogue)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def check_config(counter: Project, config: str) -> str:
    counter.write("web/playwright.config.ts", config)
    counter.repo.git("add", "-A")
    try:
        result = counter.quality("check", "--stage", "merge", "--all")
    finally:
        counter.repo.git("reset", "-q", "--hard")
        counter.repo.git("clean", "-fdq")
    assert (result.returncode, rules_of(result)) == (
        1,
        {"typescript.playwright", "scenarios.unverified"},
    ), output(result)
    assert "web/playwright.config.ts: error:" in output(result)
    assert "2 of 2 proved" not in output(result)
    return output(result)


def test_a_real_rogue_proxy_cannot_supply_the_scenario_pages(counter: Project, rogue: str) -> None:
    config = (
        "export default {\n  use: {\n"
        f'    proxy: {{ server: "{rogue}", bypass: "<-loopback>" }},\n'
        "  },\n};\n"
    )
    printed = check_config(counter, config)
    assert "rejected Playwright setting use.proxy" in printed
    assert Rogue.calls == []


@pytest.mark.parametrize(
    ("config", "key"),
    [
        ('use: { connectOptions: { wsEndpoint: "ws://127.0.0.1:1" } }', "use.connectOptions"),
        ('use: { extraHTTPHeaders: { "X-Alternate": "1" } }', "use.extraHTTPHeaders"),
        ('use: { serviceWorkers: "allow" }', "use.serviceWorkers"),
        ('use: { storageState: "session.json" }', "use.storageState"),
        (
            'use: { launchOptions: { args: ["--proxy-server=http://127.0.0.1:1"] } }',
            "use.launchOptions.args",
        ),
        (
            "use: { launchOptions: { ignoreDefaultArgs: true } }",
            "use.launchOptions.ignoreDefaultArgs",
        ),
        (
            'use: { launchOptions: { proxy: { server: "http://127.0.0.1:1" } } }',
            "use.launchOptions.proxy",
        ),
        ('globalSetup: "./setup.ts"', "globalSetup"),
        ('globalTeardown: "./teardown.ts"', "globalTeardown"),
        ('webServer: { command: "npm run dev", port: 3000 }', "webServer"),
        ('build: { external: ["./substitute.ts"] }', "build"),
    ],
)
def test_transport_and_setup_keys_are_blocking_findings(
    counter: Project, config: str, key: str
) -> None:
    # Prettier's formatting is part of the real gate, so format the candidate
    # with the component's own locked formatter before testing its semantics.
    counter.write("web/playwright.config.ts", f"export default {{ {config} }};\n")
    fixed = counter.quality("fix")
    assert fixed.returncode == 0, output(fixed)
    formatted = (counter.path / "web/playwright.config.ts").read_text()
    assert f"rejected Playwright setting {key}" in check_config(counter, formatted)
