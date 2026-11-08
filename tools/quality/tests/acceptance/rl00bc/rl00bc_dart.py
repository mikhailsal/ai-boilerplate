"""Unrun Dart VM resource experiment fixture; no installation or product integration."""

from __future__ import annotations

import os
import re
from pathlib import Path

from tests.acceptance.rl00bc import rl00bc_dart_packages, rl00bc_dart_report
from tests.acceptance.rl00bc.rl00bc_child_fixture import CHILD
from tests.acceptance.rl00bc.rl00bc_errors import invalid

DART_SOURCE = r"""import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';
import 'dart:typed_data';
import 'package:test/test.dart';
import '../lib/subject.dart';

final env = Platform.environment;
final mode = env['RL00_MODE'] ?? 'performance';
final target = env['RL00_TARGET'] ?? '';
final size = env['RL00_SIZE'] ?? 'small';
final mib = int.parse(env['RL00_ALLOC_MIB'] ?? '1');
final sharedMib = int.parse(env['RL00_SHARED_MIB'] ?? '64');
final slowSeconds = int.parse(env['RL00_SLOW_SECONDS'] ?? '8');
final clock = Stopwatch()..start();
final worker = '$pid:${Isolate.current.controlPort.hashCode}';
const part = __PART__;
final fixtureContext = part == 0 ? 'test/resource_a_test.dart' : 'test/resource_b_test.dart';
final held = <Uint8List>[];
int serial = 0;

Map<String, Object?> resourceObservation() {
  final result = <String, Object?>{
    'cgroup': null, 'cgroup_inode': null, 'memory_events_local': null,
  };
  try {
    final text = File('/proc/self/cgroup').readAsStringSync();
    result['cgroup'] = text;
    final line = text.split('\n').firstWhere((value) => value.startsWith('0::'));
    final path = '/sys/fs/cgroup${line.substring(3)}/memory.events.local';
    final counters = <String, int>{};
    for (final row in File(path).readAsLinesSync()) {
      final fields = row.trim().split(RegExp(r'\s+'));
      if (fields.length != 2) throw const FormatException('invalid counter');
      final value = int.tryParse(fields[1]);
      if (value == null || value < 0) throw const FormatException('invalid counter');
      counters[fields[0]] = value;
    }
    if (counters.isNotEmpty) result['memory_events_local'] = counters;
  } on FileSystemException {
    // Missing kernel evidence remains explicitly unavailable.
  } on FormatException {
    // Malformed counters remain explicitly unavailable.
  } on StateError {
    // A missing unified hierarchy remains explicitly unavailable.
  }
  return result;
}
void event(String name, String phase, [Map<String, Object> detail = const {}]) {
  if (env['RL00_INSTRUMENT'] != '1') return;
  final dir = env['RL00_EVENT_DIR'];
  if (dir == null || !Directory(dir).isAbsolute) throw StateError('event directory');
  File('$dir/dart-$worker-$part-${serial++}.json').writeAsStringSync(jsonEncode({
    'case': name, 'variant': name, 'target': target, 'phase': phase, 'pid': pid,
    'worker': worker, 'part': part, 'fixture_context': fixtureContext,
    'resource_observation': resourceObservation(), ...detail,
    'monotonic_us': clock.elapsedMicroseconds,
  }));
}
Future<void> workerBarrier() async {
  if (!File('worker-sync.json').existsSync()) return;
  final dir = env['RL00_EVENT_DIR'];
  if (dir == null || !Directory(dir).isAbsolute) throw StateError('worker event directory');
  final ready = File('$dir/dart-ready-$part');
  final peer = File('$dir/dart-ready-${1 - part}');
  final seen = File('$dir/dart-seen-$part');
  final peerSeen = File('$dir/dart-seen-${1 - part}');
  final deadline = DateTime.now().add(const Duration(seconds: 10));
  event('worker-$part', 'worker-ready');
  final temporary = File('${ready.path}.tmp');
  temporary.writeAsStringSync(worker);
  temporary.renameSync(ready.path);
  var peerWorker = '';
  while (peerWorker.isEmpty && DateTime.now().isBefore(deadline)) {
    if (peer.existsSync()) peerWorker = peer.readAsStringSync();
    await Future<void>.delayed(const Duration(milliseconds: 10));
  }
  if (peerWorker.isEmpty) throw StateError('worker peer readiness timeout');
  if (peerWorker == worker) throw StateError('not two native isolates');
  event('worker-$part', 'worker-peer-observed', {'peer_worker': peerWorker});
  seen.writeAsStringSync(worker);
  while (!await peerSeen.exists() && DateTime.now().isBefore(deadline)) {
    await Future<void>.delayed(const Duration(milliseconds: 10));
  }
  if (!await peerSeen.exists()) throw StateError('worker peer acknowledgment timeout');
  event('worker-$part', 'worker-overlap-complete', {'peer_worker': peerWorker});
}
Uint8List allocate(int count) {
  if (count < 0 || count > 1536) throw StateError('allocation bound');
  final data = Uint8List(count * 1024 * 1024);
  for (var i = 0; i < data.length; i += 4096) { data[i] = 1; }
  return data;
}
bool active(String label) => mode == 'correctness' && target == label;
Future<void> child() async {
  final executable = env['RL00_CHILD_PYTHON'];
  if (executable == null || !File(executable).isAbsolute) throw StateError('child interpreter');
  final process = await Process.start(executable, ['owned_child.py', '$mib']);
  final lines = StreamIterator(process.stdout.transform(utf8.decoder)
      .transform(const LineSplitter()));
  try {
    if (!await lines.moveNext() || lines.current != 'ready') throw StateError('child not ready');
    final cgroup = await File('/proc/${process.pid}/cgroup').readAsString();
    event('child case', 'child-ready', {'child_pid': process.pid, 'child_cgroup': cgroup});
    event('child case', 'child-allocation-start', {'child_pid': process.pid});
    process.stdin.write('a');
    await process.stdin.flush();
    if (!await lines.moveNext() || lines.current != 'allocated') {
      throw StateError('child allocation failed');
    }
    event('child case', 'child-allocation-end', {'child_pid': process.pid});
    process.stdin.write('x');
    await process.stdin.close();
    if (await process.exitCode != 0) throw StateError('child failed');
  } finally {
    process.kill();
    await lines.cancel();
  }
}
void main() {
  if (!['correctness', 'performance'].contains(mode) || !['small', 'large'].contains(size)) {
    throw StateError('invalid corpus mode');
  }
  if (mib < 0 || mib > 1536 || sharedMib < 0 || sharedMib > 128 ||
      slowSeconds < 1 || slowSeconds > 30) throw StateError('allocation or duration bound');
  setUpAll(() async {
    await workerBarrier();
    held.add(allocate(sharedMib));
    if (active('retained')) {
      event('retained', 'retained-allocation-start');
      held.add(allocate(mib));
      event('retained', 'retained-allocation-end');
    }
  });
  tearDownAll(held.clear);
  final cases = <String>['ordinary', 'fixture', 'child', 'parameter-heavy'];
  if (size == 'large') cases.addAll(['parameter-cheap', ...List.generate(11, (i) => 'cheap-$i')]);
  for (final entry in cases.asMap().entries.where((entry) => entry.key % 2 == part)) {
    final name = entry.value;
    group(name, () {
      Uint8List? setup;
      setUp(() {
        event('$name case', 'setup-start');
        if (name == 'fixture' && active('setup')) setup = allocate(mib);
        event('$name case', 'setup-end');
      });
      tearDown(() {
        event('$name case', 'teardown-start');
        if (name == 'fixture' && active('teardown')) setup = allocate(mib);
        setup = null;
        event('$name case', 'teardown-end');
      });
      test('case', () async {
        event('$name case', 'call-start');
        if ((name == 'ordinary' && (active('native') || active('justified'))) ||
            (name == 'parameter-heavy' && active('parameter-heavy'))) {
          setup = allocate(mib);
        }
        if (name == 'ordinary' && active('slow')) {
          await Future<void>.delayed(Duration(seconds: slowSeconds));
        }
        if (name == 'child' && active('child')) await child();
        expect(subjectValue(name.isNotEmpty), 1);
        expect(subjectValue(false), 0);
        event('$name case', 'call-end');
      });
    });
  }
}
"""


