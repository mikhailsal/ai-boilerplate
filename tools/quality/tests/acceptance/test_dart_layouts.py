"""R07.9 in other Dart layouts: workspaces, scripts, parts, generated code, and variants."""

from dataclasses import replace
from pathlib import Path

from quality.testkit.dartproject import lock, pubspec, workspace
from quality.testkit.policies import classification_toml
from quality.testkit.scratch import (
    Project,
    component,
    create_project,
    dart,
    output,
    rules_of,
)


def ifs(indent: str) -> str:
    """Return eleven `if` statements at `indent`: eleven decisions."""
    return "".join(
        f"{indent}if (value > {n}) {{\n{indent}  total += 1;\n{indent}}}\n" for n in range(11)
    )


# Each of the three bodies holds twelve paths; the functions around them hold one.
NESTED = (
    "int Function(int) classifier() {\n  return (int value) {\n    var total = 0;\n"
    + ifs("    ")
    + "    return total;\n  };\n}\n\n"
    "int outer(int value) {\n  int inner(int value) {\n    var total = 0;\n"
    + ifs("    ")
    + "    return total;\n  }\n\n  return inner(value);\n}\n\n"
    "bool every(List<bool> flags) =>\n" + " &&\n".join(f"    flags[{n}]" for n in range(11)) + ";\n"
)
NESTED_TEST = """\
import 'package:calc/nested.dart';
import 'package:test/test.dart';

void main() {
  test('classifier', () => expect(classifier()(20), 11));
  test('outer', () => expect(outer(20), 11));
  test('every', () => expect(every(List.filled(11, true)), isTrue));
}
"""
GREET = """\
String greet(String name) => 'hello $name';

void main(List<String> arguments) {
  print(greet(arguments.first));
}
"""
GREET_TEST = """\
import 'package:test/test.dart';

import '../bin/greet.dart' as cli;

void main() {
  test('greet', () => expect(cli.greet('dart'), 'hello dart'));
  test('main', () => cli.main(['dart']));
}
"""
FLIP = "import 'package:a/core.dart';\n\nint flip(int value) => -sign(value);\n"
FLIP_TEST = """\
import 'package:b/flip.dart';
import 'package:test/test.dart';

void main() {
  test('flip', () => expect(flip(-3), 1));
}
"""
UNCOVERED = "int unused(int value) {\n  return value + 1;\n}\n"
MODEL = """\
part 'model.g.dart';
part 'model_format.dart';

class Model {
  Model(this.value);

  final int value;

  int twice() => value * 2;
}
"""
FORMAT = """\
part of 'model.dart';

String describe(Model model) => 'model ${model.twice()}';
"""
GENERATED = (
    "// GENERATED CODE - DO NOT MODIFY BY HAND\n\npart of 'model.dart';\n\n"
    "int generated(int value) {\n  var total = 0;\n" + ifs("  ") + "  return total;\n}\n"
)
SHAPE = """\
abstract interface class Shape {
  double get area;

  String describe();
}

typedef Measure = double Function(Shape shape);
"""
MODEL_TEST = """\
import 'package:calc/src/model.dart';
import 'package:test/test.dart';

void main() {
  test('describe', () => expect(describe(Model(2)), 'model 4'));
}
"""
FLUTTER = pubspec(
    "calc", dependencies={"flutter": {"sdk": "flutter"}}, flutter={"uses-material-design": True}
)


def bootstrapped(project: Project) -> Project:
    """Install the hooks and fill the caches; return the project."""
    result = project.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return project


def test_every_workspace_package_is_tested_and_a_failure_in_the_second_blocks(
    tmp_path: Path,
) -> None:
    specs = (
        replace(dart("a"), root="packages/a"),
        replace(dart("b"), root="packages/b"),
    )
    project = create_project(tmp_path / "project", *specs)
    for name in ("a", "b"):
        project.repo.git("rm", "-q", f"packages/{name}/pubspec.lock")
        project.write(f"packages/{name}/pubspec.yaml", pubspec(name, resolution="workspace"))
    project.write("pubspec.yaml", workspace(["packages/a", "packages/b"]))
    project.write("packages/b/lib/flip.dart", FLIP)
    project.write("packages/b/test/flip_test.dart", FLIP_TEST)
    project.write(
        "packages/b/pubspec.yaml",
        pubspec("b", resolution="workspace", dependencies={"a": "any"}),
    )
    lock(project.path)
    project.repo.commit_all("one workspace with two packages")
    bootstrapped(project)
    result = project.quality("check", "--all")
    assert result.returncode == 0, output(result)
    assert "unit coverage of a: line 100.00%" in output(result)
    assert "unit coverage of b: line 100.00%" in output(result)
    project.write("packages/b/test/flip_test.dart", FLIP_TEST.replace("1));", "-1));"))
    rejected = project.commit("break a test of the second package")
    assert rejected.returncode != 0
    assert rules_of(rejected) == {"tests.failed"}, output(rejected)
    assert "[b]" in output(rejected)
    assert "[a]" not in output(rejected)


