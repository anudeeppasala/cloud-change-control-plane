from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cloud_guardian.models import ResourceChange


class TerraformPlanError(ValueError):
    """Raised when Terraform plan JSON is missing required structure."""


@dataclass(frozen=True)
class TerraformPlan:
    format_version: str
    terraform_version: str
    changes: tuple[ResourceChange, ...]

    @classmethod
    def from_file(cls, path: str | Path) -> TerraformPlan:
        with Path(path).open(encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TerraformPlan:
        raw_changes = data.get("resource_changes")
        if not isinstance(raw_changes, list):
            raise TerraformPlanError("plan must contain a resource_changes list")

        changes: list[ResourceChange] = []
        for index, raw in enumerate(raw_changes):
            if not isinstance(raw, Mapping):
                raise TerraformPlanError(f"resource_changes[{index}] must be an object")
            if raw.get("mode", "managed") != "managed":
                continue

            change = raw.get("change")
            if not isinstance(change, Mapping):
                raise TerraformPlanError(f"resource_changes[{index}].change must be an object")
            actions = change.get("actions")
            if not isinstance(actions, list) or not all(
                isinstance(action, str) for action in actions
            ):
                raise TerraformPlanError(
                    f"resource_changes[{index}].change.actions must be a string list"
                )

            action_set = set(actions)
            if action_set <= {"no-op", "read"}:
                continue

            address = raw.get("address")
            resource_type = raw.get("type")
            if not isinstance(address, str) or not isinstance(resource_type, str):
                raise TerraformPlanError(
                    f"resource_changes[{index}] requires address and type strings"
                )

            before = change.get("before")
            after = change.get("after")
            changes.append(
                ResourceChange(
                    address=address,
                    resource_type=resource_type,
                    actions=tuple(actions),
                    before=before if isinstance(before, Mapping) else None,
                    after=after if isinstance(after, Mapping) else None,
                )
            )

        return cls(
            format_version=str(data.get("format_version", "unknown")),
            terraform_version=str(data.get("terraform_version", "unknown")),
            changes=tuple(changes),
        )

    @property
    def change_counts(self) -> dict[str, int]:
        counts = {"create": 0, "update": 0, "delete": 0, "replace": 0}
        for change in self.changes:
            counts[change.effective_action] += 1
        counts["total"] = len(self.changes)
        return counts