def _required(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value)
    if not value or not path.is_absolute() or not path.exists():
        invalid(f"{name} must name an existing absolute path")
    return path


def prepare(root: Path, repo: Path, profile: str) -> None:
    """Write a VM test pointing to the already installed helper dependency tree."""
    if profile != "dart":
        invalid("expected dart profile")
    root.mkdir(parents=True, exist_ok=True)
    (root / "owned_child.py").write_text(CHILD, encoding="utf-8")
    config = _required("RL00_DART_PACKAGE_CONFIG")
    rl00bc_dart_packages.prepare(repo, root, config)
    (root / "lib").mkdir(exist_ok=True)
    (root / "lib" / "subject.dart").write_text(
        "int subjectValue(bool enabled) => enabled ? 1 : 0;\n", encoding="utf-8"
    )
    (root / "test").mkdir(exist_ok=True)
    for part, suffix in enumerate(("a", "b")):
        (root / "test" / f"resource_{suffix}_test.dart").write_text(
            DART_SOURCE.replace("__PART__", str(part)), encoding="utf-8"
        )
    (root / "scenarios.toml").write_text(
        'schema_version = 1\ncomponent = "rl00bc"\n[[scenarios]]\n'
        'id = "subject-value"\nsummary = "The subject produces its expected value"\n'
        'capability = "library"\nlevel = "unit"\nstage = "commit"\n'
        'tests = ["test/resource_a_test.dart::ordinary case"]\n',
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
    """Return a native command; caller must compare selected ID with the producer output."""
    if profile != "dart" or workers not in (1, 2):
        invalid("invalid profile or workers")
    output.mkdir(parents=True, exist_ok=True)
    if workers == 2 and selected is None and os.environ.get("RL00_INSTRUMENT") == "1":
        (root / "worker-sync.json").write_text("{}\n", encoding="utf-8")
    argv = [
        str(_required("RL00_DART")),
        "test",
        "--platform",
        "vm",
        "--no-retry",
        "--concurrency",
        str(workers),
        "--reporter=failures-only",
        f"--file-reporter=json:{output / 'dart.json'}",
    ]
    if coverage:
        argv.extend(["--branch-coverage", f"--coverage={output / 'coverage'}"])
    if selected is not None:
        argv.extend(["--name", f"^{re.escape(selected)}$"])
    return [*argv, "test/resource_a_test.dart", "test/resource_b_test.dart"]


def results(root: Path, output: Path, *, profile: str) -> list[dict[str, object]]:
    """Read native JSON while preserving skipped, errored and incomplete outcomes."""
    return rl00bc_dart_report.results(root, output, profile=profile)


def partial_results(
    root: Path, output: Path, *, profile: str, kernel: dict[str, object]
) -> dict[str, object]:
    """Read surviving test starts only after an observed kernel resource stop."""
    return rl00bc_dart_report.partial(root, output, profile=profile, kernel=kernel)
