from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Verdict(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


class Severity(StrEnum):
    INFO = "info"
    APPROVAL = "approval"
    BLOCK = "block"


@dataclass(frozen=True)
class ChangeIntent:
    request_id: str
    summary: str
    environment: str
    allowed_actions: frozenset[str]
    allowed_resource_types: frozenset[str]
    max_resource_changes: int
    max_deletes: int = 0
    allow_stateful_deletes: bool = False
    allow_public_ingress: bool = False
    max_monthly_cost_delta_usd: float | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ChangeIntent:
        required = (
            "request_id",
            "summary",
            "environment",
            "allowed_actions",
            "allowed_resource_types",
            "max_resource_changes",
        )
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"intent is missing required fields: {', '.join(missing)}")

        max_changes = int(data["max_resource_changes"])
        max_deletes = int(data.get("max_deletes", 0))
        if max_changes < 1:
            raise ValueError("max_resource_changes must be at least 1")
        if max_deletes < 0:
            raise ValueError("max_deletes cannot be negative")

        allowed_actions = frozenset(str(v).lower() for v in data["allowed_actions"])
        supported_actions = {"create", "update", "delete", "replace"}
        unknown_actions = allowed_actions - supported_actions
        if unknown_actions:
            raise ValueError(
                "intent contains unsupported actions: " + ", ".join(sorted(unknown_actions))
            )

        resource_types = frozenset(str(v) for v in data["allowed_resource_types"])
        if not resource_types:
            raise ValueError("allowed_resource_types cannot be empty")

        raw_cost = data.get("max_monthly_cost_delta_usd")
        max_cost = None if raw_cost is None else float(raw_cost)
        if max_cost is not None and max_cost < 0:
            raise ValueError("max_monthly_cost_delta_usd cannot be negative")

        return cls(
            request_id=str(data["request_id"]),
            summary=str(data["summary"]),
            environment=str(data["environment"]).lower(),
            allowed_actions=allowed_actions,
            allowed_resource_types=resource_types,
            max_resource_changes=max_changes,
            max_deletes=max_deletes,
            allow_stateful_deletes=bool(data.get("allow_stateful_deletes", False)),
            allow_public_ingress=bool(data.get("allow_public_ingress", False)),
            max_monthly_cost_delta_usd=max_cost,
        )


@dataclass(frozen=True)
class ResourceChange:
    address: str
    resource_type: str
    actions: tuple[str, ...]
    before: Mapping[str, Any] | None = None
    after: Mapping[str, Any] | None = None

    @property
    def effective_action(self) -> str:
        actions = set(self.actions)
        if "delete" in actions and "create" in actions:
            return "replace"
        if "delete" in actions:
            return "delete"
        if "create" in actions:
            return "create"
        if "update" in actions:
            return "update"
        return "no-op"

    @property
    def is_destructive(self) -> bool:
        return self.effective_action in {"delete", "replace"}


@dataclass(frozen=True)
class ReviewContext:
    actual_environment: str
    monthly_cost_delta_usd: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actual_environment", self.actual_environment.lower())
        if self.monthly_cost_delta_usd is not None and self.monthly_cost_delta_usd < 0:
            raise ValueError("monthly_cost_delta_usd cannot be negative")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    resource_address: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.resource_address:
            result["resource_address"] = self.resource_address
        if self.evidence:
            result["evidence"] = dict(self.evidence)
        return result


@dataclass(frozen=True)
class ReviewReport:
    request_id: str
    verdict: Verdict
    summary: str
    change_counts: Mapping[str, int]
    changed_resources: tuple[str, ...]
    findings: tuple[Finding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "verdict": self.verdict.value,
            "summary": self.summary,
            "change_counts": dict(self.change_counts),
            "changed_resources": list(self.changed_resources),
            "findings": [finding.to_dict() for finding in self.findings],
        }
