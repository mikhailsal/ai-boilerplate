from collections.abc import Mapping
from typing import cast

import pytest

from quality.ci.lanes import Lane, check_lanes, gate_lanes, in_lane
from quality.testkit.policies import ComponentSpec, browser_spec, build_policy

PATH = ".github/workflows/quality.yml"


def jobs(*scripts: str) -> list[Mapping[str, object]]:
    return [cast(Mapping[str, object], {"steps": [{"run": script}]}) for script in scripts]


def found(*scripts: str) -> list[tuple[str, str, str]]:
    return [(d.rule, d.message, str(d.data["symbol"])) for d in check_lanes(PATH, jobs(*scripts))]


def test_each_component_belongs_to_exactly_one_lane() -> None:
    policy = build_policy(ComponentSpec(id="api", root="api"), browser_spec())
    api, web = policy.components
    assert [in_lane(api, lane) for lane in (None, Lane.MAIN, Lane.BROWSER)] == [True, True, False]
    assert [in_lane(web, lane) for lane in (None, Lane.MAIN, Lane.BROWSER)] == [True, False, True]


@pytest.mark.parametrize(
    ("script", "lanes"),
    [
        ('./quality gate "$@" --lane main --reports reports', ["main"]),
        ("./quality gate --stage merge \\\n  --lane=browser", ["browser"]),
        ("./quality gate --lane 'browser'\n./quality gate --stage merge", ["browser", None]),
        ("./quality audit --rev HEAD", []),
    ],
)
def test_the_lane_of_each_gate_call_is_read(script: str, lanes: list[str | None]) -> None:
    assert list(gate_lanes(script)) == lanes


def test_both_lanes_or_the_complete_gate_cover_every_component() -> None:
    assert found("./quality gate --lane main", "./quality gate --lane browser") == []
    assert found("./quality gate --stage merge") == []
    assert found("./quality gate --lane main", "./quality gate --stage merge") == []
    assert found("./quality audit") == []


def test_a_lane_without_its_counterpart_is_reported() -> None:
    assert found("./quality gate --lane main", "./quality audit") == [
        ("ci.lanes", "the required jobs run the gate's lane main but not 'browser'", "browser")
    ]
    assert [symbol for _, _, symbol in found("./quality gate --lane browser")] == ["main"]
