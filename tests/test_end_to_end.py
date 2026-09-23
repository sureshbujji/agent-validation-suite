"""End-to-end tests: generate samples, run the CLI, check reports and gates."""

import json
from pathlib import Path

from src.generate_samples import OUT_DIR as SAMPLE_DIR, TASKS_FILE, generate
from src.run_validation import REPORTS_DIR, main


def _write_bad_trajectory(path, run_id):
    bad = {
        "run_id": run_id,
        "task": "some task",
        "steps": [
            {
                "step": 1,
                "thought": "Using a tool that does not exist.",
                "action": {"tool": "nope", "args": {}},
                "observation": "Error.",
            }
        ],
        "final_answer": "oops",
        "status": "failed",
    }
    path.write_text(json.dumps(bad), encoding="utf-8")


def test_generate_then_validate_gate_passes():
    assert generate() == 15
    assert len(list(Path(SAMPLE_DIR).glob("*.json"))) == 15

    exit_code = main(["--trajectories", str(SAMPLE_DIR),
                      "--tasks", str(TASKS_FILE)])
    assert exit_code == 0

    report_path = REPORTS_DIR / "validation_report.json"
    md_path = REPORTS_DIR / "validation_report.md"
    assert report_path.exists()
    assert md_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    for key in ("generated_at", "config", "summary", "gate", "results"):
        assert key in report, f"missing report key: {key}"
    summary = report["summary"]
    for key in ("total", "passed_count", "pass_rate", "mean_score",
                "per_validator_failures", "critical_count"):
        assert key in summary, f"missing summary key: {key}"
    assert summary["total"] == 15
    assert len(report["results"]) == 15
    assert summary["pass_rate"] >= 0.8
    assert report["gate"]["passed"] is True
    # The two seeded bad trajectories must be present and failing.
    by_task = {r["task_id"]: r for r in report["results"]}
    assert by_task["task_014"]["score"] == 1
    assert by_task["task_015"]["score"] == 2


def test_gate_fails_on_bad_only_dir(tmp_path):
    _write_bad_trajectory(tmp_path / "bad1.json", "bad1-run-001")
    _write_bad_trajectory(tmp_path / "bad2.json", "bad2-run-001")
    exit_code = main(["--trajectories", str(tmp_path),
                      "--tasks", str(TASKS_FILE),
                      "--min-pass-rate", "0.99"])
    assert exit_code == 1


def test_fail_on_critical_flag(tmp_path):
    generate()  # ensure samples exist
    exit_code = main(["--trajectories", str(SAMPLE_DIR),
                      "--tasks", str(TASKS_FILE),
                      "--fail-on-critical"])
    # task_014 scores 1 and task_015 has loop_detected status: both critical.
    assert exit_code == 1


def test_missing_trajectories_dir_returns_2(tmp_path):
    exit_code = main(["--trajectories", str(tmp_path / "does-not-exist")])
    assert exit_code == 2
