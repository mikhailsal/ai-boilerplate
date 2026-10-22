"""The lanes of the gate, which CI runs in separate required jobs (decision 0018).

The complete gate is both lanes. The browser lane checks the active browser
components; the main lane runs the common gates and the history checks and
checks every other component. Each component belongs to exactly one lane, so
the two results together are the complete gate, and a required workflow that
runs one lane must run the other in a required job too.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from enum import StrEnum

from quality.ci.workflow import Table, finding, steps
from quality.diagnostics import Diagnostic, Rule
from quality.policy import Component

LANES = Rule(
    id="ci.lanes",
    title="The required jobs do not run every lane of the gate",
    requirement="R09",
    explanation=(
        "`quality gate --lane main` runs the common gates and the history checks and "
        "checks every component that does not run in a browser; `--lane browser` checks "
        "the browser components. When a required job runs one lane, another required job "
        "must run the other, or a browser component could pass without its scenarios."
    ),
    remedy="Run both lanes, or the gate without --lane, in jobs of `[ci].required_jobs`.",
)
RULES = (LANES,)

# The arguments of a gate call; continuation lines are joined first.
GATE = re.compile(r"quality gate\b([^\n]*)")
LANE = re.compile(r"--lane[= ]+[\"']?([\w-]+)")


class Lane(StrEnum):
    """A part of the gate that one CI job runs."""

    MAIN = "main"
    BROWSER = "browser"


def in_lane(component: Component, lane: Lane | None) -> bool:
    """Whether a lane checks the component; the complete gate, None, checks every one."""
    return lane is None or component.in_browser is (lane is Lane.BROWSER)


def gate_lanes(script: str) -> Iterator[str | None]:
    """Yield the lane of each gate call in a shell script, None for the complete gate."""
    for call in GATE.finditer(script.replace("\\\n", " ")):
        lane = LANE.search(call.group(1))
        yield lane.group(1) if lane is not None else None


def check_lanes(path: str, required: Iterable[Table]) -> Iterator[Diagnostic]:
    """Report each lane that no required job runs while another required job runs one."""
    found: set[str | None] = set()
    for job in required:
        for step in steps(job):
            run = step.get("run")
            if isinstance(run, str):
                found.update(gate_lanes(run))
    if not found or None in found:
        return
    ran = ", ".join(sorted(lane for lane in found if lane is not None))
    for lane in Lane:
        if lane.value not in found:
            message = f"the required jobs run the gate's lane {ran} but not '{lane}'"
            yield finding(LANES, path, message, lane.value)
