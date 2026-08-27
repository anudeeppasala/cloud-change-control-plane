# Threat Model

## Protected assets

- Production infrastructure.
- Terraform state and plan artifacts.
- IAM policies and deployment credentials.
- Human approvals and their audit trail.
- Policy bundles and decision reports.

## Trust boundaries

| Boundary | Risk | Control |
| --- | --- | --- |
| Change request to intent JSON | Approval may be broadened | Schema validation, review ownership, signed artifact planned |
| Terraform plan to reviewer | Plan may be replaced after review | Bind report to plan hash and commit SHA in V0.2 |
| Reviewer to deployment | A blocked plan may still be applied | CI branch protection and environment approval planned |
| GitHub to AWS | Credential theft | OIDC and short-lived scoped roles planned |
| AI explanation layer | Prompt injection or unsafe advice | AI cannot set or override the verdict |

## Current controls

- Strict input validation.
- No execution of Terraform or shell content from the plan.
- Deterministic enforcement policies.
- Stable non-zero exit codes for approval and block outcomes.
- Machine-readable evidence for CI or external audit systems.
- Tests for allow, approval, and multiple blocking scenarios.

## Known V0.1 limitations

- Plan artifacts are not yet cryptographically bound to commit SHA.
- IAM analysis recognizes wildcard values but is not yet a full IAM semantic
  analyzer.
- Network analysis detects public CIDRs but does not yet model transitive paths.
- Cost is supplied as trusted context until Infracost ingestion is implemented.
- Policy bundles are local JSON/Python rather than signed OPA bundles.

## Safety principle

When the system is uncertain, it may request approval or block. It must never
silently convert uncertainty into permission.
