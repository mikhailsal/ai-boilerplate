"""Native JavaScript fixtures for the bounded resource trials."""

SHARED = r"""import { writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { join, isAbsolute } from 'node:path';
const env = process.env;
const mode = env.RL00_MODE ?? 'performance';
const size = env.RL00_SIZE ?? 'small';
const target = env.RL00_TARGET ?? '';
const mib = Number(env.RL00_ALLOC_MIB ?? '1');
const sharedMib = Number(env.RL00_SHARED_MIB ?? '64');
if (!Number.isInteger(sharedMib) || sharedMib < 0 || sharedMib > 128)
  throw Error('invalid shared allocation');
export const sharedAllocation = () => {
  const held = [allocate(sharedMib)];
  if (active('retained')) {
    event('retained', 'retained-allocation-start'); held.push(allocate(mib));
    event('retained', 'retained-allocation-end');
  }
  return held;
};
export const subjectValue = enabled => enabled ? 1 : 0;
const slowSeconds = Number(env.RL00_SLOW_SECONDS ?? '8');
if (!Number.isInteger(slowSeconds) || slowSeconds < 1 || slowSeconds > 30)
  throw Error('invalid slow duration');
if (!['performance', 'correctness'].includes(mode) || !['small', 'large'].includes(size) ||
    !Number.isInteger(mib) || mib < 0 || mib > 1536) throw Error('invalid corpus');
let serial = 0;
export const active = (name) => mode === 'correctness' && target === name;
export const cases = ['ordinary', 'fixture', 'child', 'parameter-heavy',
  ...(size === 'large' ? ['parameter-cheap',
    ...Array.from({length: 11}, (_, i) => `cheap-${i}`)] : [])];
export function event(name, phase, variant = '') {
  if (env.RL00_INSTRUMENT !== '1') return;
  if (!env.RL00_EVENT_DIR || !isAbsolute(env.RL00_EVENT_DIR))
    throw Error('invalid event directory');
  writeFileSync(join(env.RL00_EVENT_DIR, `node-${process.pid}-${serial++}.json`),
    JSON.stringify({case: name, phase, variant, target, pid: process.pid,
      monotonic_ns: process.hrtime.bigint().toString()}), {flag: 'wx'});
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
  const code = 'import sys; x=bytearray(int(sys.argv[1])*1048576); ' +
    'x[::4096]=bytes([1])*len(x[::4096]); print("ready",flush=True); sys.stdin.buffer.read(1)';
  const proc = spawn(python, ['-c', code, String(mib)], {stdio: ['pipe', 'pipe', 'pipe']});
  await new Promise((resolve, reject) => {
    proc.once('error', reject); proc.stdout.once('data', resolve);
    proc.once('exit', code => reject(Error(`child exited ${code} before ready`)));
  });
  const done = new Promise((resolve, reject) => {
    proc.once('error', reject);
    proc.once('exit', code => code === 0 ? resolve() : reject(Error(`child exit ${code}`)));
  });
  proc.stdin.end('x');
  await done;
}
export async function work(name) {
  let held;
  if ((name === 'ordinary' && (active('native') || active('justified'))) ||
      (name === 'parameter-heavy' && active('parameter-heavy'))) held = allocate(mib);
  if (name === 'ordinary' && active('slow'))
    await new Promise(resolve => setTimeout(resolve, slowSeconds * 1000));
  if (name === 'child' && active('child')) await child();
  return held;
}
export const allocation = () => allocate(mib);
"""

VITEST = r"""import { afterAll, afterEach, beforeAll, beforeEach, expect, test } from 'vitest';
import { active, sharedAllocation, allocation, cases, event, work, subjectValue }
  from './shared.mjs';
let shared;
let fixture;
let current;
beforeAll(() => { shared = sharedAllocation(); });
afterAll(() => { shared = undefined; });
beforeEach((context) => {
  current = context.task.name; event(current, 'setup');
  if (current === 'fixture' && active('setup')) fixture = allocation();
});
afterEach(() => {
  event(current, 'teardown');
  if (current === 'fixture' && active('teardown')) fixture = allocation();
  fixture = undefined;
});
test.each(cases)('%s', async (name) => {
  event(name, 'call'); fixture = await work(name);
  expect(subjectValue(name.length > 0)).toBe(1); expect(subjectValue(false)).toBe(0);
});
"""

PLAYWRIGHT = r"""import { test, expect } from '@playwright/test';
import { createServer } from 'node:net';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { active, sharedAllocation, allocation, cases, event, work, subjectValue }
  from './shared.mjs';
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
  server = spawn(node, [modules + '/vite/bin/vite.js', 'preview', '--host', '127.0.0.1',
    '--port', String(port), '--strictPort'], {cwd: process.cwd(), stdio: 'ignore'});
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
test.afterAll(async () => {
  shared = undefined;
  if (server && server.exitCode === null) {
    const done = once(server, 'exit'); server.kill('SIGTERM'); await done;
  }
});
test.beforeEach(async ({}, info) => {
  event(info.title, 'setup', info.project.name);
  if (info.title === 'parameter:fixture' && active('setup')) fixture = allocation();
});
test.afterEach(async ({}, info) => {
  event(info.title, 'teardown', info.project.name);
  if (info.title === 'parameter:fixture' && active('teardown')) fixture = allocation();
  fixture = undefined;
});
for (const name of cases) test(`parameter:${name}`, async ({page}, info) => {
  event(name, 'call', info.project.name); fixture = await work(name); await page.goto(url);
  await expect(page.locator('h1')).toHaveText('Ready');
  await expect(page.locator('h1')).toHaveAttribute('data-source', 'executed');
});
"""
