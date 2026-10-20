"""Builders for policy documents used by tests and adapter contract tests."""

from __future__ import annotations

from dataclasses import dataclass

from quality.policy import Policy, parse_policy

BASE_POLICY = """\
schema_version = 1

[repository]
mode = "{mode}"

[thresholds]
source_file_lines = {{ warning = 250, error = 400 }}
function_code_lines = {{ error = 50 }}
cyclomatic_complexity = {{ error = 10 }}
nesting_depth = {{ warning = 3, error = 4 }}
parameters = {{ warning = 5 }}
doc_page_lines = 300
doc_page_words = 2000
agents_lines = 150
agents_words = 1000
blob_bytes = 1048576

[coverage]
line = 80
branch = 70
changed_lines = 90
new_file_must_be_covered = true
"""


def _toml_list(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(f'"{value}"' for value in values) + "]"


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    """One `[[components]]` table; defaults describe a small Python library."""

    id: str = "app"
    root: str = "."
    profile: str = "python"
    role: str = "application"
    source: tuple[str, ...] = ("src",)
    unit: tuple[str, ...] = ("tests",)
    capabilities: tuple[str, ...] = ("library",)
    extra: str = ""

    def toml(self) -> str:
        """Render the component as TOML."""
        lines = [
            "[[components]]",
            f'id = "{self.id}"',
            f'role = "{self.role}"',
            f'profile = "{self.profile}"',
            f'root = "{self.root}"',
            f"source = {_toml_list(self.source)}",
            f"tests = {{ unit = {_toml_list(self.unit)} }}",
        ]
        if self.capabilities:
            lines.append(f"capabilities = {_toml_list(self.capabilities)}")
        else:
            lines.append('no_boundary_reason = "pure computation without external boundaries"')
        if self.extra:
            lines.append(self.extra.strip())
        return "\n".join(lines) + "\n"


def policy_toml(*components: ComponentSpec, mode: str = "project", extra: str = "") -> str:
    """Render a complete policy document with the template defaults."""
    specs = components or (ComponentSpec(),)
    body = [BASE_POLICY.format(mode=mode), *(spec.toml() for spec in specs)]
    if extra:
        body.append(extra.strip() + "\n")
    return "\n".join(body)


def classification_toml(pattern: str, category: str, reason: str = "test fixture") -> str:
    """Render one `[[classification]]` table."""
    lines = [f'pattern = "{pattern}"', f'category = "{category}"', f'reason = "{reason}"']
    return "\n".join(["[[classification]]", *lines]) + "\n"


def build_policy(*components: ComponentSpec, mode: str = "project", extra: str = "") -> Policy:
    """Parse a rendered policy, failing loudly when the test document is invalid."""
    result = parse_policy(policy_toml(*components, mode=mode, extra=extra).encode())
    if result.policy is None:
        msg = f"invalid test policy: {[d.message for d in result.diagnostics]}"
        raise AssertionError(msg)
    return result.policy
