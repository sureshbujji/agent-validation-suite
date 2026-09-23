"""Unit tests for the 1-5 rubric scorer (hand-computed expectations)."""

from src.scorer import aggregate, score_trajectory


def _step(n, tool, args):
    return {
        "step": n,
        "thought": f"Step {n}.",
        "action": {"tool": tool, "args": args},
        "observation": f"Obs {n}.",
    }


TASK = {
    "task_id": "task_x",
    "known_tools": ["web_search", "calculator", "file_reader", "memory"],
    "expected_tools": ["file_reader", "memory"],
    "max_steps": 10,
    "must_contain": ["v3.2.1"],
}

PERFECT_STEPS = [
    _step(1, "file_reader", {"path": "docs/release_notes.md"}),
    _step(2, "memory", {"op": "write", "key": "v", "value": "v3.2.1"}),
]


def _traj(steps, final_answer="Version v3.2.1 released.", status="success"):
    return {
        "run_id": "score-run-001",
        "task": "t",
        "steps": steps,
        "final_answer": final_answer,
        "status": status,
    }


def test_perfect_trajectory_scores_5():
    scored = score_trajectory(_traj(PERFECT_STEPS), TASK)
    assert scored["score"] == 5
    assert scored["passed"] is True
    assert scored["failed_validators"] == []
    assert scored["critical"] is False


def test_one_failed_validator_scores_4():
    # Hand-computed: 5 - 1 failure = 4, must_contain present -> stays 4.
    steps = [_step(1, "file_reader", {"path": "docs/release_notes.md"})]
    # plan_adherence fails: expected "memory" never used.
    scored = score_trajectory(_traj(steps), TASK)
    assert scored["failed_validators"] == ["plan_adherence"]
    assert scored["score"] == 4
    assert scored["passed"] is True


def test_missing_must_contain_caps_score_at_2():
    # Hand-computed: 0 failures -> 5, but must_contain missing -> min(5, 2) = 2.
    scored = score_trajectory(
        _traj(PERFECT_STEPS, final_answer="Version released."), TASK
    )
    assert scored["failed_validators"] == []
    assert scored["missing_must_contain"] == ["v3.2.1"]
    assert scored["score"] == 2
    assert scored["passed"] is False


def test_failure_plus_missing_must_contain():
    # Hand-computed: 5 - 1 = 4, then min(4, 2) = 2.
    steps = [_step(1, "file_reader", {"path": "docs/release_notes.md"})]
    scored = score_trajectory(
        _traj(steps, final_answer="Version released."), TASK
    )
    assert scored["score"] == 2


def test_four_failed_validators_scores_1_and_is_critical():
    # Hand-computed: 5 - 4 = 1 (floor); score 1 -> critical.
    steps = [_step(i, "scraper", {"url": "https://x.example"}) for i in range(1, 5)]
    steps.append(_step(5, "scraper", "not-a-dict"))
    for i in range(6, 12):  # 11 steps > max_steps=10, identical-run loop too
        steps.append(_step(i, "scraper", {"url": "https://x.example"}))
    traj = _traj(steps, status="failed")
    scored = score_trajectory(traj, TASK)
    assert len(scored["failed_validators"]) == 4
    assert scored["score"] == 1
    assert scored["critical"] is True
    assert scored["passed"] is False


def test_loop_detected_status_is_critical():
    steps = [_step(i, "file_reader", {"path": "s.txt"}) for i in range(1, 4)]
    traj = _traj(steps, status="loop_detected")
    scored = score_trajectory(traj, TASK)
    assert scored["critical"] is True


def test_aggregate_hand_computed():
    # Hand-computed over three scored results:
    #   scores 5, 4, 2 -> total 3, passed 2, pass_rate 0.6667, mean 3.6667
    scored = [
        {"score": 5, "passed": True, "failed_validators": [], "critical": False},
        {"score": 4, "passed": True, "failed_validators": ["plan_adherence"],
         "critical": False},
        {"score": 2, "passed": False,
         "failed_validators": ["tool_calls", "loop_detection"], "critical": False},
    ]
    agg = aggregate(scored)
    assert agg["total"] == 3
    assert agg["passed_count"] == 2
    assert agg["pass_rate"] == round(2 / 3, 4)
    assert agg["mean_score"] == round(11 / 3, 4)
    assert agg["per_validator_failures"]["plan_adherence"] == 1
    assert agg["per_validator_failures"]["tool_calls"] == 1
    assert agg["per_validator_failures"]["loop_detection"] == 1
    assert agg["per_validator_failures"]["max_steps"] == 0
    assert agg["critical_count"] == 0


def test_aggregate_empty():
    agg = aggregate([])
    assert agg["total"] == 0
    assert agg["pass_rate"] == 0.0
    assert agg["mean_score"] == 0.0
