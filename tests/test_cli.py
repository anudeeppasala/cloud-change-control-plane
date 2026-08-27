from __future__ import annotations

import json
from pathlib import Path

from cloud_guardian.cli import main

ROOT = Path(__file__).parents[1]


def test_cli_emits_json_and_returns_allow_exit_code(capsys: object) -> None:
    exit_code = main(
        [
            "review",
            "--intent",
            str(ROOT / "examples" / "intents" / "safe-change.json"),
            "--plan",
            str(ROOT / "examples" / "plans" / "safe-plan.json"),
            "--cost-delta",
            "1.25",
            "--json",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["verdict"] == "allow"


def test_cli_returns_block_exit_code(capsys: object) -> None:
    exit_code = main(
        [
            "review",
            "--intent",
            str(ROOT / "examples" / "intents" / "safe-change.json"),
            "--plan",
            str(ROOT / "examples" / "plans" / "dangerous-plan.json"),
            "--environment",
            "production",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 3
    assert "BLOCK" in captured.out


def test_cli_reports_bad_input(capsys: object) -> None:
    exit_code = main(
        [
            "review",
            "--intent",
            "missing.json",
            "--plan",
            "missing.tfplan.json",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 1
    assert "input error" in captured.err
