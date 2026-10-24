"""FR05: the isolated production build of a browser component, with the real Vite.

Until the browser scenarios run it, these cases drive the build adapter
directly, on a component installed from the npm cache as a snapshot's is. The
packages written into `node_modules` stand for dependencies: `leaky` imports a
Node builtin and the server-only package `pg`, the CommonJS `legacy` requires
one, the `browser` field of `mapped` maps the builtin it imports away, and
`events` is an npm package named like a builtin, which resolves to a file.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from quality.adapters.typescript.build import BuildOutcome, BuildRequest, production_build
from quality.adapters.typescript.environment import npm_ci, tool_script
from quality.testkit.browserproject import (
    APP,
    FILES,
    STYLES,
    VITE,
    browser_packages,
    browser_project,
)
from quality.testkit.nodefakes import browser_component
from quality.testkit.typescriptproject import pinned_node

SETTINGS = """\
[components.browser]
public_env = { VITE_TITLE = "declared-title" }
server_modules = ["src/server/**"]
server_packages = ["pg"]
"""
LEAKY = """\
import { readFileSync } from "node:fs";
import { q } from "pg";

export const l = typeof readFileSync + q;
"""
PACKAGES: dict[str, tuple[dict[str, object], str]] = {
    "leaky": ({}, LEAKY),
    "pg": ({}, 'export const q = "pg";\n'),
    "mapped": ({"browser": {"fs": False}}, 'import fs from "fs";\n\nexport const m = typeof fs;\n'),
    "events": ({}, "export class EventEmitter {}\n"),
    "legacy": ({"type": "commonjs"}, 'module.exports = typeof require("path");\n'),
}
REACT = 'import { useState } from "react";\n'
COUNT = "        Count {count}\n"
VALUES = APP.replace(
    COUNT,
    COUNT
    + "        {import.meta.env.VITE_TITLE}\n"
    + "        {String(import.meta.env.VITE_SECRET)}\n"
    + "        {String(import.meta.env.VITE_AMBIENT)}\n",
)
CROSSING = APP.replace(
    REACT,
    'import { EventEmitter } from "events";\n'
    'import { l } from "leaky";\n'
    'import legacy from "legacy";\n'
    'import { m } from "mapped";\n' + REACT + '\nimport { rows } from "../shared/client.ts";\n',
).replace(
    COUNT, "        Count {count + rows.length + l + m + legacy + String(new EventEmitter())}\n"
)
# The shared module reaches the server module through an alias, which only Vite resolves.
ALIASED = VITE.replace(
    "export default defineConfig({ plugins: [react()] });",
    'const server = fileURLToPath(new URL("./src/server", import.meta.url));\n\n'
    "export default defineConfig({\n"
    '  plugins: [react()],\n  resolve: { alias: { "@server": server } },\n});',
).replace("import react", 'import { fileURLToPath } from "node:url";\n\nimport react')
SERVER = "web/src/server/db.ts"
SECRETS = ("local-secret", "production-secret", "ambient-value")


def install(web: Path) -> None:
    """Install the component's locked packages, then the stand-in dependencies."""
    npm_ci(pinned_node(), web, web.parent / "npm-home", label="web")
    for name, (fields, source) in PACKAGES.items():
        package = web / "node_modules" / name
        package.mkdir()
        manifest = {"name": name, "version": "1.0.0", "type": "module", "main": "index.js"}
        (package / "package.json").write_text(json.dumps({**manifest, **fields}))
        (package / "index.js").write_text(source)


