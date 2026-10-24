"""FR03: the static gates of a browser component, run by `quality check` with the real tools.

A clean component passes. Each case finds exactly the finding of one gate,
and its unit suite still passes.
"""

import hashlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from quality.testkit.browserproject import APP, ESLINT, ICON, INDEX, STYLES, TESTS
from quality.testkit.scratch import Project, browser, create_project, output, rules_of

SERVER = '[components.browser]\nserver_modules = ["src/server/**"]'
DATABASE = "export interface Row {\n  id: number;\n}\n\nexport const rows: Row[] = [];\n"
STATE = "  const [count, setCount] = useState(0);\n"
HEADING = "      <h1>Counter</h1>\n"
COUNT = "        Count {count}\n"
STYLE_IMPORT = 'import styles from "./App.module.css";\n'
# One line, so the return nothing runs leaves no changed line uncovered.
CONDITIONAL = APP.replace(STATE, "  if (Math.random() > 1) return null;\n" + STATE)
IMAGE = APP.replace(HEADING, HEADING + '      <img src="/icon.svg" />\n')
SERVER_IMPORT = APP.replace(
    STYLE_IMPORT, STYLE_IMPORT + 'import { rows } from "./server/db.ts";\n'
).replace(COUNT, "        Count {count + rows.length}\n")
TYPE_IMPORT = APP.replace(
    STYLE_IMPORT, STYLE_IMPORT + 'import type { Row } from "./server/db.ts";\n'
).replace(STATE, STATE.replace("useState(0)", 'useState<Row["id"]>(0)'))
BUILTIN = APP.replace(
    'import { useState } from "react";\n',
    'import { sep } from "node:path";\nimport { useState } from "react";\n',
).replace(HEADING, HEADING + "      <p>{sep}</p>\n")
WRONG_TYPE = APP.replace(HEADING, HEADING.replace("Counter", "{title}")).replace(
    "export function App() {\n", 'const title: number = "Counter";\n\nexport function App() {\n'
)
UNKNOWN = STYLES.replace("  margin: 0 auto;\n", "  colr: red;\n  margin: 0 auto;\n")
DISABLED = STYLES.replace(
    "  margin: 0 auto;\n",
    "  /* stylelint-disable-next-line property-no-unknown */\n  colr: red;\n  margin: 0 auto;\n",
)
UNFORMATTED = "error: the file is not formatted"
# Built at run time, so no secret is ever committed.
TOKEN = "ghp" + "_" + hashlib.sha256(b"browser").hexdigest()[:36]
# Assets keep the blob limit of `quality.toml`, 1048576 bytes in the scratch policy.
LARGE = f"<!-- {'0' * (1048600 - len(ICON) - 10)} -->\n{ICON}"
# Each case: the changed files of `web`, the rules it adds, and a line of their output.
CASES: dict[str, tuple[Mapping[str, str], set[str], str]] = {
    "hooks-rules-disabled": (
        {"eslint.config.js": ESLINT.replace("  reactHooks.configs.flat.recommended,\n", "")},
        {"typescript.lint"},
        "requires react-hooks/rules-of-hooks, react-hooks/exhaustive-deps, which ESLint does not",
    ),
    "conditional-hook": (
        {"src/App.tsx": CONDITIONAL},
        {"typescript.lint"},
        "react-hooks/rules-of-hooks: React Hook",
    ),
    "image-without-text": (
        {"src/App.tsx": IMAGE},
        {"typescript.lint"},
        "jsx-a11y-x/alt-text: ",
    ),
    # The assertion runs before the click, so the test fails as well.
    "unawaited-interaction": (
        {"tests/App.test.tsx": TESTS.replace("  await userEvent", "  userEvent")},
        {"typescript.lint", "tests.failed"},
        "@typescript-eslint/no-floating-promises: ",
    ),
    "transpilable-type-error": (
        {"src/App.tsx": WRONG_TYPE},
        {"typescript.types"},
        "Type 'string' is not assignable to type 'number'",
    ),
    "server-module": (
        {"src/App.tsx": SERVER_IMPORT},
        {"typescript.boundaries"},
        "browser code imports the server-only module web/src/server/db.ts",
    ),
    # The page has no Node types, so the compiler rejects the import as well.
    "node-builtin": (
        {"src/App.tsx": BUILTIN},
        {"typescript.boundaries", "typescript.types"},
        "browser code imports the Node builtin 'node:path'",
    ),
    "unknown-property": (
        {"src/App.module.css": UNKNOWN},
        {"typescript.styles"},
        'web/src/App.module.css:2:3: error: Unknown property "colr" (property-no-unknown)',
    ),
    "disabled-stylesheet-rule": (
        {"src/App.module.css": DISABLED},
        {"suppressions.inline"},
        "inline suppression 'stylelint-disable-next-line property-no-unknown' needs",
    ),
    "unformatted-stylesheet": (
        {"src/App.module.css": STYLES.replace("  margin", "    margin")},
        {"typescript.format"},
        f"web/src/App.module.css: {UNFORMATTED}",
    ),
    "unformatted-entry": (
        {"index.html": INDEX.replace("<title>", "<title>  ")},
        {"typescript.format"},
        f"web/index.html: {UNFORMATTED}",
    ),
    "sass": (
        {"src/theme.scss": ".page {\n  color: red;\n}\n"},
        {"typescript.styles"},
        "web/src/theme.scss: error: Sass is not supported in a browser component",
    ),
    "secret-in-stylesheet": (
        {"src/App.module.css": f"{STYLES}\n/* {TOKEN} */\n"},
        {"secrets.detected"},
        "web/src/App.module.css:6:",
    ),
    "oversized-asset": (
        {"public/large.svg": LARGE},
        {"files.blob-size"},
        "web/public/large.svg: error: blob is 1048600 bytes; the limit is 1048576 bytes",
    ),
    "missing-script": (
        {"index.html": INDEX.replace("/src/main.tsx", "/src/missing.tsx")},
        {"typescript.entries"},
        "'/src/missing.tsx' does not resolve to a file of the component",
    ),
}


