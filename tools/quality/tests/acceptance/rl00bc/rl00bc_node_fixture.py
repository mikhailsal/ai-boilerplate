"""Native JavaScript fixtures for the bounded resource trials."""

SHARED = r"""import { existsSync, readFileSync, renameSync, statSync, writeFileSync }
  from 'node:fs';
import { randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { join, isAbsolute } from 'node:path';
import { createInterface } from 'node:readline';
const env = process.env;
const mode = env.RL00_MODE ?? 'performance';
const size = env.RL00_SIZE ?? 'small';
const target = env.RL00_TARGET ?? '';
const mib = Number(env.RL00_ALLOC_MIB ?? '1');
const sharedMib = Number(env.RL00_SHARED_MIB ?? '64');
if (!Number.isInteger(sharedMib) || sharedMib < 0 || sharedMib > 128)
  throw Error('invalid shared allocation');
export const sharedAllocation = fixtureContext => {
  const held = [allocate(sharedMib)];
  if (active('retained')) {
    event('retained', 'retained-allocation-start', 'retained', {fixture_context: fixtureContext});
    held.push(allocate(mib));
    event('retained', 'retained-allocation-end', 'retained', {fixture_context: fixtureContext});
  }
  return held;
};
export const subjectValue = enabled => enabled ? 1 : 0;
const slowSeconds = Number(env.RL00_SLOW_SECONDS ?? '8');
if (!Number.isInteger(slowSeconds) || slowSeconds < 1 || slowSeconds > 30)
  throw Error('invalid slow duration');
if (!['performance', 'correctness'].includes(mode) || !['small', 'large'].includes(size) ||
    !Number.isInteger(mib) || mib < 0 || mib > 1536) throw Error('invalid corpus');
export const active = (name) => mode === 'correctness' && target === name;
export const cases = ['ordinary', 'fixture', 'child', 'parameter-heavy',
  ...(size === 'large' ? ['parameter-cheap',
    ...Array.from({length: 11}, (_, i) => `cheap-${i}`)] : [])];
function resourceObservation() {
  let cgroup = null, cgroup_inode = null, memory_events_local = null;
  try {
    cgroup = readFileSync('/proc/self/cgroup', 'utf8');
    const line = cgroup.split('\n').find(value => value.startsWith('0::'));
    if (!line) throw Error('missing unified cgroup');
    const path = join('/sys/fs/cgroup', line.slice(3));
    try { cgroup_inode = statSync(path, {bigint: true}).ino.toString(); } catch {}
    const counters = {};
    for (const row of readFileSync(join(path, 'memory.events.local'), 'utf8').trim().split('\n')) {
      const [key, raw] = row.split(/\s+/); const value = Number(raw);
      if (!key || !Number.isSafeInteger(value) || value < 0) throw Error('invalid counter');
      counters[key] = value;
    }
    memory_events_local = counters;
  } catch {}
  return {cgroup, cgroup_inode, memory_events_local};
}
export function event(name, phase, variant = name, detail = {}) {
  if (env.RL00_INSTRUMENT !== '1') return;
  if (!env.RL00_EVENT_DIR || !isAbsolute(env.RL00_EVENT_DIR))
    throw Error('invalid event directory');
  writeFileSync(join(env.RL00_EVENT_DIR, `node-${process.pid}-${randomUUID()}.json`),
    JSON.stringify({case: name, phase, variant, target, pid: process.pid, ...detail,
      resource_observation: resourceObservation(),
      monotonic_ns: process.hrtime.bigint().toString()}), {flag: 'wx'});
}
export async function workerBarrier(part) {
  if (!existsSync('worker-sync.json')) return;
  const dir = env.RL00_EVENT_DIR;
  if (!dir || !isAbsolute(dir)) throw Error('invalid worker barrier directory');
  const ready = join(dir, `node-ready-${part}`);
  const peer = join(dir, `node-ready-${1 - part}`);
  const seen = join(dir, `node-seen-${part}`);
  const peerSeen = join(dir, `node-seen-${1 - part}`);
  const deadline = Date.now() + 10000;
  event(`worker-${part}`, 'worker-ready', String(part));
  writeFileSync(`${ready}.tmp`, String(process.pid), {flag: 'wx'});
  renameSync(`${ready}.tmp`, ready);
  let peerPid = 0;
  while (peerPid <= 0 && Date.now() < deadline) {
    if (existsSync(peer)) peerPid = Number(readFileSync(peer, 'utf8'));
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  if (peerPid <= 0) throw Error('worker peer readiness timeout');
  if (!Number.isInteger(peerPid) || peerPid === process.pid)
    throw Error('not two worker processes');
  event(`worker-${part}`, 'worker-peer-observed', String(part), {peer_pid: peerPid});
  writeFileSync(seen, String(process.pid), {flag: 'wx'});
  while (!existsSync(peerSeen) && Date.now() < deadline)
    await new Promise(resolve => setTimeout(resolve, 10));
  if (!existsSync(peerSeen)) throw Error('worker peer acknowledgment timeout');
  event(`worker-${part}`, 'worker-overlap-complete', String(part), {peer_pid: peerPid});
}
export function allocate(amount) {
  if (!Number.isInteger(amount) || amount < 0 || amount > 1536) throw Error('allocation bound');
  const bytes = Buffer.allocUnsafe(amount * 1048576);
  for (let i = 0; i < bytes.length; i += 4096) bytes[i] = 1;
  return bytes;
}
export async function child(caseId, variant, fixtureContext) {
  const python = env.RL00_CHILD_PYTHON;
  if (!python || !isAbsolute(python)) throw Error('invalid child interpreter');
  const proc = spawn(python, ['owned_child.py', String(mib)], {stdio: ['pipe', 'pipe', 'pipe']});
  if (!proc.pid) throw Error('child did not start');
  const lines = createInterface({input: proc.stdout})[Symbol.asyncIterator]();
  const done = new Promise(resolve => {
    proc.once('error', error => resolve(error));
    proc.once('exit', code => resolve(code));
  });
  try {
    if ((await lines.next()).value !== 'ready') throw Error('child readiness failed');
    const cgroup = readFileSync(`/proc/${proc.pid}/cgroup`, 'utf8');
    const native = {native_name: caseId, native_project: variant === caseId ? null : variant,
      fixture_context: fixtureContext};
    event(caseId, 'child-ready', variant, {...native, child_pid: proc.pid, child_cgroup: cgroup});
    event(caseId, 'child-allocation-start', variant, {...native, child_pid: proc.pid});
    proc.stdin.write('a');
    if ((await lines.next()).value !== 'allocated') throw Error('child allocation failed');
    event(caseId, 'child-allocation-end', variant, {...native, child_pid: proc.pid});
    proc.stdin.end('x');
    const status = await done;
    if (status !== 0) throw Error(`child exit ${status}`);
  } finally {
    if (proc.exitCode === null) proc.kill('SIGKILL');
  }
}
export async function work(name, caseId = name, variant = caseId, fixtureContext = null) {
  let held;
  if ((name === 'ordinary' && (active('native') || active('justified'))) ||
      (name === 'parameter-heavy' && active('parameter-heavy'))) held = allocate(mib);
  if (name === 'ordinary' && active('slow'))
    await new Promise(resolve => setTimeout(resolve, slowSeconds * 1000));
  if (name === 'child' && active('child')) await child(caseId, variant, fixtureContext);
  return held;
}
export const allocation = () => allocate(mib);
"""

