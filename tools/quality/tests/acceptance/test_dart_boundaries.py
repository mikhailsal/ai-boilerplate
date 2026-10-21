"""R04.7 and R06.9 in a Dart component: declared layers and a loopback-only suite.

The unit suite needs the VM service on loopback to collect coverage; the gate
runs it in a network namespace where loopback is the only interface.
"""

from dataclasses import replace
from pathlib import Path

from quality.process.isolation import unavailable
from quality.testkit.scratch import Project, create_project, dart, output, rules_of

# Two layers: the user interface may import the core, never the reverse.
ARCHITECTURE = """
[components.architecture]
layers = ["ui", "core"]

[[components.architecture.modules]]
name = "ui"
paths = ["lib/src/ui/**"]

[[components.architecture.modules]]
name = "core"
paths = ["lib/src/core/**"]
"""
MATH = "int triple(int value) {\n  return value * 3;\n}\n"
LABEL = """\
import 'package:calc/src/core/math.dart';

String label(int value) => 'x${triple(value)}';
"""
LABEL_TEST = """\
import 'package:calc/src/ui/label.dart';
import 'package:test/test.dart';

void main() {
  test('label', () => expect(label(2), 'x6'));
}
"""
# Loopback answers inside the unit suite's namespace; any other address is
# unreachable (errno 101) rather than merely slow.
NETWORK_TEST = """\
import 'dart:io';

import 'package:test/test.dart';

void main() {
  test('loopback answers', () async {
    final server = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
    final client = await Socket.connect(
      InternetAddress.loopbackIPv4,
      server.port,
    );
    await client.close();
    await server.close();
  });
  test('other addresses are unreachable', () async {
    try {
      await Socket.connect('192.0.2.1', 9, timeout: const Duration(seconds: 5));
      fail('connected to 192.0.2.1');
    } on SocketException catch (error) {
      expect(error.osError?.errorCode, 101);
    }
  });
}
"""
PREFIX = "const prefix = 'x';\n"
UPWARD = "import '../ui/prefix.dart';\n\n" + MATH.replace(
    "  return value * 3;", "  return prefix.length * value * 3;"
)


def test_imports_between_declared_modules_follow_the_layers(tmp_path: Path) -> None:
    spec = replace(dart("calc"), extra=ARCHITECTURE)
    calc = create_project(tmp_path / "project", spec)
    assert calc.quality("bootstrap").returncode == 0
    calc.write("calc/lib/src/core/math.dart", MATH)
    calc.write("calc/lib/src/ui/label.dart", LABEL)
    calc.write("calc/test/label_test.dart", LABEL_TEST)
    accepted = calc.commit("the interface imports the core")
    assert accepted.returncode == 0, output(accepted)
    calc.write("calc/lib/src/ui/prefix.dart", PREFIX)
    calc.write("calc/lib/src/core/math.dart", UPWARD)
    rejected = calc.commit("the core imports the interface")
    assert rejected.returncode != 0
    assert "architecture.forbidden-dependency" in rules_of(rejected), output(rejected)
    assert "calc/lib/src/core/math.dart" in output(rejected)


def test_unit_tests_keep_the_vm_service_on_loopback_and_reach_nothing_else(
    calc: Project,
) -> None:
    calc.write("calc/test/network_test.dart", NETWORK_TEST)
    result = calc.commit("test the network")
    reason = unavailable()
    if reason is None:
        assert result.returncode == 0, output(result)
        assert "unit coverage of calc: line 100.00%" in output(result)
    else:
        assert result.returncode != 0
        assert "tests.network" in rules_of(result), output(result)
        assert reason in output(result)
