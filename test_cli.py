#!/usr/bin/env python3
"""Smoke test: CLI help and basic import check."""

import subprocess
import sys


def test_cli_help():
    """CLI --help should exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "paper_router", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--queries" in result.stdout
    assert "--providers" in result.stdout
    print("[OK] CLI help test passed")


def test_legacy_main_import():
    """Legacy main.py should delegate to cli.main without errors."""
    from paper_router.main import main
    from paper_router.cli import main as cli_main
    assert main is cli_main
    print("[OK] Legacy main.py delegates to cli.main")


if __name__ == "__main__":
    test_cli_help()
    test_legacy_main_import()
    print("\nAll smoke tests passed!")
