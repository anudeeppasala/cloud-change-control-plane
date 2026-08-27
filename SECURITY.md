# Security Policy

## Supported versions

The latest commit on the default branch is supported during the V0.x phase.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could enable infrastructure
policy bypass, credential exposure, or unsafe deployment.

Send a private report to the repository owner with:

- Affected version or commit.
- Reproduction steps.
- Expected and actual verdict.
- Potential infrastructure impact.
- Suggested mitigation, if known.

The report will be acknowledged before public disclosure is discussed.

## Enforcement scope

Cloud Change Control Plane is a defense-in-depth control. Production use must
also enforce protected branches, independent IAM authorization, Terraform state
protection, and human approval for sensitive environments.
