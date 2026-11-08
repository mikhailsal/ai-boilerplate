"""Unrun Vitest and Playwright resource fixtures using bootstrapped dependencies."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


SHARED = r"""import { writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { join, isAbsolute } from 'node:path';
const env = process.env;
const mode = env.RL00_MODE ?? 'performance';
const size = env.RL00_SIZE ?? 'small';
const target = env.RL00_TARGET ?? '';
const mib = Number(env.RL00_ALLOC_MIB ?? '1');
const sharedMib = Number(env.RL00_SHARED_MIB ?? '64');
if (!Number.isInteger(sharedMib) || sharedMib < 0 || sharedMib > 128) throw Error('invalid shared allocation');
export const sharedAllocation = () => { const held = [allocate(sharedMib)]; if (active('retained')) { event('retained', 'retained-allocation-start'); held.push(allocate(mib)); event('retained', 'retained-allocation-end'); } return held; };
export const subjectValue = enabled => enabled ? 1 : 0;
const slowSeconds = Number(env.RL00_SLOW_SECONDS ?? '8');
if (!Number.isInteger(slowSeconds) || slowSeconds < 1 || slowSeconds > 30) throw Error('invalid slow duration');
if (!['performance', 'correctness'].includes(mode) || !['small', 'large'].includes(size) || !Number.isInteger(mib) || mib < 0 || mib > 1536) throw Error('invalid corpus');
let serial = 0;
export const active = (name) => mode === 'correctness' && target === name;
export const cases = ['ordinary', 'fixture', 'child', 'parameter-heavy', ...(size === 'large' ? ['parameter-cheap', ...Array.from({length: 11}, (_, i) => `cheap-${i}`)] : [])];
export function event(name, phase, variant = '') {
  if (env.RL00_INSTRUMENT !== '1') return;
  if (!env.RL00_EVENT_DIR || !isAbsolute(env.RL00_EVENT_DIR)) throw Error('invalid event directory');
  writeFileSync(join(env.RL00_EVENT_DIR, `node-${process.pid}-${serial++}.json`), JSON.stringify({case: name, phase, variant, target, pid: process.pid, monotonic_ns: process.hrtime.bigint().toString()}), {flag: 'wx'});
}
export function allocate(amount) {
  if (!Number.isInteger(amount) || amount < 0 || amount > 1536) throw Error('allocation bound');
  const bytes = Buffer.allocUnsafe(amount * 1048576);
  for (let i = 0; i < bytes.length; i += 4096) bytes[i] = 1;
  return bytes;
}
export async function child() {
  const python = env.RL00_CHILD_PYTHON;
  if (!python || !isAbsolute(python)) throw Error('invalid child interpreter');
  const code = 'import sys; x=bytearray(int(sys.argv[1])*1048576); x[::4096]=bytes([1])*len(x[::4096]); print("ready",flush=True); sys.stdin.buffer.read(1)';
  const proc = spawn(python, ['-c', code, String(mib)], {stdio: ['pipe', 'pipe', 'pipe']});
  await new Promise((resolve, reject) => { proc.once('error', reject); proc.stdout.once('data', resolve); proc.once('exit', code => reject(Error(`child exited ${code} before ready`))); });
  const done = new Promise((resolve, reject) => { proc.once('error', reject); proc.once('exit', code => code === 0 ? resolve() : reject(Error(`child exit ${code}`))); });
  proc.stdin.end('x');
  await done;
}
export async function work(name) {
  let held;
  if ((name === 'ordinary' && (active('native') || active('justified'))) || (name === 'parameter-heavy' && active('parameter-heavy'))) held = allocate(mib);
  if (name === 'ordinary' && active('slow')) await new Promise(resolve => setTimeout(resolve, slowSeconds * 1000));
  if (name === 'child' && active('child')) await child();
  return held;
}
export const allocation = () => allocate(mib);
"""

VITEST = r"""import { afterAll, afterEach, beforeAll, beforeEach, expect, test } from 'vitest';
import { active, sharedAllocation, allocation, cases, event, work, subjectValue } from './shared.mjs';
let shared;
let fixture;
let current;
beforeAll(() => { shared = sharedAllocation(); });
afterAll(() => { shared = undefined; });
beforeEach((context) => { current = context.task.name; event(current, 'setup'); if (current === 'fixture' && active('setup')) fixture = allocation(); });
afterEach(() => { event(current, 'teardown'); if (current === 'fixture' && active('teardown')) fixture = allocation(); fixture = undefined; });
test.each(cases)('%s', async (name) => { event(name, 'call'); fixture = await work(name); expect(subjectValue(name.length > 0)).toBe(1); expect(subjectValue(false)).toBe(0); });
"""

PLAYWRIGHT = r"""import { test, expect } from '@playwright/test';
import { createServer } from 'node:net';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { active, sharedAllocation, allocation, cases, event, work, subjectValue } from './shared.mjs';
let shared;
let fixture;
let server;
let url;
test.beforeAll(async () => {
  shared = sharedAllocation();
  const reservation = createServer();
  await new Promise(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const port = reservation.address().port;
  await new Promise(resolve => reservation.close(resolve));
  const node = process.env.RL00_NODE;
  const modules = process.env.RL00_NODE_MODULES;
  if (!node || !modules) throw Error('missing pinned Node paths');
  server = spawn(node, [modules + '/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], {cwd: process.cwd(), stdio: 'ignore'});
  url = `http://127.0.0.1:${port}/`;
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (server.exitCode !== null) throw Error('preview exited');
    try { if ((await fetch(url)).ok) return; } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  server.kill('SIGTERM');
  throw Error('preview readiness timeout');
});
test.afterAll(async () => { shared = undefined; if (server && server.exitCode === null) { const done = once(server, 'exit'); server.kill('SIGTERM'); await done; } });
test.beforeEach(async ({}, info) => { event(info.title, 'setup', info.project.name); if (info.title === 'parameter:fixture' && active('setup')) fixture = allocation(); });
test.afterEach(async ({}, info) => { event(info.title, 'teardown', info.project.name); if (info.title === 'parameter:fixture' && active('teardown')) fixture = allocation(); fixture = undefined; });
for (const name of cases) test(`parameter:${name}`, async ({page}, info) => { event(name, 'call', info.project.name); fixture = await work(name); await page.goto(url); await expect(page.locator('h1')).toHaveText('Ready'); await expect(page.locator('h1')).toHaveAttribute('data-source', 'executed'); });
"""


def _required(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value)
    if not value or not path.is_absolute() or not path.exists():
        raise ValueError(f"{name} must name an existing absolute path")
    return path


def prepare(root: Path, repo: Path, profile: str) -> None:
    """Create fixture files; the supplied modules must already be bootstrapped."""
    if profile not in ("node", "browser"):
        raise ValueError("invalid Node profile")
    root.mkdir(parents=True, exist_ok=True)
    (root / "node_modules").symlink_to(_required("RL00_NODE_MODULES"), target_is_directory=True)
    (root / "package.json").write_text(
        '{"name":"rl00bc","private":true,"type":"module"}\n', encoding="utf-8"
    )
    (root / "shared.mjs").write_text(SHARED, encoding="utf-8")
    if profile == "browser":
        (root / "index.html").write_text(
            '<!doctype html><html><head><title>RL00</title></head><body><h1>Loading</h1><script type="module" src="/src.js"></script></body></html>',
            encoding="utf-8",
        )
        (root / "src.js").write_text(
            "const heading = document.querySelector('h1');\nheading.textContent = 'Ready';\nheading.dataset.source = 'executed';\n",
            encoding="utf-8",
        )
    (root / "resource.test.mjs").write_text(
        VITEST if profile == "node" else PLAYWRIGHT, encoding="utf-8"
    )
    selector = (
        "resource.test.mjs::parameter:ordinary"
        if profile == "browser"
        else "resource.test.mjs::ordinary"
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
        raise ValueError("invalid profile or worker count")
    output.mkdir(parents=True, exist_ok=True)
    node = str(_required("RL00_NODE"))
    modules = _required("RL00_NODE_MODULES")
    if profile == "node":
        config = {
            "test": {
                "include": ["resource.test.mjs"],
                "watch": False,
                "retry": 0,
                "allowOnly": False,
                "maxWorkers": workers,
                "reporters": ["json", "junit"],
                "outputFile": {
                    "json": str(output / "vitest.json"),
                    "junit": str(output / "junit.xml"),
                },
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
            node,
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
    if coverage:
        raise ValueError("Playwright scenarios do not produce canonical unit coverage")
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
    argv = [
        node,
        str(modules / "@playwright" / "test" / "cli.js"),
        "test",
        "--config",
        str(config_path),
    ]
    if selected is not None:
        name, separator, project = selected.rpartition("[")
        if not separator or not project.endswith("]") or project[:-1] not in ("desktop", "mobile"):
            raise ValueError("browser identity must be name[viewport]")
        if not re.fullmatch(
            r"parameter:(?:ordinary|fixture|child|parameter-heavy|parameter-cheap|cheap-(?:[0-9]|10))",
            name,
        ):
            raise ValueError("unknown browser case identity")
        # Playwright greps project, file and title together; these fixtures have
        # no tags, so the title is a unique suffix. The caller still verifies
        # the complete emitted project and identity after execution.
        argv.extend(["--project", project[:-1], "--grep", f"(?:^| ){re.escape(name)}$"])
    return argv


def results(root: Path, output: Path, *, profile: str) -> list[dict[str, object]]:
    """Retain native status and every browser project; malformed output fails."""
    if profile == "node":
        report = json.loads((output / "vitest.json").read_text(encoding="utf-8"))
        cases = [
            {
                "id": case["fullName"],
                "outcome": case["status"],
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

        def visit(suite: dict[str, object]) -> None:
            for spec in suite.get("specs", []):
                for case in spec["tests"]:
                    project = case["projectName"]
                    cases.append(
                        {
                            "id": f"{spec['title']}[{project}]",
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
        raise ValueError("invalid Node profile")
    if not cases or len({str(case["id"]) for case in cases}) != len(cases):
        raise ValueError("missing or duplicate native identities")
    return cases
