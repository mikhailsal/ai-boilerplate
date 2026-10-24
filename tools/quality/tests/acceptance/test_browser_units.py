"""FR04: the jsdom unit suite of a browser component in `quality check`, with the real tools.

Each case finds exactly the findings of the unit suite and its floors. The
component's Playwright scenarios run at the merge stage, so the commit check
runs only the unit suite; Playwright Test throws when anything else calls its
`test`, so a passing case also shows that Vitest left them alone. A line is a
statement V8 reports on the original TS/TSX file: a component's `return (` is
one line, its JSX is not, and a conditional in the JSX is a branch of its own
line.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

from quality.testkit.browserproject import APP, TESTS
from quality.testkit.scratch import Project, browser, create_project, output, rules_of, typescript
from quality.testkit.typescriptproject import CORE

HOOK = """\
import { useState } from "react";

export function useCounter(limit: number) {
  const [count, setCount] = useState(0);
  function increment() {
    if (count >= limit) {
      return;
    }
    setCount(count + 1);
  }
  return { count, increment };
}
"""
# No test reaches the limit, so four of the hook's five lines run.
HOOK_TESTS = """\
import { act, renderHook } from "@testing-library/react";
import { expect, test } from "vitest";

import { useCounter } from "../src/useCounter.ts";

test("the counter counts up", () => {
  const { result } = renderHook(() => useCounter(5));
  act(() => {
    result.current.increment();
  });
  expect(result.current.count).toBe(1);
});
"""
LIMIT_TESTS = (
    HOOK_TESTS
    + """
test("the counter stops at its limit", () => {
  const { result } = renderHook(() => useCounter(0));
  act(() => {
    result.current.increment();
  });
  expect(result.current.count).toBe(0);
});
"""
)
BADGE = """\
export function Badge({ count }: { count: number }) {
  return (
    <p>
      {count > 9 ? "many" : "few"}
      {count > 99 && <strong>very many</strong>}
    </p>
  );
}
"""
# One small count takes one side of each conditional: two of four branches.
BADGE_TESTS = """\
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Badge } from "../src/Badge.tsx";

test("a small count is few", () => {
  render(<Badge count={3} />);
  expect(screen.getByText("few").tagName).toBe("P");
});
"""
ALL_BADGE_TESTS = (
    BADGE_TESTS
    + """
test("a large count is very many", () => {
  render(<Badge count={100} />);
  expect(screen.getByText("very many").tagName).toBe("STRONG");
});
"""
)
UNUSED = "export function Unused() {\n  return <p>unused</p>;\n}\n"
SILENT = """\
import { render } from "@testing-library/react";
import { test } from "vitest";

import { App } from "../src/App.tsx";

test("the page renders", () => {
  render(<App />);
});
"""
# Three lines nothing runs, committed without the hook: an existing shortfall.
LEGACY = """\
export function legacy(value: number): number {
  const doubled = value * 2;
  const shifted = doubled + 1;
  return shifted;
}
"""
TWICE = "\nexport function twice(value: number): number {\n  return value * 2;\n}\n"
REACT = 'import { useState } from "react";\n'
SHARED = APP.replace(REACT, REACT + '\nimport { twice } from "../../lib/src/core.ts";\n').replace(
    "        Count {count}\n", "        Count {twice(count) / 2}\n"
)
WEB = "unit coverage of web: "
# Each case: the changed files of `web`, the rules it adds, and a line of their output.
CASES: dict[str, tuple[Mapping[str, str], set[str], str]] = {
    "logic-hook-and-component-tests": (
        {
            "src/useCounter.ts": HOOK,
            "tests/useCounter.test.ts": LIMIT_TESTS,
            "src/Badge.tsx": BADGE,
            "tests/Badge.test.tsx": ALL_BADGE_TESTS,
        },
        set(),
        f"{WEB}line 100.00% (13/13), branch 100.00% (8/8), changed lines 100.00% (6/6)",
    ),
    "conditional-jsx-branches": (
        {"src/Badge.tsx": BADGE, "tests/Badge.test.tsx": BADGE_TESTS},
        {"coverage.branch"},
        f"{WEB}line 100.00% (8/8), branch 66.66% (4/6), changed lines 100.00% (1/1)",
    ),
    "uncovered-changed-lines": (
        {"src/useCounter.ts": HOOK, "tests/useCounter.test.ts": HOOK_TESTS},
        {"coverage.changed-lines"},
        f"{WEB}line 91.66% (11/12), branch 75.00% (3/4), changed lines 80.00% (4/5)",
    ),
    "unimported-component": (
        {"src/Unused.tsx": UNUSED},
        {"coverage.new-file", "coverage.changed-lines"},
        "new file 'web/src/Unused.tsx' has no unit coverage",
    ),
    "test-without-assertions": (
        {"tests/Render.test.tsx": SILENT},
        {"tests.failed"},
        "failed: tests/Render.test.tsx::the page renders",
    ),
}


def bootstrapped(created: Project) -> Project:
    """Bootstrap the project, which installs its hook and proves that Chromium starts."""
    result = created.quality("bootstrap")
    assert result.returncode == 0, output(result)
    assert rules_of(result) == {"typescript.browser-ready"}
    return created


def check(project: Project, files: Mapping[str, str]) -> tuple[set[str], str]:
    for path, text in files.items():
        project.write(path, text)
    project.repo.git("add", "-A")
    result = project.quality("check")
    rules = rules_of(result)
    assert result.returncode == (1 if rules else 0), output(result)
    return rules, output(result)


@pytest.fixture
def web(tmp_path: Path) -> Project:
    """Return a bootstrapped project with the browser component `web`."""
    return bootstrapped(create_project(tmp_path / "project", browser()))


@pytest.mark.parametrize("case", CASES)
def test_each_unit_floor_and_result_is_judged_alone(web: Project, case: str) -> None:
    files, added, text = CASES[case]
    rules, printed = check(web, {f"web/{path}": body for path, body in files.items()})
    assert rules == added, printed
    assert text in printed, printed


def test_the_line_floor_applies_to_unchanged_code(web: Project) -> None:
    web.write("web/src/legacy.ts", LEGACY)
    web.repo.git("add", "-A")
    web.repo.git("commit", "-q", "--no-verify", "-m", "legacy code")
    renamed = TESTS.replace("counts its clicks", "counts every click")
    rules, printed = check(web, {"web/tests/App.test.tsx": renamed})
    assert rules == {"coverage.line"}, printed
    assert f"{WEB}line 70.00% (7/10), branch 100.00% (2/2), changed lines not applicable" in printed


def test_shared_source_is_covered_only_by_its_owner(tmp_path: Path) -> None:
    owner = browser(extra='depends_on = ["lib"]')
    shared = bootstrapped(create_project(tmp_path / "project", typescript("lib"), owner))
    # Only the browser component's tests run the new function of the library.
    changes = {"lib/src/core.ts": CORE + TWICE, "web/src/App.tsx": SHARED}
    rules, printed = check(shared, changes)
    assert rules == {"coverage.line", "coverage.changed-lines"}, printed
    assert "(coverage.changed-lines) [lib]" in printed, printed
    assert (
        "unit coverage of lib: line 75.00% (3/4), branch 100.00% (2/2), changed lines 0.00% (0/1)"
    ) in printed
    assert f"{WEB}line 100.00% (7/7), branch 100.00% (2/2)" in printed
