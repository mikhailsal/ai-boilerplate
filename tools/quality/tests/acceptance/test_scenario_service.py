"""R08: the HTTP and database scenarios of the `notes` reference fixture through the hooks.

The service publishes its operations in an OpenAPI document and declares the
http-api, database, migrations, and authorization capabilities; each test
breaks one obligation and the pre-commit hook must reject the commit.
"""

from quality.testkit.notesfixture import SERVER
from quality.testkit.notestests import MANIFEST, OPENAPI
from quality.testkit.scratch import Project, output, rules_of

SCENARIOS = "notes/scenarios.toml"
WRITERS_ONLY = """\
        elif self.headers.get("X-Role") != WRITER:
            self.reply(HTTPStatus.FORBIDDEN, {"error": "only writers create notes"})
"""
TRANSACTIONS = """\
[[not_applicable]]
requirement = "database.transactions"
reason = "Every write is one statement, and each migration is one transaction."
"""
START = MANIFEST.index('[[scenarios]]\nid = "fresh-schema"')
FRESH = MANIFEST[START : MANIFEST.index("[[scenarios]]", START + 1)]


def rejected(project: Project, message: str) -> tuple[set[str], str]:
    before = project.head()
    result = project.commit(message)
    assert result.returncode != 0, output(result)
    assert project.head() == before
    return rules_of(result), output(result)


def test_the_service_commits_with_every_requirement_proved(notes: Project) -> None:
    notes.write("notes/src/notes/server.py", SERVER.replace("MAX_BODY = 4096", "MAX_BODY = 8192"))
    result = notes.commit("accept larger bodies")
    assert result.returncode == 0, output(result)
    assert "scenarios of notes: 10 of 10 proved" in output(result)


def test_an_operation_no_scenario_names_is_uncovered(notes: Project) -> None:
    delete = (
        '"delete": {"operationId": "deleteNote", "responses": {"204": {"description": "Gone"}}},'
    )
    notes.write(
        "notes/openapi.json", OPENAPI.replace('"/notes/{id}": {', '"/notes/{id}": {' + delete)
    )
    rules, text = rejected(notes, "publish a delete operation")
    assert rules == {"scenarios.uncovered"}, text
    assert "no scenario names the OpenAPI operation 'deleteNote'" in text


def test_a_scenario_cannot_name_an_unpublished_operation(notes: Project) -> None:
    notes.write(SCENARIOS, MANIFEST.replace('"getNote"]', '"getNote", "updateNote"]'))
    rules, text = rejected(notes, "claim an update operation")
    assert rules == {"scenarios.reference"}, text
    assert "'updateNote', which is not an operation of the OpenAPI document" in text


def test_a_broken_permission_check_fails_the_scenarios_it_proves(notes: Project) -> None:
    notes.write("notes/src/notes/server.py", SERVER.replace(WRITERS_ONLY, ""))
    rules, text = rejected(notes, "let readers write")
    assert rules == {"tests.failed", "scenarios.failed"}, text
    assert "scenario 'reader-refused' (http-api, integration)" in text
    assert "scenario 'writers-only' (authorization, integration)" in text


def test_an_optional_requirement_needs_a_scenario_or_a_reason(notes: Project) -> None:
    notes.write(SCENARIOS, MANIFEST.replace(TRANSACTIONS, ""))
    rules, text = rejected(notes, "drop the transactions reason")
    assert rules == {"scenarios.uncovered"}, text
    assert "no scenario proves 'database.transactions'" in text


def test_a_mandatory_requirement_cannot_be_declared_not_applicable(notes: Project) -> None:
    excused = '[[not_applicable]]\nrequirement = "migrations.fresh"\nreason = "Not needed."\n'
    notes.write(SCENARIOS, MANIFEST.replace(FRESH, "") + "\n" + excused)
    rules, text = rejected(notes, "excuse the fresh schema")
    assert rules == {"scenarios.uncovered", "scenarios.deleted"}, text
    assert "'migrations.fresh' (migrations build a fresh schema) always applies" in text


def test_a_unit_test_cannot_prove_a_database_requirement(notes: Project) -> None:
    rows = 'level = "integration"\nstage = "commit"\nrequirements = ["database.engine"'
    unit = rows.replace('"integration"', '"unit"')
    moved = MANIFEST.replace(rows, unit).replace(
        "integration.test_api::test_notes_are_rows_of_the_sqlite_file",
        "tests.test_notes::test_the_store_reads_what_it_writes",
    )
    notes.write(SCENARIOS, moved)
    rules, text = rejected(notes, "prove the database with a unit test")
    assert rules == {"scenarios.level"}, text
    assert "proves 'database.engine' with the unit suite" in text
