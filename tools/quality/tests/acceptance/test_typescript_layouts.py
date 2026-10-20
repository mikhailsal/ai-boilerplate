"""R07.4: TypeScript layouts the profile measures from their original sources."""

import json
from pathlib import Path

from quality.testkit.policies import ComponentSpec, classification_toml
from quality.testkit.scratch import Project, create_project, output, rules_of, typescript
from quality.testkit.typescriptproject import (
    COMPILER_OPTIONS,
    CORE,
    TSCONFIG,
    lock,
    package_json,
    pinned_packages,
)

FIRST = "export const first = <T,>(items: readonly T[]): T | undefined => items[0];\n"
DOUBLE = "export function double(value: number): number {\n  return value * 2;\n}\n"
EVERY_EXTENSION = {
    "web/src/view.tsx": FIRST,
    "web/src/util.mts": DOUBLE,
    "web/src/legacy.cts": "export function half(value: number): number {\n  return value / 2;\n}\n",
    "web/tests/core.test.ts": """\
import { expect, test } from "vitest";

import { sign } from "../src/core.ts";
import { half } from "../src/legacy.cts";
import { double } from "../src/util.mts";
import { first } from "../src/view.tsx";

test("every extension", () => {
  expect(sign(-1)).toBe(-1);
  expect(sign(1)).toBe(1);
  expect(double(2)).toBe(4);
  expect(half(4)).toBe(2);
  expect(first([3])).toBe(3);
});
""",
}
UNCOVERED = "export function unused(value: number): number {\n  return value + 1;\n}\n"
EMITTED = {
    "web/dist/core.js": CORE.replace("(value: number): number", "(value)"),
    "web/dist/core.d.ts": "export declare function sign(value: number): number;\n",
    "web/tests/built.test.ts": """\
import { expect, test } from "vitest";

import { sign } from "../dist/core.js";

test("the emitted module runs", () => {
  expect(sign(-2)).toBe(-1);
});
""",
}
SHARED: dict[str, object] = {
    "target": "es2024",
    "module": "nodenext",
    "moduleResolution": "nodenext",
    "strict": True,
    "skipLibCheck": True,
    "paths": {"@lib/*": ["./src/lib/*"]},
}
LIBRARY: dict[str, object] = {**SHARED, "composite": True, "rootDir": "src", "outDir": "dist"}
TESTING: dict[str, object] = {**SHARED, "noEmit": True, "allowImportingTsExtensions": True}
REFERENCES: dict[str, dict[str, object]] = {
    "web/tsconfig.json": {
        "files": [],
        "references": [{"path": "./tsconfig.lib.json"}, {"path": "./tsconfig.test.json"}],
    },
    "web/tsconfig.lib.json": {"compilerOptions": LIBRARY, "include": ["src"]},
    "web/tsconfig.test.json": {
        "compilerOptions": TESTING,
        "include": ["tests"],
        "references": [{"path": "./tsconfig.lib.json"}],
    },
}
REFERENCED_SOURCES = {
    "web/src/lib/math.ts": DOUBLE,
    "web/src/core.ts": """\
import { double } from "@lib/math.js";

export function quadruple(value: number): number {
  return double(double(value));
}
""",
    "web/tests/core.test.ts": """\
import { expect, test } from "vitest";

import { quadruple } from "../src/core.ts";
import { double } from "@lib/math.ts";

test("quadruple", () => {
  expect(quadruple(1)).toBe(4);
  expect(double(2)).toBe(4);
});
""",
}
FLIP = """\
import { sign } from "a";

export function flip(value: number): number {
  return -sign(value);
}
"""
FLIP_TEST = """\
import { expect, test } from "vitest";

import { flip } from "../src/core.ts";

test("flip", () => {
  expect(flip(2)).toBe(-1);
});
"""


def bootstrapped(project: Project) -> Project:
    result = project.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return project


def write_all(project: Project, files: dict[str, str]) -> None:
    for path, text in files.items():
        project.write(path, text)


def test_every_extension_is_measured_from_its_source(tmp_path: Path) -> None:
    web = bootstrapped(create_project(tmp_path / "project", typescript("web")))
    write_all(web, EVERY_EXTENSION)
    # The compiler resolves `.tsx` modules only when JSX is configured.
    options = {**COMPILER_OPTIONS, "jsx": "preserve"}
    web.write("web/tsconfig.json", json.dumps({**TSCONFIG, "compilerOptions": options}, indent=2))
    accepted = web.commit("add .tsx, .mts, and .cts modules")
    assert accepted.returncode == 0, output(accepted)
    assert "unit coverage of web: line 100.00%" in output(accepted)
    for suffix in ("tsx", "mts", "cts"):
        web.write(f"web/src/extra.{suffix}", UNCOVERED)
    rejected = web.commit("add unimported modules")
    assert rejected.returncode != 0
    assert "coverage.new-file" in rules_of(rejected), output(rejected)
    for suffix in ("tsx", "mts", "cts"):
        assert f"new file 'web/src/extra.{suffix}' has no unit coverage" in output(rejected)