@pytest.fixture(scope="module")
def web(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return an installed browser component `web` below the snapshot directory."""
    files = {
        **FILES,
        "src/server/db.ts": "export const rows = [1, 2];\n",
        "shared/client.ts": 'export { rows } from "@server/db.ts";\n',
        ".env.local": "VITE_SECRET=local-secret\n",
        ".env.production": "VITE_SECRET=production-secret\n",
        "dist/stale.txt": "stale\n",
    }
    snapshot = tmp_path_factory.mktemp("build").resolve()
    directory = browser_project(snapshot / "web", files, node=pinned_node())
    install(directory)
    return directory


def build(web: Path, run: Path, changes: Mapping[str, str] | None = None) -> BuildOutcome:
    """Write the changed files of `web` over the defaults and build it into `run`."""
    written = {"src/App.tsx": APP, "src/App.module.css": STYLES, "vite.config.ts": ALIASED}
    for path, text in {**written, **(changes or {})}.items():
        (web / path).write_text(text)
    owned = tuple(
        f"web/{path.relative_to(web).as_posix()}"
        for path in sorted(web.rglob("*"))
        if path.is_file() and "node_modules" not in path.parts
    )
    sources = frozenset(
        path for path in owned if path.startswith("web/src/") and "/server/" not in path
    )
    request = BuildRequest(
        browser_component(extra=SETTINGS), web.parent, run, owned, sources, "candidate"
    )
    script = tool_script("vite", web, web, browser_packages()["vite"])
    return production_build(pinned_node(), script, request)


def test_the_build_uses_only_the_snapshot_and_the_declared_values(
    web: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("VITE_AMBIENT", "ambient-value")
    outcome = build(web, tmp_path / "run", {"src/App.tsx": VALUES})
    assert outcome.diagnostics == []
    output = outcome.output
    assert output is not None
    built = sorted(output.files)
    assert {"index.html", "icon.svg", ".vite/manifest.json"} <= set(built)
    scripts = [path for path in built if re.fullmatch(r"assets/index-[\w-]+\.js", path)]
    styles = [path for path in built if re.fullmatch(r"assets/index-[\w-]+\.css", path)]
    assert len(scripts) == len(styles) == 1
    assert "stale.txt" not in built
    assert (web / "dist/stale.txt").read_text() == "stale\n"
    code = (output.directory / scripts[0]).read_text()
    assert "declared-title" in code
    for path in built:
        text = (output.directory / path).read_bytes()
        assert not [secret for secret in SECRETS if secret.encode() in text], path
    listing = "".join(
        f"{hashlib.sha256((output.directory / path).read_bytes()).hexdigest()}  {path}\n"
        for path in built
    )
    assert output.evidence()["digest"] == hashlib.sha256(listing.encode()).hexdigest()
    assert output.evidence()["candidate"] == "candidate"


def test_crossings_outside_the_browser_sources_are_found_in_the_module_graph(
    web: Path, tmp_path: Path
) -> None:
    outcome = build(web, tmp_path / "run", {"src/App.tsx": CROSSING})
    found = sorted((d.rule, d.location and d.location.path, d.message) for d in outcome.diagnostics)
    leaky, legacy = "web/node_modules/leaky/index.js", "web/node_modules/legacy/index.js"
    assert found == [
        (
            "typescript.boundaries",
            leaky,
            f"the production build imports the Node builtin 'node:fs', imported by {leaky}",
        ),
        (
            "typescript.boundaries",
            leaky,
            f"the production build includes the server-only package 'pg', imported by {leaky}",
        ),
        (
            "typescript.boundaries",
            legacy,
            f"the production build imports the Node builtin 'path', imported by {legacy}",
        ),
        (
            "typescript.boundaries",
            "web/shared/client.ts",
            (
                f"the production build includes the server-only module {SERVER}, "
                "imported by web/shared/client.ts"
            ),
        ),
    ]


def test_a_stylesheet_url_outside_the_build_is_found(web: Path, tmp_path: Path) -> None:
    missing = STYLES.replace("  margin: 0 auto;\n", "  background: url(/missing.png);\n")
    outcome = build(web, tmp_path / "run", {"src/App.module.css": missing})
    (found,) = outcome.diagnostics
    assert found.rule == "typescript.build-output"
    assert re.fullmatch(
        r"assets/index-[\w-]+\.css: '/missing\.png' is not a file of the build", found.message
    )


def test_a_build_error_is_a_finding(web: Path, tmp_path: Path) -> None:
    broken = APP.replace(REACT, REACT + 'import "./missing.ts";\n')
    outcome = build(web, tmp_path / "run", {"src/App.tsx": broken})
    assert outcome.output is None
    (found,) = outcome.diagnostics
    assert found.rule == "typescript.build"
    assert found.message.startswith("vite build exited with status 1: ")
    assert "missing.ts" in found.message
