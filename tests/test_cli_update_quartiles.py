from __future__ import annotations

import subprocess
import sys


def test_cli_update_quartiles_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "paper_router.cli", "update-quartiles", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Update local JCR quartile database" in result.stdout