def test_closures_nested_and_expression_bodied_functions_are_measured_alone(
    calc: Project,
) -> None:
    calc.write("calc/lib/nested.dart", NESTED)
    calc.write("calc/test/nested_test.dart", NESTED_TEST)
    result = calc.commit("add nested functions")
    assert result.returncode != 0
    assert rules_of(result) == {"structure.complexity"}, output(result)
    text = output(result)
    assert "'classifier.<anonymous>' has complexity 12" in text
    assert "'outer.inner' has complexity 12" in text
    assert "'every' has complexity 11" in text
    assert "'classifier' has" not in text
    assert "'outer' has" not in text


def test_scripts_outside_lib_are_measured(tmp_path: Path) -> None:
    spec = replace(dart("calc"), source=("bin", "lib"))
    project = bootstrapped(create_project(tmp_path / "project", spec))
    project.write("calc/bin/greet.dart", GREET)
    project.write("calc/test/greet_test.dart", GREET_TEST)
    accepted = project.commit("add a script")
    assert accepted.returncode == 0, output(accepted)
    assert "unit coverage of calc: line 100.00%" in output(accepted)
    project.write("calc/bin/extra.dart", UNCOVERED)
    rejected = project.commit("add a script nothing imports")
    assert rejected.returncode != 0
    assert "coverage.new-file" in rules_of(rejected), output(rejected)
    assert "new file 'calc/bin/extra.dart' has no unit coverage" in output(rejected)


def test_parts_count_and_generated_code_and_declarations_do_not(tmp_path: Path) -> None:
    generated = classification_toml(
        "calc/lib/**/*.g.dart", "generated", "Code that build_runner writes."
    )
    spec = replace(dart("calc"), extra=generated)
    project = bootstrapped(create_project(tmp_path / "project", spec))
    project.write("calc/lib/src/model.dart", MODEL)
    project.write("calc/lib/src/model_format.dart", FORMAT)
    project.write("calc/lib/src/model.g.dart", GENERATED)
    project.write("calc/lib/src/shape.dart", SHAPE)
    project.write("calc/test/model_test.dart", MODEL_TEST)
    accepted = project.commit("add a library with parts and declarations")
    assert accepted.returncode == 0, output(accepted)
    assert "unit coverage of calc: line 100.00%" in output(accepted)
    project.write("calc/lib/src/model_format.dart", FORMAT + "\n" + UNCOVERED)
    rejected = project.commit("add uncovered code to a part")
    assert rejected.returncode != 0
    assert "coverage.changed-lines" in rules_of(rejected), output(rejected)


def test_a_flutter_package_is_an_unsupported_variant(calc: Project) -> None:
    calc.write("calc/pubspec.yaml", FLUTTER)
    result = calc.commit("turn the package into a Flutter app", "calc/pubspec.yaml")
    assert result.returncode != 0
    assert "dart.config" in rules_of(result), output(result)
    assert "Flutter" in output(result)
    assert "unit coverage of calc" not in output(result)


def test_a_browser_test_platform_is_an_unsupported_variant(calc: Project) -> None:
    calc.write("calc/dart_test.yaml", "platforms: [chrome]\n")
    result = calc.commit("run the tests in a browser", "calc/dart_test.yaml")
    assert result.returncode != 0
    assert "dart.config" in rules_of(result), output(result)
    assert "Dart VM" in output(result)


def test_a_covered_python_change_cannot_compensate_for_dart(tmp_path: Path) -> None:
    project = bootstrapped(create_project(tmp_path / "project", component("app"), dart("calc")))
    tests = project.path / "app/tests/test_app.py"
    project.write("app/tests/test_app.py", tests.read_text() + "    assert sign(0) == 1\n")
    python_only = project.commit("test the Python component more")
    assert python_only.returncode == 0, output(python_only)
    assert "unit coverage of calc" not in output(python_only)
    project.write("app/tests/test_app.py", tests.read_text() + "    assert sign(1) == 1\n")
    project.write("calc/lib/extra.dart", UNCOVERED)
    rejected = project.commit("add an uncovered Dart file")
    assert rejected.returncode != 0
    assert "coverage.new-file" in rules_of(rejected), output(rejected)
    assert "[calc]" in output(rejected)
    assert "[app]" not in output(rejected)
