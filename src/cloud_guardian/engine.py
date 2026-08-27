from __future__ import annotations

from cloud_guardian.models import (
    ChangeIntent,
    Finding,
    ReviewContext,
    ReviewReport,
    Severity,
    Verdict,
)
from cloud_guardian.policies import PolicyConfig, evaluate_policies
from cloud_guardian.terraform_plan import TerraformPlan


def _final_verdict(findings: tuple[Finding, ...]) -> Verdict:
    if any(finding.severity is Severity.BLOCK for finding in findings):
        return Verdict.BLOCK
    if any(finding.severity is Severity.APPROVAL for finding in findings):
        return Verdict.REQUIRE_APPROVAL
    return Verdict.ALLOW


def review_plan(
    intent: ChangeIntent,
    plan: TerraformPlan,
    context: ReviewContext,
    policy: PolicyConfig | None = None,
) -> ReviewReport:
    policy_config = policy or PolicyConfig()
    findings = evaluate_policies(intent, plan, context, policy_config)
    verdict = _final_verdict(findings)

    if not findings:
        findings = (
            Finding(
                code="WITHIN_APPROVED_SCOPE",
                severity=Severity.INFO,
                message="plan stays within the approved intent and policy boundaries",
            ),
        )

    return ReviewReport(
        request_id=intent.request_id,
        verdict=verdict,
        summary=intent.summary,
        change_counts=plan.change_counts,
        changed_resources=tuple(change.address for change in plan.changes),
        findings=findings,
    )
