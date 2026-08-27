from __future__ import annotations

import json
from pathlib import Path

from cloud_guardian.engine import review_plan
from cloud_guardian.models import ChangeIntent, ReviewContext, Verdict
from cloud_guardian.terraform_plan import TerraformPlan

ROOT = Path(__file__).parents[1]


def load_intent(name: str) -> ChangeIntent:
    data = json.loads((ROOT / "examples" / "intents" / name).read_text())
    return ChangeIntent.from_dict(data)


def load_plan(name: str) -> TerraformPlan:
    return TerraformPlan.from_file(ROOT / "examples" / "plans" / name)


def finding_codes(report: object) -> set[str]:
    return {finding.code for finding in report.findings}  # type: ignore[attr-defined]


def test_safe_plan_is_allowed() -> None:
    report = review_plan(
        load_intent("safe-change.json"),
        load_plan("safe-plan.json"),
        ReviewContext("dev", monthly_cost_delta_usd=1.25),
    )
    assert report.verdict is Verdict.ALLOW
    assert finding_codes(report) == {"WITHIN_APPROVED_SCOPE"}


def test_dangerous_plan_is_blocked_for_multiple_independent_reasons() -> None:
    report = review_plan(
        load_intent("safe-change.json"),
        load_plan("dangerous-plan.json"),
        ReviewContext("production", monthly_cost_delta_usd=120.0),
    )
    codes = finding_codes(report)
    assert report.verdict is Verdict.BLOCK
    assert {
        "ENVIRONMENT_MISMATCH",
        "CHANGE_COUNT_EXCEEDED",
        "DELETE_COUNT_EXCEEDED",
        "PUBLIC_NETWORK_EXPOSURE",
        "WILDCARD_IAM_PERMISSION",
        "STATEFUL_RESOURCE_DELETION",
        "COST_LIMIT_EXCEEDED",
    } <= codes


def test_non_stateful_replacement_requires_human_approval() -> None:
    report = review_plan(
        load_intent("replacement-change.json"),
        load_plan("replacement-plan.json"),
        ReviewContext("dev", monthly_cost_delta_usd=0.5),
    )
    assert report.verdict is Verdict.REQUIRE_APPROVAL
    assert "RESOURCE_REPLACEMENT" in finding_codes(report)


def test_report_is_strictly_serializable_without_cost_data() -> None:
    report = review_plan(
        load_intent("safe-change.json"),
        load_plan("safe-plan.json"),
        ReviewContext("dev", monthly_cost_delta_usd=None),
    )
    encoded = json.dumps(report.to_dict(), allow_nan=False)
    assert report.verdict is Verdict.ALLOW
    assert "Infinity" not in encoded
