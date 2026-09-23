"""Rubric scoring for validated agent trajectories.

Per-trajectory score on a 1-5 scale:
  - start at 5
  - minus 1 per failed validator (floor at 1)
  - if any of task["must_contain"] strings is missing from
    trajectory["final_answer"], the trajectory is failed and the
    score is capped at 2

A trajectory passes the quality bar when score >= 4.
"""

from src.validators import VALIDATORS

PASS_THRESHOLD = 4
MIN_SCORE = 1
MAX_SCORE = 5


def score_trajectory(trajectory, task):
    """Score one trajectory against its task. Returns a result dict."""
    validator_results = {
        name: fn(trajectory, task) for name, fn in VALIDATORS.items()
    }
    failures = sum(1 for r in validator_results.values() if not r["passed"])
    score = max(MIN_SCORE, MAX_SCORE - failures)

    final_answer = trajectory.get("final_answer", "") or ""
    missing = [
        s for s in (task.get("must_contain", []) or []) if s not in final_answer
    ]
    if missing:
        score = min(score, 2)

    status = trajectory.get("status")
    critical = status == "loop_detected" or score == MIN_SCORE

    return {
        "run_id": trajectory.get("run_id"),
        "task_id": task.get("task_id"),
        "score": score,
        "passed": score >= PASS_THRESHOLD,
        "validator_results": validator_results,
        "failed_validators": [
            name for name, r in validator_results.items() if not r["passed"]
        ],
        "missing_must_contain": missing,
        "status": status,
        "critical": critical,
    }


def aggregate(scored):
    """Aggregate per-trajectory results into suite-level metrics."""
    total = len(scored)
    passed_count = sum(1 for s in scored if s["passed"])
    mean_score = round(sum(s["score"] for s in scored) / total, 4) if total else 0.0
    per_validator_failures = {
        name: sum(1 for s in scored if name in s["failed_validators"])
        for name in VALIDATORS
    }
    return {
        "total": total,
        "passed_count": passed_count,
        "pass_rate": round(passed_count / total, 4) if total else 0.0,
        "mean_score": mean_score,
        "per_validator_failures": per_validator_failures,
        "critical_count": sum(1 for s in scored if s["critical"]),
    }
