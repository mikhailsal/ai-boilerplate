"""R08: the mandatory scenarios of the `greet` reference fixture through the real hooks.

Each test breaks one scenario of a bootstrapped project the way a change
could, and the pre-commit hook must reject it; only fresh passing results of
the mapped tests prove a scenario.
"""

from quality.testkit.greetfixture import E2E_TESTS, MANIFEST
from quality.testkit.policies import quarantine_toml
from quality.testkit.scratch import Project, output, rules_of

E2E = "greet/e2e/test_zipapp.py"
SCENARIOS = "greet/scenarios.toml"
SMOKE = "def test_the_built_archive_greets"
SMOKE_CASE = "e2e.test_zipapp::test_the_built_archive_greets"
EXPECTED = '(0, "Hello, World!\\n")'
EARTH = E2E_TESTS.replace(EXPECTED, '(0, "Hello, Earth!\\n")')
CAPABILITIES = 'capabilities = ["library", "cli"]'
EXTRA = """
[[scenarios]]
id = "usage-error"
summary = "The built zipapp refuses a blank name."
capability = "cli"
level = "e2e"
stage = "commit"
tests = ["e2e.test_zipapp::test_a_blank_name_is_refused_with_status_2"]
"""


def policy(project: Project) -> str:
    return (project.path / "quality.toml").read_text(encoding="utf-8")


def rejected(project: Project, message: str) -> tuple[set[str], str]:
    before = project.head()
    result = project.commit(message)
    assert result.returncode != 0, output(result)
    assert project.head() == before
    return rules_of(result), output(result)


def test_a_change_is_committed_when_every_scenario_passes(greet: Project) -> None:
    greet.write(E2E, E2E_TESTS.replace('"World"', '"Ada"').replace("World!", "Ada!"))
    result = greet.commit("greet Ada")
    assert result.returncode == 0, output(result)
    assert "scenarios of greet: 3 of 3 proved" in output(result)


def test_a_failing_mapped_test_rejects_the_commit(greet: Project) -> None:
    greet.write(E2E, EARTH)
    rules, text = rejected(greet, "expect another greeting")
    assert rules == {"tests.failed", "scenarios.failed"}, text
    assert f"'{SMOKE_CASE}' failed" in text


def test_a_skipped_mapped_test_does_not_prove_its_scenario(greet: Project) -> None:
    greet.write(E2E, E2E_TESTS.replace(SMOKE, '@pytest.mark.skip(reason="later")\n' + SMOKE))
    rules, text = rejected(greet, "skip the smoke test")
    assert rules == {"tests.skipped", "scenarios.skipped"}, text
    assert f"'{SMOKE_CASE}' was skipped" in text


def test_an_expected_failure_does_not_prove_its_scenario(greet: Project) -> None:
    greet.write(E2E, EARTH.replace(SMOKE, '@pytest.mark.xfail(reason="earth")\n' + SMOKE))
    rules, text = rejected(greet, "expect the smoke test to fail")
    assert rules == {"tests.skipped", "scenarios.skipped"}, text
    assert f"'{SMOKE_CASE}' was expected to fail" in text


def test_a_selection_that_drops_a_mapped_test_leaves_its_scenario_absent(greet: Project) -> None:
    settings = (greet.path / "greet" / "pyproject.toml").read_text(encoding="utf-8")
    deselect = 'pythonpath = ["src"]\naddopts = ["-k", "not greets"]'
    greet.write("greet/pyproject.toml", settings.replace('pythonpath = ["src"]', deselect))
    rules, text = rejected(greet, "deselect the smoke test")
    assert rules == {"scenarios.absent"}, text
    assert f"the e2e suite has no case '{SMOKE_CASE}'" in text


def test_a_renamed_test_leaves_its_scenario_absent(greet: Project) -> None:
    greet.write(E2E, E2E_TESTS.replace(SMOKE, "def test_the_archive_greets"))
    rules, text = rejected(greet, "rename the smoke test")
    assert rules == {"scenarios.absent"}, text
    assert "similar: 'e2e.test_zipapp::test_the_archive_greets'" in text


def test_a_declared_capability_without_scenarios_is_uncovered(greet: Project) -> None:
    widened = CAPABILITIES.replace('"cli"]', '"cli", "http-api"]')
    greet.write("quality.toml", policy(greet).replace(CAPABILITIES, widened))
    rules, text = rejected(greet, "declare an HTTP API")
    assert rules == {"scenarios.uncovered"}, text
    assert "'greet' declares 'http-api', but no scenario proves it" in text
    assert "no scenario proves 'http-api.success'" in text


def test_a_scenario_declared_twice_is_ambiguous(greet: Project) -> None:
    smoke = MANIFEST[MANIFEST.index('[[scenarios]]\nid = "archive-smoke"') :]
    greet.write(SCENARIOS, MANIFEST + "\n" + smoke)
    rules, text = rejected(greet, "declare the smoke scenario twice")
    assert rules == {"scenarios.ambiguous"}, text


