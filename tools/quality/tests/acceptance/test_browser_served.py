"""Each passing browser test must independently fetch the owned production document."""

import pytest

from quality.testkit.browserscenarios import SCENARIOS, SCENARIOS_FILE
from quality.testkit.scratch import Project, output, rules_of

GOTO = '  await page.goto("/");\n'
REPLACEMENT = "<main><h1>Substituted counter</h1><button>Count 0</button></main>"
SET_CONTENT = f'  await page.setContent("{REPLACEMENT}");\n'
FULFILLED = (
    '  await page.route("**/*", async (route) => {\n'
    "    const response = await route.fetch();\n"
    "    await route.fulfill({\n"
    "      response,\n"
    f'      body: "{REPLACEMENT}",\n'
    "    });\n"
    "  });\n" + GOTO
)
ACTIVATE = """\
  await expect(page.getByRole("heading", { name: "Substituted counter" })).toBeVisible();
  await page.getByRole("button").evaluate((button) => {
    button.addEventListener("click", () => {
      button.textContent = "Count 1";
    });
  });
"""


@pytest.mark.parametrize("navigation", [SET_CONTENT, FULFILLED], ids=["no-fetch", "fulfilled"])
def test_other_documents_or_copied_response_tokens_cannot_prove_a_substituted_page(
    counter: Project, navigation: str
) -> None:
    first, keyboard = SCENARIOS.rsplit(GOTO, 1)
    # The first test fetches enough owned documents to satisfy the former aggregate counter.
    changed = first.replace(GOTO, GOTO * 4) + navigation + ACTIVATE + keyboard
    counter.write(f"web/{SCENARIOS_FILE}", changed)
    fixed = counter.quality("fix")
    assert fixed.returncode == 0, output(fixed)
    counter.repo.git("add", "-A")
    try:
        result = counter.quality("check", "--stage", "merge", "--all")
    finally:
        counter.repo.git("reset", "-q", "--hard")
        counter.repo.git("clean", "-fdq")
    assert result.returncode == 1, output(result)
    assert "typescript.browser-served" in rules_of(result), output(result)
    assert "scenarios.failed" in rules_of(result), output(result)
    assert "the counter counts from the keyboard" in output(result)
    assert "passed without fetching a document from the owned server" in output(result)
    assert "runner exit status 0" in output(result)
    assert "scenarios of web: 1 of 2 proved" in output(result)