def test_emitted_output_is_not_measured(tmp_path: Path) -> None:
    web = create_project(tmp_path / "project", typescript("web"))
    policy = (web.path / "quality.toml").read_text()
    web.write(
        "quality.toml", policy + classification_toml("web/dist/**", "generated", "Compiler output.")
    )
    write_all(web, EMITTED)
    web.repo.commit_all("commit compiler output")
    bootstrapped(web)
    web.write("web/src/core.ts", "// The sign of a number.\n" + CORE)
    result = web.commit("document sign", "web/src/core.ts")
    assert result.returncode == 0, output(result)
    # The emitted copy runs in a test but only the three lines of the source are counted.
    assert "unit coverage of web: line 100.00% (3/3)" in output(result)


def test_aliases_and_project_references_are_followed(tmp_path: Path) -> None:
    web = create_project(tmp_path / "project", typescript("web"))
    for path, document in REFERENCES.items():
        web.write(path, json.dumps(document, indent=2) + "\n")
    write_all(web, REFERENCED_SOURCES)
    web.repo.commit_all("split the sources and tests into referenced projects")
    bootstrapped(web)
    web.write(
        "web/src/core.ts", "// Four times a number.\n" + REFERENCED_SOURCES["web/src/core.ts"]
    )
    accepted = web.commit("document quadruple", "web/src/core.ts")
    assert accepted.returncode == 0, output(accepted)
    assert "unit coverage of web: line 100.00%" in output(accepted)
    math = REFERENCED_SOURCES["web/src/lib/math.ts"] + "\nexport const zero: string = 0;\n"
    web.write("web/src/lib/math.ts", math)
    rejected = web.commit("add a type error to the referenced project")
    assert rejected.returncode != 0
    # The referenced sources have no branches to measure, which is only reported.
    expected = {"typescript.types", "coverage.not-applicable"}
    assert rules_of(rejected) == expected, output(rejected)
    assert "web/src/lib/math.ts" in output(rejected)


def test_es_module_and_commonjs_components(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", typescript("esm"), typescript("cjs"))
    project.write(
        "cjs/package.json", package_json("cjs", module=False, devDependencies=pinned_packages())
    )
    project.repo.git("mv", "cjs/eslint.config.js", "cjs/eslint.config.mjs")
    project.write(
        "esm/src/legacy.cts",
        "export function half(value: number): number {\n  return value / 2;\n}\n",
    )
    project.write(
        "cjs/src/modern.mts",
        "export function triple(value: number): number {\n  return value * 3;\n}\n",
    )
    for name, module, function, call in (
        ("esm", "legacy.cts", "half", "half(4)).toBe(2"),
        ("cjs", "modern.mts", "triple", "triple(1)).toBe(3"),
    ):
        test = (project.path / name / "tests" / "core.test.ts").read_text()
        test = test.replace(
            'from "../src/core.ts";\n',
            f'from "../src/core.ts";\nimport {{ {function} }} from "../src/{module}";\n',
        )
        project.write(
            f"{name}/tests/core.test.ts", test.replace("});\n", f"  expect({call});\n}});\n")
        )
    project.repo.commit_all("one ES module and one CommonJS package")
    bootstrapped(project)
    result = project.quality("check", "--all")
    assert result.returncode == 0, output(result)
    assert "unit coverage of esm: line 100.00%" in output(result)
    assert "unit coverage of cjs: line 100.00%" in output(result)


def test_workspace_packages_are_separate_components(tmp_path: Path) -> None:
    specs = (
        ComponentSpec(id="a", root="packages/a", profile="typescript"),
        ComponentSpec(id="b", root="packages/b", profile="typescript"),
    )
    project = create_project(tmp_path / "project", *specs)
    for name in ("a", "b"):
        project.repo.git("rm", "-q", f"packages/{name}/package-lock.json")
    project.write(
        "package.json",
        package_json("workspace", workspaces=["packages/*"], devDependencies=pinned_packages()),
    )
    project.write("packages/a/package.json", package_json("a", exports="./src/core.ts"))
    project.write("packages/b/package.json", package_json("b", dependencies={"a": "0.0.0"}))
    project.write("packages/b/src/core.ts", FLIP)
    project.write("packages/b/tests/core.test.ts", FLIP_TEST)
    lock(project.path)
    project.repo.commit_all("one workspace with two packages")
    bootstrapped(project)
    result = project.quality("check", "--all")
    assert result.returncode == 0, output(result)
    assert "unit coverage of a: line 100.00%" in output(result)
    assert "unit coverage of b: line 100.00%" in output(result)
    project.write(
        "packages/b/src/extra.ts",
        "export function unused(value: number): number {\n  return value + 1;\n}\n",
    )
    rejected = project.commit("add an uncovered file to b")
    assert rejected.returncode != 0
    assert {"coverage.new-file", "coverage.line"} <= rules_of(rejected), output(rejected)
    assert "[a]" not in output(rejected)
    assert "[b]" in output(rejected)
    assert "unit coverage of a" not in output(rejected)
