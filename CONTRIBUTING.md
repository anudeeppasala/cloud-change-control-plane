# Contributing

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Quality gate

Every change must pass:

```bash
make lint
make typecheck
make test
make build
```

Policy changes must include at least one safe case and one unsafe case. A rule
must not broaden infrastructure permissions without a documented approval
boundary.
