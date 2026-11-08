"""Unrun Dart VM resource experiment fixture; no installation or product integration."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin

from tests.acceptance.rl00bc.rl00bc_errors import invalid

DART_SOURCE = r"""import 'dart:async';
import 'dart:convert';
import 'dart:io';
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
final held = <Uint8List>[];
int serial = 0;

void event(String name, String phase) {
  if (env['RL00_INSTRUMENT'] != '1') return;
  final dir = env['RL00_EVENT_DIR'];
  if (dir == null || !Directory(dir).isAbsolute) throw StateError('event directory');
  File('$dir/dart-$pid-${serial++}.json').writeAsStringSync(jsonEncode({
    'case': name, 'variant': target, 'phase': phase, 'pid': pid,
    'monotonic_us': clock.elapsedMicroseconds,
  }));
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
  final process = await Process.start(executable, ['-c',
    'import sys; x=bytearray(int(sys.argv[1])*1048576); '
    'x[::4096]=bytes([1])*len(x[::4096]); print("ready", flush=True); '
    'sys.stdin.buffer.read(1)', '$mib']);
  try {
    await process.stdout.transform(utf8.decoder).transform(const LineSplitter()).first;
  } finally {
    process.stdin.write('x');
    await process.stdin.close();
    if (await process.exitCode != 0) throw StateError('child failed');
  }
}
void main() {
  if (!['correctness', 'performance'].contains(mode) || !['small', 'large'].contains(size)) {
    throw StateError('invalid corpus mode');
  }
  if (mib < 0 || mib > 1536 || sharedMib < 0 || sharedMib > 128 ||
      slowSeconds < 1 || slowSeconds > 30) throw StateError('allocation or duration bound');
  setUpAll(() {
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
  for (final name in cases) {
    group(name, () {
      Uint8List? setup;
      setUp(() {
        event(name, 'setup');
        if (name == 'fixture' && active('setup')) setup = allocate(mib);
      });
      tearDown(() {
        event(name, 'teardown');
        if (name == 'fixture' && active('teardown')) setup = allocate(mib);
        setup = null;
      });
      test('case', () async {
        event(name, 'call');
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
    config = _required("RL00_DART_PACKAGE_CONFIG")
    (root / ".dart_tool").mkdir(exist_ok=True)
    package_config = json.loads(config.read_text(encoding="utf-8"))
    for package in package_config["packages"]:
        package["rootUri"] = urljoin(config.as_uri(), package["rootUri"])
    (root / ".dart_tool" / "package_config.json").write_text(
        json.dumps(package_config), encoding="utf-8"
    )
    (root / "pubspec.yaml").write_text(
        "name: rl00bc_dart\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n", encoding="utf-8"
    )
    (root / "lib").mkdir(exist_ok=True)
    (root / "lib" / "subject.dart").write_text(
        "int subjectValue(bool enabled) => enabled ? 1 : 0;\n", encoding="utf-8"
    )
    (root / "test").mkdir(exist_ok=True)
    (root / "test" / "resource_test.dart").write_text(DART_SOURCE, encoding="utf-8")
    (root / "scenarios.toml").write_text(
        'schema_version = 1\ncomponent = "rl00bc"\n[[scenarios]]\n'
        'id = "subject-value"\nsummary = "The subject produces its expected value"\n'
        'capability = "library"\nlevel = "unit"\nstage = "commit"\n'
        'tests = ["test/resource_test.dart::ordinary case"]\n',
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
    return [*argv, str(root / "test" / "resource_test.dart")]


def _visible(case: dict[str, object]) -> bool:
    return not (case.get("hidden") and case["outcome"] == "success")


def results(root: Path, output: Path, *, profile: str) -> list[dict[str, object]]:
    """Read native JSON event IDs and outcome; absent/incomplete results raise."""
    if profile != "dart":
        invalid("expected dart profile")
    tests: dict[int, dict[str, object]] = {}
    for line in (output / "dart.json").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") == "testStart":
            case = event["test"]
            tests[case["id"]] = {
                "id": case["name"],
                "native_id": case["id"],
                "outcome": None,
                "native_report": str(output / "dart.json"),
                "raw_coverage": str(output / "coverage"),
            }
        elif event.get("type") == "testDone" and event["testID"] in tests:
            tests[event["testID"]]["outcome"] = event["result"]
            tests[event["testID"]]["hidden"] = event.get("hidden") is True
    if not tests or any(case["outcome"] is None for case in tests.values()):
        invalid("missing or incomplete native Dart results")
    return [case for case in tests.values() if _visible(case)]
