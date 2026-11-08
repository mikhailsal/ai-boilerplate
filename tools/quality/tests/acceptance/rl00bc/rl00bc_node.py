"""Unrun Vitest and Playwright resource fixtures using bootstrapped dependencies."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from tests.acceptance.rl00bc import rl00bc_node_results
from tests.acceptance.rl00bc.rl00bc_child_fixture import CHILD
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_node_fixture import PLAYWRIGHT, SHARED, VITEST


def _required(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value)
    if not value or not path.is_absolute() or not path.exists():
        invalid(f"{name} must name an existing absolute path")
    return path


def prepare(root: Path, repo: Path, profile: str) -> None:
    """Create fixture files; the supplied modules must already be bootstrapped."""
    if profile not in ("node", "browser"):
        invalid("invalid Node profile")
    root.mkdir(parents=True, exist_ok=True)
    (root / "owned_child.py").write_text(CHILD, encoding="utf-8")
    (root / "node_modules").symlink_to(_required("RL00_NODE_MODULES"), target_is_directory=True)
    (root / "package.json").write_text(
        '{"name":"rl00bc","private":true,"type":"module"}\n', encoding="utf-8"
    )
    (root / "shared.mjs").write_text(SHARED, encoding="utf-8")
    if profile == "browser":
        (root / "index.html").write_text(
            "<!doctype html><html><head><title>RL00</title></head><body><h1>Loading</h1>"
            '<script type="module" src="/src.js"></script></body></html>',
            encoding="utf-8",
        )
        (root / "src.js").write_text(
            "const heading = document.querySelector('h1');\n"
            "heading.textContent = 'Ready';\nheading.dataset.source = 'executed';\n",
            encoding="utf-8",
        )
    if profile == "node":
        for part, suffix in enumerate(("a", "b")):
            (root / f"resource-{suffix}.test.mjs").write_text(
                VITEST.replace("__PART__", str(part)), encoding="utf-8"
            )
    else:
        (root / "resource.test.mjs").write_text(PLAYWRIGHT, encoding="utf-8")
    selector = (
        "resource.test.mjs::parameter:ordinary"
        if profile == "browser"
        else "resource-a.test.mjs::ordinary"
    )
    level = "e2e" if profile == "browser" else "unit"
    capability = "ui" if profile == "browser" else "library"
    boundary = 'boundary = "local Vite preview"\n' if profile == "browser" else ""
    (root / "scenarios.toml").write_text(
        'schema_version = 1\ncomponent = "rl00bc"\n[[scenarios]]\n'
        f'id = "subject-value"\nsummary = "The subject produces its expected value"\n'
        f'capability = "{capability}"\nlevel = "{level}"\nstage = "commit"\n'
        f"tests = [{json.dumps(selector)}]\n{boundary}",
        encoding="utf-8",
    )


def _vitest_command(
    root: Path, output: Path, selected: str | None, workers: int, coverage: bool
) -> list[str]:
    modules = _required("RL00_NODE_MODULES")
    config = {
        "test": {
            "include": ["resource-*.test.mjs"],
            "watch": False,
            "retry": 0,
            "allowOnly": False,
            "maxWorkers": workers,
            "pool": "forks",
            "fileParallelism": True,
            "reporters": ["json", "junit"],
            "outputFile": {"json": str(output / "vitest.json"), "junit": str(output / "junit.xml")},
            "coverage": {
                "enabled": coverage,
                "provider": "v8",
                "reporter": ["lcov"],
                "reportsDirectory": str(output / "coverage"),
                "include": ["shared.mjs"],
            },
        }
    }
    config_path = root / "vitest.config.mjs"
    config_path.write_text("export default " + json.dumps(config) + ";\n", encoding="utf-8")
    argv = [
        str(_required("RL00_NODE")),
        str(modules / "vitest" / "vitest.mjs"),
        "run",
        "--root",
        str(root),
        "--config",
        str(config_path),
    ]
    if selected is not None:
        argv.extend(["--testNamePattern", f"^{re.escape(selected)}$"])
    return argv


def _browser_config(root: Path, repo: Path, output: Path, workers: int) -> Path:
    config_path = root / "playwright.config.mjs"
    reporter_source = (
        repo / "tools/quality/src/quality/adapters/typescript/playwright.py"
    ).read_text(encoding="utf-8")
    reporter_body = reporter_source.split('REPORTER_BODY = """\\', 1)[1].split('"""', 1)[0]
    reporter_path = output / "quality-reporter.mjs"
    reporter_settings = {
        "directory": str(root),
        "output": str(output),
        "results": str(output / "quality-playwright.json"),
        "projects": ["desktop", "mobile"],
    }
    reporter_path.write_text(
        "const settings = " + json.dumps(reporter_settings) + ";\n" + reporter_body,
        encoding="utf-8",
    )
    config = {
        "testDir": str(root),
        "testMatch": "resource.test.mjs",
        "workers": workers,
        "retries": 0,
        "forbidOnly": True,
        "reporter": [
            ["json", {"outputFile": str(output / "playwright.json")}],
            [str(reporter_path)],
        ],
        "outputDir": str(output / "artifacts"),
        "use": {
            "browserName": "chromium",
            "launchOptions": {"executablePath": str(_required("RL00_CHROMIUM"))},
            "serviceWorkers": "block",
            "trace": "on",
        },
        "projects": [
            {"name": "desktop", "use": {"viewport": {"width": 1280, "height": 720}}},
            {"name": "mobile", "use": {"viewport": {"width": 390, "height": 844}}},
        ],
    }
    config_path.write_text("export default " + json.dumps(config) + ";\n", encoding="utf-8")
    return config_path


def command(
    root: Path,
    repo: Path,
    output: Path,
    selected: str | None,
    *,
    profile: str,
    workers: int,
    coverage: bool,
) -> list[str]:
    """Return native command. Caller verifies exactly one matching produced identity."""
    if profile not in ("node", "browser") or workers not in (1, 2):
        invalid("invalid profile or worker count")
    output.mkdir(parents=True, exist_ok=True)
    rl00bc_node_results.selection(output, profile, os.environ.get("RL00_SIZE", "small"), selected)
    if workers == 2 and selected is None and os.environ.get("RL00_INSTRUMENT") == "1":
        (root / "worker-sync.json").write_text("{}\n", encoding="utf-8")
    if profile == "node":
        return _vitest_command(root, output, selected, workers, coverage)
    if coverage:
        invalid("Playwright scenarios do not produce canonical unit coverage")
    config_path = _browser_config(root, repo, output, workers)
    argv = [
        str(_required("RL00_NODE")),
        str(_required("RL00_NODE_MODULES") / "@playwright" / "test" / "cli.js"),
        "test",
        "--config",
        str(config_path),
    ]
    if selected is not None:
        name, separator, project = selected.rpartition("[")
        if not separator or not project.endswith("]") or project[:-1] not in ("desktop", "mobile"):
            invalid("browser identity must be name[viewport]")
        if not re.fullmatch(
            r"parameter:(?:ordinary|fixture|child|parameter-heavy|parameter-cheap|"
            r"cheap-(?:[0-9]|10))",
            name,
        ):
            invalid("unknown browser case identity")
        # Playwright greps project, file and title together; these fixtures have
        # no tags, so the title is a unique suffix. The caller still verifies
        # the complete emitted project and identity after execution.
        argv.extend(["--project", project[:-1], "--grep", f"(?:^| ){re.escape(name)}$"])
    return argv


def results(root: Path, output: Path, *, profile: str) -> list[dict[str, object]]:
    """Retain native status and every browser project; malformed output fails."""
    if profile == "node":
        report = json.loads((output / "vitest.json").read_text(encoding="utf-8"))
        cases: list[dict[str, object]] = [
            {
                "id": case["fullName"],
                "source": suite["name"],
                "outcome": case["status"],
                "duration_ms": case.get("duration"),
                "failure_messages": case.get("failureMessages"),
                "coverage": str(output / "coverage" / "lcov.info"),
                "native_report": str(output / "vitest.json"),
                "junit": str(output / "junit.xml"),
            }
            for suite in report["testResults"]
            for case in suite["assertionResults"]
        ]
    elif profile == "browser":
        report = json.loads((output / "playwright.json").read_text(encoding="utf-8"))
        cases = []

        def visit(suite: dict[str, Any]) -> None:
            for spec in suite.get("specs", []):
                for case in spec["tests"]:
                    project = case["projectName"]
                    cases.append(
                        {
                            "id": f"{spec['title']}[{project}]",
                            "source": spec.get("file", suite.get("file")),
                            "variant": project,
                            "outcome": case["status"],
                            "native_results": case["results"],
                            "native_report": str(output / "playwright.json"),
                            "artifacts": str(output / "artifacts"),
                        }
                    )
            for child_suite in suite.get("suites", []):
                visit(child_suite)

        for suite in report["suites"]:
            visit(suite)
    else:
        invalid("invalid Node profile")
    if not cases or len({str(case["id"]) for case in cases}) != len(cases):
        invalid("missing or duplicate native identities")
    return rl00bc_node_results.reconcile(output, cases) if profile == "node" else cases
