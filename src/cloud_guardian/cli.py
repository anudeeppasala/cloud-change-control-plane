from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from cloud_guardian.engine import review_plan
from cloud_guardian.models import ChangeIntent, ReviewContext, ReviewReport, Verdict
from cloud_guardian.policies import PolicyConfig
from cloud_guardian.terraform_plan import TerraformPlan

EXIT_CODES = {
    Verdict.ALLOW: 0,
    Verdict.REQUIRE_APPROVAL: 2,
    Verdict.BLOCK: 3,
}


def _load_intent(path: str | Path) -> ChangeIntent:
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("intent must be a JSON object")
    return ChangeIntent.from_dict(data)


def _render_human(report: ReviewReport) -> str:
    lines = [
        f"{report.verdict.value.upper()}  {report.request_id}",
        report.summary,
        (
            "Changes: "
            + ", ".join(f"{name}={count}" for name, count in report.change_counts.items())
        ),
        "Findings:",
    ]
    for finding in report.findings:
        location = f" ({finding.resource_address})" if finding.resource_address else ""
        lines.append(
            f"  [{finding.severity.value.upper()}] {finding.code}{location}: {finding.message}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloud-guardian",
        description="Compare a Terraform plan with an approved change intent.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    review = subparsers.add_parser("review", help="review a Terraform plan JSON file")
    review.add_argument("--intent", required=True, help="approved change intent JSON")
    review.add_argument("--plan", required=True, help="terraform show -json output")
    review.add_argument(
        "--environment",
        help="actual target environment; defaults to the approved environment",
    )
    review.add_argument(
        "--cost-delta",
        type=float,
        help="estimated monthly cost increase in USD",
    )
    review.add_argument("--policy", help="optional policy configuration JSON")
    review.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    review.add_argument("--output", help="write the JSON report to this file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        intent = _load_intent(args.intent)
        plan = TerraformPlan.from_file(args.plan)
        context = ReviewContext(
            actual_environment=args.environment or intent.environment,
            monthly_cost_delta_usd=args.cost_delta,
        )
        policy = PolicyConfig.from_file(args.policy) if args.policy else None
        report = review_plan(intent, plan, context, policy)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 1

    serialized = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized if args.json else _render_human(report))
    return EXIT_CODES[report.verdict]


if __name__ == "__main__":
    raise SystemExit(main())
