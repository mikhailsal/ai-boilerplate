"""The CI wrappers of this repository: thin translators that leave every decision to the CLI."""

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
import yaml

from quality.ci.aggregate import check_required
from quality.ci.workflow import check_workflow, jobs, mapping, steps
from quality.policy import load_policy

TEMPLATE = Path(__file__).resolve().parents[4]
GITHUB = ".github/workflows/quality.yml"
GITLAB = "ci/gitlab/quality.gitlab-ci.yml"
RULESET = ".github/rulesets/main.json"
# The GitHub App ID of GitHub Actions.
GITHUB_ACTIONS = 15368
DIGEST = re.compile(r"[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}")
ENTRY_POINTS = ("./quality bootstrap", "./quality gate", "./quality audit")


def load(path: str) -> Mapping[str, object]:
    document = yaml.safe_load((TEMPLATE / path).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return cast(Mapping[str, object], document)


def lines(value: object) -> list[str]:
    return [str(line) for line in cast(list[object], value)] if isinstance(value, list) else []


def gitlab_jobs(document: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    found = {name: mapping(job) for name, job in document.items()}
    return {name: job for name, job in found.items() if job is not None and "script" in job}


def scripts(path: str) -> str:
    """Return every shell line of a wrapper: GitHub steps or GitLab scripts."""
    document = load(path)
    if path == GITHUB:
        found = [str(step.get("run", "")) for job in jobs(document).values() for step in steps(job)]
        return "\n".join(found)
    default = cast(Mapping[str, object], document["default"])
    found = lines(default.get("before_script"))
    for job in gitlab_jobs(document).values():
        found.extend(lines(job.get("script")))
    return "\n".join(found)


def test_the_github_workflow_meets_the_trust_rules_and_the_ci_policy() -> None:
    policy = load_policy(TEMPLATE)
    assert policy.policy is not None
    assert policy.policy.ci is not None
    document = load(GITHUB)
    assert list(check_workflow(GITHUB, document)) == []
    assert list(check_required(document, policy.policy.ci)) == []


@pytest.mark.parametrize("path", [GITHUB, GITLAB])
def test_both_wrappers_call_the_same_entry_points(path: str) -> None:
    text = scripts(path)
    for entry in ENTRY_POINTS:
        assert entry in text, (path, entry)
    # Each gate call names its revisions; the CLI reads no provider variable.
    assert text.count('./quality gate "$@" --reports reports') == 1


def test_the_gitlab_wrapper_has_no_optional_job_and_a_pinned_image() -> None:
    document = load(GITLAB)
    found = gitlab_jobs(document)
    assert set(found) == {"gate", "audit"}
    for job in found.values():
        assert "allow_failure" not in job
        assert "rules" not in job
        assert "when" not in job
    default = cast(dict[str, object], document["default"])
    assert DIGEST.fullmatch(str(default["image"]))


def test_the_prepared_ruleset_requires_review_and_the_aggregate_status() -> None:
    ruleset = json.loads((TEMPLATE / RULESET).read_text(encoding="utf-8"))
    policy = load_policy(TEMPLATE).policy
    assert policy is not None
    assert policy.ci is not None
    assert ruleset["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    assert ruleset["enforcement"] == "active"
    assert ruleset["bypass_actors"] == []
    rules = {rule["type"]: rule.get("parameters", {}) for rule in ruleset["rules"]}
    assert {"deletion", "non_fast_forward"} <= set(rules)
    review = rules["pull_request"]
    assert review["require_code_owner_review"] is True
    assert review["required_approving_review_count"] >= 1
    assert review["dismiss_stale_reviews_on_push"] is True
    checks = rules["required_status_checks"]
    assert checks["strict_required_status_checks_policy"] is True
    # The status must come from GitHub Actions, so no other app or user can set it.
    assert checks["required_status_checks"] == [
        {"context": policy.ci.aggregate_job, "integration_id": GITHUB_ACTIONS}
    ]
