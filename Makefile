.PHONY: install test lint typecheck demo-safe demo-approval demo-block build clean

install:
	python -m pip install -e ".[dev]"

test:
	pytest --cov=cloud_guardian --cov-report=term-missing

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy

demo-safe:
	cloud-guardian review --intent examples/intents/safe-change.json --plan examples/plans/safe-plan.json --cost-delta 1.25

demo-approval:
	cloud-guardian review --intent examples/intents/replacement-change.json --plan examples/plans/replacement-plan.json

demo-block:
	cloud-guardian review --intent examples/intents/safe-change.json --plan examples/plans/dangerous-plan.json --environment production --cost-delta 120

build:
	python -m build

clean:
	python -c "import shutil; [shutil.rmtree(path, ignore_errors=True) for path in ('build', 'dist', '.pytest_cache', '.mypy_cache', '.ruff_cache')]"
