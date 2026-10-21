"""CI wrapper rules: workflow trust, the required aggregate job, and control-file ownership."""

from quality.adapters import actionlint
from quality.ci import aggregate, codeowners, control, verdict, workflow
from quality.ci.control import changed_control, control_files
from quality.ci.gates import ci_gates
from quality.ci.verdict import ResultsError, job_verdict, parse_results

# Rules of the gates every check runs; the verdict and control-change rules run elsewhere.
GATE_RULES = (*workflow.RULES, *aggregate.RULES, *codeowners.RULES, *actionlint.RULES)
RULES = (*GATE_RULES, *control.RULES, *verdict.RULES)

__all__ = [
    "GATE_RULES",
    "RULES",
    "ResultsError",
    "changed_control",
    "ci_gates",
    "control_files",
    "job_verdict",
    "parse_results",
]