def test_a_deleted_scenario_must_be_retired(greet: Project) -> None:
    greet.write(SCENARIOS, MANIFEST + EXTRA)
    added = greet.commit("add a scenario")
    assert added.returncode == 0, output(added)
    greet.write(SCENARIOS, MANIFEST)
    rules, text = rejected(greet, "delete the scenario")
    assert rules == {"scenarios.deleted"}, text
    assert "'usage-error'" in text
    retired = '\n[[retired]]\nid = "usage-error"\nreason = "archive-refusal proves it."\n'
    greet.write(SCENARIOS, MANIFEST + retired)
    result = greet.commit("retire the scenario")
    assert result.returncode == 0, output(result)


def test_a_quarantine_suspends_only_the_scenarios_it_names(greet: Project) -> None:
    base = policy(greet)
    greet.write(E2E, EARTH)
    entry = quarantine_toml(SMOKE_CASE, suite="e2e", component="greet")
    greet.write("quality.toml", base + "\n" + entry)
    rules, text = rejected(greet, "quarantine without naming the scenario")
    assert rules == {"tests.quarantined", "scenarios.quarantined"}, text
    entry = quarantine_toml(SMOKE_CASE, "archive-smoke", suite="e2e", component="greet")
    greet.write("quality.toml", base + "\n" + entry)
    result = greet.commit("quarantine the flaky smoke test")
    assert result.returncode == 0, output(result)
    assert rules_of(result) == {"tests.quarantined", "scenarios.suspended"}, output(result)
    assert "scenarios of greet: 3 of 3 proved" not in output(result)


def test_an_expired_or_unit_quarantine_is_rejected(greet: Project) -> None:
    base = policy(greet)
    greet.write(E2E, EARTH)
    expired = quarantine_toml(
        SMOKE_CASE, "archive-smoke", suite="e2e", expires="2020-01-01", component="greet"
    )
    greet.write("quality.toml", base + "\n" + expired)
    rules, text = rejected(greet, "rely on an expired quarantine")
    assert {"quarantine.expired", "tests.failed", "scenarios.failed"} <= rules, text
    unit = quarantine_toml("tests.test_greet::test_a_blank_name_is_refused", suite="unit")
    greet.write("quality.toml", base + "\n" + unit.replace('"app"', '"greet"'))
    rules, text = rejected(greet, "quarantine a unit test")
    assert "policy.conflict" in rules, text
    assert "unit tests cannot be quarantined" in text


def test_scenarios_of_the_merge_stage_wait_for_the_merge_gate(greet: Project) -> None:
    suites = 'tests = { unit = ["tests"], e2e = ["e2e"] }'
    later = 'tests = { unit = ["tests"], integration = ["integration"], e2e = ["e2e"] }'
    greet.write("quality.toml", policy(greet).replace(suites, later))
    greet.write("greet/integration/test_flow.py", "def test_flow() -> None:\n    assert False\n")
    flow = EXTRA.replace('"usage-error"', '"later-flow"').replace('"commit"', '"merge"')
    flow = flow.replace('"e2e"', '"integration"').replace(
        "e2e.test_zipapp::test_a_blank_name_is_refused_with_status_2",
        "integration.test_flow::test_flow",
    )
    greet.write(SCENARIOS, MANIFEST + flow)
    result = greet.commit("add a merge-stage scenario")
    assert result.returncode == 0, output(result)
    assert "scenarios of greet: 3 of 3 proved, 1 not required by this run" in output(result)
    merge = greet.quality("check", "--stage", "merge", "--rev", "HEAD")
    assert merge.returncode == 1, output(merge)
    assert rules_of(merge) == {"tests.failed", "scenarios.failed"}, output(merge)


def test_capabilities_are_suggested_but_never_required(greet: Project) -> None:
    greet.write("greet/src/greet/migrations/0001_create.sql", "CREATE TABLE names (name TEXT);\n")
    greet.repo.git("add", "-A")
    result = greet.quality("scenarios")
    assert result.returncode == 0, output(result)
    assert (
        "'greet' may have the 'migrations' capability: it has migrations under "
        "'src/greet/migrations'"
    ) in output(result)


def test_mutation_testing_cannot_be_enabled_and_tagged_profiles_need_a_scenario(
    greet: Project,
) -> None:
    base = policy(greet)
    greet.write(
        "quality.toml", base.replace(CAPABILITIES, CAPABILITIES + '\nenhanced = ["mutation"]')
    )
    rules, text = rejected(greet, "enable mutation testing")
    assert rules == {"scenarios.enhanced"}, text
    greet.write(
        "quality.toml", base.replace(CAPABILITIES, CAPABILITIES + '\nenhanced = ["property"]')
    )
    rules, text = rejected(greet, "enable property testing")
    assert rules == {"scenarios.uncovered"}, text
    tagged = MANIFEST.replace(
        'stage = "commit"\nrequirements = ["library.public-api"]',
        ('stage = "commit"\nenhanced = "property"\nrequirements = ["library.public-api"]'),
    )
    greet.write(SCENARIOS, tagged)
    result = greet.commit("tag the consumer scenario as a property test")
    assert result.returncode == 0, output(result)
