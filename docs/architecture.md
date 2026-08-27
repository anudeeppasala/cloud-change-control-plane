# Architecture

## Goal

Prevent an infrastructure deployment when its real effect exceeds the approved
change request.

## Data flow

1. A human or ticketing system produces a bounded change intent.
2. Terraform creates a binary plan.
3. `terraform show -json` converts the plan to reviewable JSON.
4. Cloud Guardian parses managed resource changes and ignores reads/no-ops.
5. Domain policies compare the plan against the intent and inspect exact cloud
   risks that should not be delegated to an LLM.
6. The engine selects the most restrictive verdict.
7. Human and JSON reports are emitted with evidence and CI exit codes.

## Component responsibilities

| Component | Responsibility |
| --- | --- |
| `terraform_plan.py` | Validate and normalize Terraform plan JSON |
| `policies.py` | Enforce exact environment, action, resource, IAM, network, state, and cost rules |
| `engine.py` | Reduce policy findings to the most restrictive verdict |
| `cli.py` | Provide human/JSON output and stable CI exit codes |

## Decision precedence

`BLOCK` outranks `REQUIRE_APPROVAL`, which outranks `ALLOW`.

One permissive signal can never override a blocking signal. This property is
important when independent policy engines are added later.

## What the policies check

Blast-radius questions bound the plan against the approved request:

- Does the plan change more resources than were approved?
- Does it destroy more than the approved number of resources?
- Does it cost more than the approved monthly increase?

Domain questions catch exact cloud hazards:

- Does the plan contain public network exposure?
- Does IAM contain a wildcard?
- Is a stateful database being destroyed?
- Is the target environment different?

Every rule is a pure function of the intent, the plan, and the review context,
so a given input always produces the same verdict.

## Planned AWS architecture

The cloud phase will keep enforcement stateless and inexpensive:

- Lambda runs the review engine.
- S3 stores immutable plan and decision evidence.
- DynamoDB indexes decisions by request and commit.
- EventBridge publishes decision events.
- CloudWatch records latency, verdict counts, and failures.
- GitHub authenticates through OIDC without long-lived AWS credentials.

The planned cloud layer is not part of V0.1 and must not be represented as
already deployed.
