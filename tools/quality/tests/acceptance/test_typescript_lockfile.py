"""AUD-002: manifest drift is rejected by the gate and real hook before npm installs."""

import pytest

from quality.testkit.scratch import Project, output, rules_of
from quality.testkit.typescriptproject import CORE, TESTS, lock, package_json, pinned_packages


@pytest.mark.parametrize("workspace", [False, True], ids=["component", "workspace"])
def test_manifest_drift_is_a_candidate_failure_after_a_matching_offline_commit(
    web: Project, workspace: bool
) -> None:
    pins = pinned_packages()
    if workspace:
        web.write(
            "package.json",
            package_json("root", workspaces=["web"], devDependencies=pins),
        )
        (web.path / "web" / "package-lock.json").unlink()
        lock(web.path)
        bootstrapped = web.quality("bootstrap")
        assert bootstrapped.returncode == 0, output(bootstrapped)
    web.write("web/src/core.ts", CORE.replace("return 1;", "return 2;"))
    web.write("web/tests/core.test.ts", TESTS.replace("toBe(1)", "toBe(2)"))
    accepted = web.commit("accept matching manifests and their lockfile offline")
    assert accepted.returncode == 0, output(accepted)
    assert "unit coverage of web: line 100.00%" in output(accepted)
    before = web.head()
    web.write("web/package.json", package_json("web", devDependencies={**pins, "vitest": "0.0.0"}))
    web.repo.git("add", "web/package.json")
    checked = web.quality("check")
    assert checked.returncode == 1, output(checked)
    assert rules_of(checked) == {"typescript.lockfile"}, output(checked)
    assert "web/package.json" in output(checked)
    assert "requires vitest@'0.0.0'" in output(checked)
    assert "run `npm install`" in output(checked)
    assert "bootstrap" not in output(checked)
    rejected = web.git("commit", "-q", "-m", "reject manifest drift")
    assert rejected.returncode == 1, output(rejected)
    assert rules_of(rejected) == {"typescript.lockfile"}, output(rejected)
    assert web.head() == before