VITEST = r"""import { afterAll, afterEach, beforeAll, beforeEach, expect, test } from 'vitest';
import { active, sharedAllocation, allocation, cases, event, work, subjectValue, workerBarrier }
  from './shared.mjs';
const part = __PART__;
const fixtureContext = `node:${import.meta.url}`;
let shared;
let fixture;
let current;
beforeAll(async () => { await workerBarrier(part); shared = sharedAllocation(fixtureContext); });
afterAll(() => { shared = undefined; });
beforeEach((context) => {
  current = context.task.name;
  event(current, 'setup-start', current,
    {native_name: current, native_project: null, fixture_context: fixtureContext});
  if (current === 'fixture' && active('setup')) fixture = allocation();
  event(current, 'setup-end', current,
    {native_name: current, native_project: null, fixture_context: fixtureContext});
});
afterEach(() => {
  event(current, 'teardown-start', current,
    {native_name: current, native_project: null, fixture_context: fixtureContext});
  if (current === 'fixture' && active('teardown')) fixture = allocation();
  fixture = undefined;
  event(current, 'teardown-end', current,
    {native_name: current, native_project: null, fixture_context: fixtureContext});
});
test.each(cases.filter((_, index) => index % 2 === part))('%s', async (name) => {
  event(current, 'call-start', current,
    {native_name: current, native_project: null, fixture_context: fixtureContext});
  fixture = await work(name, current, current, fixtureContext);
  expect(subjectValue(name.length > 0)).toBe(1); expect(subjectValue(false)).toBe(0);
  event(current, 'call-end', current,
    {native_name: current, native_project: null, fixture_context: fixtureContext});
});
"""

PLAYWRIGHT = r"""import { test, expect } from '@playwright/test';
import { createServer } from 'node:net';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { active, sharedAllocation, allocation, cases, event, work, subjectValue, workerBarrier }
  from './shared.mjs';
let shared;
let fixture;
let server;
let url;
const fixtureContext = project => `browser:${project}:${import.meta.url}`;
test.beforeAll(async ({}, workerInfo) => {
  await workerBarrier(workerInfo.project.name === 'desktop' ? 0 : 1);
  shared = sharedAllocation(fixtureContext(workerInfo.project.name));
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
  event(info.title, 'setup-start', info.project.name,
    {native_name: info.title, native_project: info.project.name,
      fixture_context: fixtureContext(info.project.name)});
  if (info.title === 'parameter:fixture' && active('setup')) fixture = allocation();
  event(info.title, 'setup-end', info.project.name,
    {native_name: info.title, native_project: info.project.name,
      fixture_context: fixtureContext(info.project.name)});
});
test.afterEach(async ({}, info) => {
  event(info.title, 'teardown-start', info.project.name,
    {native_name: info.title, native_project: info.project.name,
      fixture_context: fixtureContext(info.project.name)});
  if (info.title === 'parameter:fixture' && active('teardown')) fixture = allocation();
  fixture = undefined;
  event(info.title, 'teardown-end', info.project.name,
    {native_name: info.title, native_project: info.project.name,
      fixture_context: fixtureContext(info.project.name)});
});
for (const name of cases) test(`parameter:${name}`, async ({page}, info) => {
  event(info.title, 'call-start', info.project.name,
    {native_name: info.title, native_project: info.project.name,
      fixture_context: fixtureContext(info.project.name)});
  fixture = await work(name, info.title, info.project.name, fixtureContext(info.project.name));
  await page.goto(url);
  await expect(page.locator('h1')).toHaveText('Ready');
  await expect(page.locator('h1')).toHaveAttribute('data-source', 'executed');
  event(info.title, 'call-end', info.project.name,
    {native_name: info.title, native_project: info.project.name,
      fixture_context: fixtureContext(info.project.name)});
});
"""
