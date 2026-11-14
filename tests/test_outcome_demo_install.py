"""Verify the recovery demo runs from a clean, dependency-free installation."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_recovery_demo_runs_from_fresh_package_install(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    install_target = tmp_path / "site"
    install_target.mkdir()
    installed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-build-isolation",
            "--target",
            str(install_target),
            str(repository),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(install_target)
    demo = subprocess.run(
        [sys.executable, str(repository / "examples" / "outcome_recovery_demo.py")],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert demo.returncode == 0, demo.stdout + demo.stderr
    assert str(install_target) in demo.stdout
    assert "Correction arrives" in demo.stdout
    assert "blocks the stale continue action" in demo.stdout
    assert "recovers, replans" in demo.stdout
    assert "Independent evaluator: COMPLETED (VERIFIED_TERMINAL_STATE)" in demo.stdout
    assert "REAL_AGENT_NOT_RUN" in demo.stdout