@pytest.fixture
def web(tmp_path: Path) -> Project:
    """Return a bootstrapped project with the browser component `web` and a server module."""
    created = create_project(tmp_path / "project", browser(extra=SERVER))
    created.write("web/src/server/db.ts", DATABASE)
    created.repo.commit_all("add the server module")
    result = created.quality("bootstrap")
    assert result.returncode == 0, output(result)
    assert rules_of(result) == {"typescript.browser-ready"}
    return created


def check(project: Project, files: Mapping[str, str]) -> tuple[set[str], str]:
    for path, text in files.items():
        project.write(f"web/{path}", text)
    project.repo.git("add", "-A")
    result = project.quality("check")
    rules = rules_of(result)
    assert result.returncode == (1 if rules else 0), output(result)
    return rules, output(result)


def test_a_clean_browser_component_passes(web: Project) -> None:
    rules, printed = check(web, {"src/App.tsx": TYPE_IMPORT})
    assert rules == set(), printed
    assert "PASSED: 0 error(s), 0 warning(s)" in printed, printed


@pytest.mark.parametrize("case", CASES)
def test_each_static_gate_rejects_its_finding(web: Project, case: str) -> None:
    files, added, text = CASES[case]
    rules, printed = check(web, files)
    assert rules == added, printed
    assert text in printed, printed


def test_fix_formats_the_stylesheets_and_the_entry_point(web: Project) -> None:
    web.write("web/src/App.module.css", STYLES.replace("  margin", "    margin"))
    web.write("web/index.html", INDEX.replace("<title>", "<title>  "))
    result = web.quality("fix")
    assert result.returncode == 0, output(result)
    assert (web.path / "web/src/App.module.css").read_text() == STYLES
    assert (web.path / "web/index.html").read_text() == INDEX
