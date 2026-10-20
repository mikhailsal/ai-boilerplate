"""R07.9 and A02: Python and TypeScript components in one repository, each on its own."""

from pathlib import Path

from quality.testkit.scratch import CORE, component, create_project, output, rules_of, typescript
from quality.testkit.typescriptproject import CORE as TYPESCRIPT_CORE

UNCOVERED = "export function unused(value: number): number {\n  return value + 1;\n}\n"


def test_each_profile_checks_only_the_components_a_change_affects(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", component("app"), typescript("web"))
    assert project.quality("bootstrap").returncode == 0
    project.write("web/src/core.ts", "// The sign of a number.\n" + TYPESCRIPT_CORE)
    web = project.commit("document the TypeScript sign", "web/src/core.ts")
    assert web.returncode == 0, output(web)
    assert "unit coverage of web" in output(web)
    assert "unit coverage of app" not in output(web)
    project.write("app/src/app/core.py", "# The sign of a number.\n" + CORE)
    app = project.commit("document the Python sign", "app/src/app/core.py")
    assert app.returncode == 0, output(app)
    assert "unit coverage of app" in output(app)
    assert "unit coverage of web" not in output(app)


def test_a02_a_covered_python_change_cannot_compensate_for_typescript(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", component("app"), typescript("web"))
    assert project.quality("bootstrap").returncode == 0
    project.write("app/src/app/core.py", "# The sign of a number.\n" + CORE)
    project.write("web/src/extra.ts", UNCOVERED)
    result = project.commit("change both components")
    assert result.returncode != 0
    expected = {"coverage.changed-lines", "coverage.line", "coverage.new-file"}
    assert rules_of(result) == expected, output(result)
    # Pooled, the two components would cover 7 of 8 lines, above the floor of 80%.
    assert "line coverage of 'web' is 75.00% (3/4)" in output(result)
    assert "[app]" not in output(result)
    assert "unit coverage of app: line 100.00% (4/4)" in output(result)
