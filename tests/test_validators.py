"""Unit tests for the four trajectory validators."""

import pytest

from src.validators import VALIDATORS


def _step(n, tool, args):
    return {
        "step": n,
        "thought": f"Step {n} thought.",
        "action": {"tool": tool, "args": args},
        "observation": f"Step {n} observation.",
    }


def _traj(steps, status="success"):
    return {
        "run_id": "test-run-001",
        "task": "test task",
        "steps": steps,
        "final_answer": "done",
        "status": status,
    }


TASK = {
    "task_id": "task_x",
    "known_tools": ["web_search", "calculator", "file_reader", "memory"],
    "expected_tools": ["file_reader", "memory"],
    "max_steps": 10,
    "must_contain": ["done"],
}


def _valid_steps():
    return [
        _step(1, "web_search", {"query": "postgres 16 eol"}),
        _step(2, "calculator", {"expression": "8*65"}),
        _step(3, "file_reader", {"path": "infra/pricing.yaml"}),
        _step(4, "memory", {"op": "write", "key": "cost", "value": "520"}),
    ]


class TestToolCallValidator:
    fn = staticmethod(VALIDATORS["tool_calls"])

    def test_passing_fixture(self):
        result = self.fn(_traj(_valid_steps()), TASK)
        assert result["passed"] is True
        assert "4 tool calls valid" in result["details"]

    def test_failing_fixture_unknown_tool(self):
        steps = _valid_steps() + [_step(5, "scraper", {"url": "https://x.example"})]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is False
        assert "unknown tool 'scraper'" in result["details"]

    def test_failing_fixture_args_not_dict(self):
        steps = [_step(1, "web_search", "just a string, not a dict")]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is False
        assert "not an object" in result["details"]

    def test_failing_fixture_missing_required_arg(self):
        steps = [
            _step(1, "calculator", {"oops": "no expression here"}),
            _step(2, "memory", {"op": "read"}),  # missing key
        ]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is False
        assert "requires non-empty string arg 'expression'" in result["details"]
        assert "requires non-empty string arg 'key'" in result["details"]

    def test_failing_fixture_empty_string_arg(self):
        steps = [_step(1, "file_reader", {"path": "   "})]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is False
        assert "'path'" in result["details"]


class TestPlanAdherenceValidator:
    fn = staticmethod(VALIDATORS["plan_adherence"])

    def test_passing_fixture(self):
        result = self.fn(_traj(_valid_steps()), TASK)
        assert result["passed"] is True
        assert "file_reader" in result["details"] and "memory" in result["details"]

    def test_failing_fixture_missing_expected_tool(self):
        steps = [
            _step(1, "file_reader", {"path": "a.txt"}),
            _step(2, "calculator", {"expression": "1+1"}),
        ]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is False
        assert "memory" in result["details"]


class TestMaxStepValidator:
    fn = staticmethod(VALIDATORS["max_steps"])

    def test_passing_fixture(self):
        result = self.fn(_traj(_valid_steps()), TASK)  # 4 steps <= 10, success
        assert result["passed"] is True
        assert "4 steps (max 10)" in result["details"]

    def test_failing_fixture_over_budget(self):
        steps = [_step(i, "calculator", {"expression": "1+1"}) for i in range(1, 12)]
        result = self.fn(_traj(steps), TASK)  # 11 > 10
        assert result["passed"] is False
        assert "exceeds max_steps=10" in result["details"]

    def test_failing_fixture_bad_status(self):
        result = self.fn(_traj(_valid_steps(), status="failed"), TASK)
        assert result["passed"] is False
        assert "status is 'failed'" in result["details"]


class TestLoopDetector:
    fn = staticmethod(VALIDATORS["loop_detection"])

    def test_passing_fixture_no_loop(self):
        steps = [
            _step(1, "file_reader", {"path": "a.txt"}),
            _step(2, "file_reader", {"path": "a.txt"}),  # only 2x: fine
            _step(3, "calculator", {"expression": "1+1"}),
        ]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is True

    def test_passing_fixture_same_tool_different_args(self):
        steps = [
            _step(1, "file_reader", {"path": f"f{i}.txt"}) for i in range(3)
        ]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is True

    def test_failing_fixture_three_identical_consecutive(self):
        steps = [
            _step(1, "calculator", {"expression": "1+1"}),
            _step(2, "file_reader", {"path": "stuck.txt"}),
            _step(3, "file_reader", {"path": "stuck.txt"}),
            _step(4, "file_reader", {"path": "stuck.txt"}),
        ]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is False
        assert "Loop detected" in result["details"]
        assert "3x consecutively (steps 2-4)" in result["details"]

    def test_loop_broken_by_different_call_resets(self):
        steps = [
            _step(1, "file_reader", {"path": "a.txt"}),
            _step(2, "file_reader", {"path": "a.txt"}),
            _step(3, "calculator", {"expression": "1+1"}),
            _step(4, "file_reader", {"path": "a.txt"}),
            _step(5, "file_reader", {"path": "a.txt"}),
        ]
        result = self.fn(_traj(steps), TASK)
        assert result["passed"] is True


def test_validators_registry_has_four():
    assert set(VALIDATORS) == {
        "tool_calls", "plan_adherence", "max_steps", "loop_detection"
    }
