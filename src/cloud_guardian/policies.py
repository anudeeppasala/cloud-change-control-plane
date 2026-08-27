from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cloud_guardian.models import (
    ChangeIntent,
    Finding,
    ResourceChange,
    ReviewContext,
    Severity,
)
from cloud_guardian.terraform_plan import TerraformPlan

DEFAULT_STATEFUL_RESOURCE_TYPES = frozenset(
    {
        "aws_db_instance",
        "aws_rds_cluster",
        "aws_dynamodb_table",
        "aws_s3_bucket",
        "aws_efs_file_system",
        "aws_elasticache_cluster",
        "aws_opensearch_domain",
        "aws_msk_cluster",
    }
)

IAM_RESOURCE_TYPES = frozenset(
    {
        "aws_iam_policy",
        "aws_iam_role_policy",
        "aws_iam_user_policy",
        "aws_iam_group_policy",
    }
)

PUBLIC_CIDRS = frozenset({"0.0.0.0/0", "::/0"})


@dataclass(frozen=True)
class PolicyConfig:
    stateful_resource_types: frozenset[str] = DEFAULT_STATEFUL_RESOURCE_TYPES
    block_public_ingress: bool = True
    block_wildcard_iam: bool = True

    @classmethod
    def from_file(cls, path: str | Path) -> PolicyConfig:
        with Path(path).open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, Mapping):
            raise ValueError("policy configuration must be a JSON object")
        return cls(
            stateful_resource_types=frozenset(
                str(value)
                for value in data.get("stateful_resource_types", DEFAULT_STATEFUL_RESOURCE_TYPES)
            ),
            block_public_ingress=bool(data.get("block_public_ingress", True)),
            block_wildcard_iam=bool(data.get("block_wildcard_iam", True)),
        )


def _walk_values(value: Any) -> Iterable[Any]:
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _walk_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_values(nested)
    else:
        yield value


def _contains_public_cidr(change: ResourceChange) -> bool:
    return any(value in PUBLIC_CIDRS for value in _walk_values(change.after or {}))


def _decoded_json_values(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            yield json.loads(value)
        except json.JSONDecodeError:
            return


def _contains_wildcard_iam(change: ResourceChange) -> bool:
    for raw in _walk_values(change.after or {}):
        for value in _decoded_json_values(raw):
            if isinstance(value, Mapping):
                for nested in _walk_values(value):
                    if nested == "*":
                        return True
            elif value == "*":
                return True
    return False


def evaluate_policies(
    intent: ChangeIntent,
    plan: TerraformPlan,
    context: ReviewContext,
    config: PolicyConfig,
) -> tuple[Finding, ...]:
    findings: list[Finding] = []

    if intent.environment != context.actual_environment:
        findings.append(
            Finding(
                code="ENVIRONMENT_MISMATCH",
                severity=Severity.BLOCK,
                message=(
                    f"approved environment is {intent.environment!r}, but the plan "
                    f"targets {context.actual_environment!r}"
                ),
            )
        )

    if len(plan.changes) > intent.max_resource_changes:
        findings.append(
            Finding(
                code="CHANGE_COUNT_EXCEEDED",
                severity=Severity.BLOCK,
                message=(
                    f"plan changes {len(plan.changes)} resources; approval allows "
                    f"at most {intent.max_resource_changes}"
                ),
                evidence={
                    "actual": len(plan.changes),
                    "allowed": intent.max_resource_changes,
                },
            )
        )

    delete_count = sum(
        1 for change in plan.changes if change.effective_action in {"delete", "replace"}
    )
    if delete_count > intent.max_deletes:
        findings.append(
            Finding(
                code="DELETE_COUNT_EXCEEDED",
                severity=Severity.BLOCK,
                message=(
                    f"plan contains {delete_count} destructive changes; approval "
                    f"allows at most {intent.max_deletes}"
                ),
                evidence={"actual": delete_count, "allowed": intent.max_deletes},
            )
        )

    for change in plan.changes:
        action = change.effective_action
        if action not in intent.allowed_actions:
            findings.append(
                Finding(
                    code="ACTION_OUTSIDE_INTENT",
                    severity=Severity.BLOCK,
                    message=f"{action} is not an approved action",
                    resource_address=change.address,
                    evidence={"action": action},
                )
            )

        if (
            "*" not in intent.allowed_resource_types
            and change.resource_type not in intent.allowed_resource_types
        ):
            findings.append(
                Finding(
                    code="RESOURCE_TYPE_OUTSIDE_INTENT",
                    severity=Severity.BLOCK,
                    message=f"{change.resource_type} is not an approved resource type",
                    resource_address=change.address,
                    evidence={"resource_type": change.resource_type},
                )
            )

        if (
            change.is_destructive
            and change.resource_type in config.stateful_resource_types
            and not intent.allow_stateful_deletes
        ):
            findings.append(
                Finding(
                    code="STATEFUL_RESOURCE_DELETION",
                    severity=Severity.BLOCK,
                    message="destructive change to a stateful resource requires explicit approval",
                    resource_address=change.address,
                    evidence={"resource_type": change.resource_type, "action": action},
                )
            )

        if action == "replace" and change.resource_type not in config.stateful_resource_types:
            findings.append(
                Finding(
                    code="RESOURCE_REPLACEMENT",
                    severity=Severity.APPROVAL,
                    message="resource replacement requires a human checkpoint",
                    resource_address=change.address,
                )
            )

        if (
            config.block_public_ingress
            and not intent.allow_public_ingress
            and _contains_public_cidr(change)
        ):
            findings.append(
                Finding(
                    code="PUBLIC_NETWORK_EXPOSURE",
                    severity=Severity.BLOCK,
                    message="plan exposes a resource to a public CIDR",
                    resource_address=change.address,
                    evidence={"public_cidrs": sorted(PUBLIC_CIDRS)},
                )
            )

        if (
            config.block_wildcard_iam
            and change.resource_type in IAM_RESOURCE_TYPES
            and _contains_wildcard_iam(change)
        ):
            findings.append(
                Finding(
                    code="WILDCARD_IAM_PERMISSION",
                    severity=Severity.BLOCK,
                    message="IAM policy contains a wildcard action or resource",
                    resource_address=change.address,
                )
            )

    if (
        intent.max_monthly_cost_delta_usd is not None
        and context.monthly_cost_delta_usd is not None
        and context.monthly_cost_delta_usd > intent.max_monthly_cost_delta_usd
    ):
        findings.append(
            Finding(
                code="COST_LIMIT_EXCEEDED",
                severity=Severity.BLOCK,
                message=(
                    f"estimated monthly increase ${context.monthly_cost_delta_usd:.2f} "
                    f"exceeds approved ${intent.max_monthly_cost_delta_usd:.2f}"
                ),
            )
        )

    return tuple(findings)
