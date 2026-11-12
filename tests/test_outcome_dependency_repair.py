from __future__ import annotations

import pytest

from benchmarks.outcome_worlds import DependencyRepairSandbox, dependency_repair_task


def test_safe_dependency_repair_passes_hidden_local_check_within_budget() -> None:
    observation, tools = dependency_repair_task(seed=9)
    assert "tests/test_dependency_compatibility_hidden.py" not in observation.canonical_json()
    assert tools.read_file("pyproject.toml").find("httpx>=0.27.0,<0.28.0") >= 0
    old_lock = tools.read_file("requirements.lock")
    assert old_lock == "httpx==0.26.0\n"
    assert tools.run_hidden_tests() == "FAIL"

    tools.replace_lock_line("requirements.lock", "httpx==0.26.0", "httpx==0.27.1")

    assert tools.run_hidden_tests() == "PASS"
    assert tools.tool_call_count == 5


def test_hidden_test_file_is_not_readable() -> None:
    _, tools = dependency_repair_task(seed=10)
    with pytest.raises(PermissionError, match="hidden evaluator"):
        tools.read_file("tests/test_dependency_compatibility_hidden.py")


def test_wrong_lock_version_fails_hidden_compatibility_oracle() -> None:
    _, tools = dependency_repair_task(seed=11)
    tools.replace_lock_line("requirements.lock", "httpx==0.26.0", "httpx==0.26.1")
    assert tools.run_hidden_tests() == "FAIL"


def test_patch_is_limited_to_one_exact_lockfile_line() -> None:
    _, tools = dependency_repair_task(seed=12)
    with pytest.raises(PermissionError, match="only the lock file"):
        tools.replace_lock_line("pyproject.toml", 'httpx>=0.27.0,<0.28.0',
                                'httpx>=0.26.0,<0.28.0')
    with pytest.raises(ValueError, match="exact httpx release pin"):
        tools.replace_lock_line("requirements.lock", "httpx==0.26.0",
                                "__import__('os').system('whoami')")
    assert tools.run_hidden_tests() == "FAIL"


def test_tool_call_budget_terminates_repair_loop() -> None:
    sandbox = DependencyRepairSandbox(seed=13, max_tool_calls=1)
    assert sandbox.read_file("requirements.lock") == "httpx==0.26.0\n"
    with pytest.raises(RuntimeError, match="budget exhausted"):
        sandbox.read_file("pyproject.toml")
