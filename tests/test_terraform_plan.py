from __future__ import annotations

import pytest

from cloud_guardian.terraform_plan import TerraformPlan, TerraformPlanError


def test_parses_managed_changes_and_ignores_noop_and_data_resources() -> None:
    plan = TerraformPlan.from_dict(
        {
            "format_version": "1.2",
            "terraform_version": "1.10.5",
            "resource_changes": [
                {
                    "address": "aws_s3_bucket.assets",
                    "mode": "managed",
                    "type": "aws_s3_bucket",
                    "change": {"actions": ["create"], "before": None, "after": {}},
                },
                {
                    "address": "aws_s3_bucket.existing",
                    "mode": "managed",
                    "type": "aws_s3_bucket",
                    "change": {"actions": ["no-op"], "before": {}, "after": {}},
                },
                {
                    "address": "data.aws_caller_identity.current",
                    "mode": "data",
                    "type": "aws_caller_identity",
                    "change": {"actions": ["read"], "before": None, "after": {}},
                },
            ],
        }
    )

    assert [change.address for change in plan.changes] == ["aws_s3_bucket.assets"]
    assert plan.change_counts == {
        "create": 1,
        "update": 0,
        "delete": 0,
        "replace": 0,
        "total": 1,
    }


def test_detects_replacement_action() -> None:
    plan = TerraformPlan.from_dict(
        {
            "resource_changes": [
                {
                    "address": "aws_lambda_function.api",
                    "type": "aws_lambda_function",
                    "change": {"actions": ["delete", "create"]},
                }
            ]
        }
    )
    assert plan.changes[0].effective_action == "replace"
    assert plan.changes[0].is_destructive is True


def test_rejects_invalid_plan_shape() -> None:
    with pytest.raises(TerraformPlanError, match="resource_changes"):
        TerraformPlan.from_dict({"format_version": "1.2"})
