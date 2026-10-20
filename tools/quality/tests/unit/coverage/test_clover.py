import re
from pathlib import Path

import pytest

from quality.boundedio import ReportError
from quality.coverage import Counter, CoverageReport, FileCoverage, parse_clover

SAMPLES = Path(__file__).parent / "samples"
ROOT = Path("/work/snapshot")
METRICS = '<metrics conditionals="2" coveredconditionals="1" statements="2" coveredstatements="1"/>'


def parse(data: str | bytes, *, measured: bool = True) -> CoverageReport:
    raw = data.encode() if isinstance(data, str) else data
    return parse_clover(raw, "clover.xml", root=ROOT, cwd=ROOT, branches_measured=measured)


def clover(*files: str) -> str:
    return f'<coverage><project><package name="p">{"".join(files)}</package></project></coverage>'


def file(body: str, name: str = "src/a.php") -> str:
    return f'<file name="{name}">{body}</file>'


LINES = '<line num="3" type="stmt" count="2"/><line num="4" type="stmt" count="0"/>'


def test_a_sample_in_phpunit_clover_shape_is_normalized() -> None:
    # Hand-made in the shape of PHPUnit's Clover writer: class metrics, method lines,
    # files in and outside packages. Real PHPUnit output is tested with the PHP profile.
    report = parse((SAMPLES / "phpunit-shape.clover.xml").read_bytes())
    assert report.branches_measured
    assert dict(report.files) == {
        "src/Calc.php": FileCoverage(
            "src/Calc.php", frozenset({9, 10, 15, 16, 18}), frozenset({9, 10, 15}), Counter(3, 4)
        ),
        "src/helpers.php": FileCoverage(
            "src/helpers.php", frozenset({5}), frozenset(), Counter(0, 0)
        ),
    }


def test_the_adapter_states_whether_branches_were_measured() -> None:
    report = parse(clover(file(LINES + METRICS)), measured=False)
    assert not report.branches_measured
    assert report.files["src/a.php"].lines == Counter(1, 2)


def test_non_statement_lines_are_ignored() -> None:
    method = '<line num="2" type="method" name="f" count="0"/><line num="9" type="cond" count="1"/>'
    report = parse(clover(file(method + LINES + METRICS)))
    assert report.files["src/a.php"].executable == frozenset({3, 4})


def fails(data: str, message: str) -> None:
    with pytest.raises(ReportError, match=f"^{re.escape(message)}$"):
        parse(data)


@pytest.mark.parametrize(
    "data", ["<report/>", "<coverage/>", "<project><file/></project>"], ids=str
)
def test_documents_that_are_not_clover_are_rejected(data: str) -> None:
    fails(data, "clover.xml: not a Clover report (<coverage><project>)")


def test_files_need_names_and_appear_once() -> None:
    fails(clover('<file name="">' + METRICS + "</file>"), "clover.xml: <file> without a name")
    twice = clover(file(LINES + METRICS), file(LINES + METRICS, f"{ROOT}/src/a.php"))
    fails(twice, "clover.xml: src/a.php is reported twice")
    fails(
        clover(file(METRICS, "/elsewhere/a.php")),
        "report names a file outside the snapshot: /elsewhere/a.php",
    )


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        (LINES, "<file> has no <metrics>"),
        (
            LINES + METRICS.replace('statements="2"', 'statements="3"'),
            "statement metrics disagree with the <line> records",
        ),
        (
            LINES + METRICS.replace('coveredstatements="1"', 'coveredstatements="2"'),
            "statement metrics disagree with the <line> records",
        ),
        (
            LINES + METRICS.replace('coveredconditionals="1"', 'coveredconditionals="3"'),
            "more covered conditionals than conditionals",
        ),
        (
            LINES + METRICS.replace(' conditionals="2"', ""),
            "<metrics> needs a non-negative integer 'conditionals'",
        ),
        (
            LINES + METRICS.replace('statements="2"', 'statements="-2"'),
            "<metrics> needs a non-negative integer 'statements'",
        ),
        (
            '<line num="x" type="stmt" count="1"/>' + METRICS,
            "<line> needs a non-negative integer 'num'",
        ),
        ('<line num="3" type="stmt"/>' + METRICS, "<line> needs a non-negative integer 'count'"),
        (
            '<line num="0" type="stmt" count="1"/>' + METRICS,
            "statement line 0 is invalid or repeated",
        ),
        (
            LINES + '<line num="3" type="stmt" count="1"/>' + METRICS,
            "statement line 3 is invalid or repeated",
        ),
    ],
)
def test_inconsistent_files_are_rejected(body: str, problem: str) -> None:
    fails(clover(file(body)), f"clover.xml [src/a.php]: {problem}")
