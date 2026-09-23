"""CLI: validate a directory of agent trajectories against golden tasks.

Usage:
    python src/run_validation.py --trajectories DIR [--tasks TASKS_JSONL]
        [--min-pass-rate 0.8] [--fail-on-critical] [--generate-samples]

Writes reports/validation_report.json and reports/validation_report.md.
Exits 1 when the quality gate fails.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.generate_samples import TASKS_FILE, generate, load_tasks  # noqa: E402
from src.scorer import aggregate, score_trajectory  # noqa: E402

REPORTS_DIR = REPO_ROOT / "reports"


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Validate agent trajectories against golden tasks."
    )
    p.add_argument("--trajectories", default=str(REPO_ROOT / "data" / "sample_trajectories"),
                   help="Directory of trajectory JSON files.")
    p.add_argument("--tasks", default=str(TASKS_FILE),
                   help="Golden tasks JSONL file.")
    p.add_argument("--min-pass-rate", type=float, default=0.8,
                   help="Gate: required fraction of trajectories with score >= 4.")
    p.add_argument("--fail-on-critical", action="store_true",
                   help="Gate also fails if any trajectory is critical "
                        "(status loop_detected or score 1).")
    p.add_argument("--generate-samples", action="store_true",
                   help="Run the synthetic trajectory generator first.")
    return p.parse_args(argv)


def _match_task(trajectory, filename_stem, tasks_by_id):
    run_id = trajectory.get("run_id", "")
    for key in (filename_stem, run_id.rsplit("-run-", 1)[0]):
        if key in tasks_by_id:
            return tasks_by_id[key], False
    return {}, True


def validate_all(trajectories_dir, tasks):
    tasks_by_id = {t["task_id"]: t for t in tasks}
    results = []
    for path in sorted(Path(trajectories_dir).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            trajectory = json.load(f)
        task, unknown = _match_task(trajectory, path.stem, tasks_by_id)
        scored = score_trajectory(trajectory, task)
        scored["file"] = path.name
        scored["unknown_task"] = unknown
        results.append(scored)
    return results


def _gate(summary, min_pass_rate, fail_on_critical):
    reasons = []
    if summary["pass_rate"] < min_pass_rate:
        reasons.append(
            f"pass_rate {summary['pass_rate']} < min_pass_rate {min_pass_rate}"
        )
    if fail_on_critical and summary["critical_count"] > 0:
        reasons.append(
            f"{summary['critical_count']} critical trajector"
            f"{'y' if summary['critical_count'] == 1 else 'ies'} "
            f"(loop_detected status or score 1)"
        )
    return {"passed": not reasons, "reasons": reasons}


def _write_json_report(report, reports_dir):
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "validation_report.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    return path


def _write_md_report(report, reports_dir):
    summary = report["summary"]
    gate = report["gate"]
    lines = [
        "# Agent Trajectory Validation Report",
        "",
        f"Generated: {report['generated_at']}",
        f"Trajectories: `{report['config']['trajectories_dir']}`",
        f"Tasks: `{report['config']['tasks_file']}`",
        "",
        "## Summary",
        "",
        f"- Total trajectories: {summary['total']}",
        f"- Passed (score >= 4): {summary['passed_count']}",
        f"- Pass rate: {summary['pass_rate']} (gate: >= {report['config']['min_pass_rate']})",
        f"- Mean score: {summary['mean_score']}",
        f"- Critical trajectories: {summary['critical_count']}",
        "",
        "## Per-validator failures",
        "",
    ]
    for name, count in summary["per_validator_failures"].items():
        lines.append(f"- {name}: {count}")
    lines += [
        "",
        "## Per-trajectory results",
        "",
        "| run_id | task_id | score | passed | failed validators | critical |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in report["results"]:
        failed = ", ".join(r["failed_validators"]) or "-"
        lines.append(
            f"| {r['run_id']} | {r['task_id']} | {r['score']} "
            f"| {'yes' if r['passed'] else 'no'} | {failed} "
            f"| {'yes' if r['critical'] else 'no'} |"
        )
    lines += [
        "",
        "## Gate",
        "",
        f"**{'PASSED' if gate['passed'] else 'FAILED'}**",
        "",
    ]
    for reason in gate["reasons"]:
        lines.append(f"- {reason}")
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "validation_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    args = _parse_args(argv)

    if args.generate_samples:
        count = generate()
        print(f"Generated {count} sample trajectories.")

    tasks = load_tasks(args.tasks)
    trajectories_dir = Path(args.trajectories)
    if not trajectories_dir.is_dir():
        print(f"Error: trajectories directory not found: {trajectories_dir}",
              file=sys.stderr)
        return 2

    results = validate_all(trajectories_dir, tasks)
    if not results:
        print(f"Error: no trajectory JSON files in {trajectories_dir}",
              file=sys.stderr)
        return 2

    summary = aggregate(results)
    gate = _gate(summary, args.min_pass_rate, args.fail_on_critical)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "trajectories_dir": str(trajectories_dir),
            "tasks_file": str(args.tasks),
            "min_pass_rate": args.min_pass_rate,
            "fail_on_critical": args.fail_on_critical,
        },
        "summary": summary,
        "gate": gate,
        "results": results,
    }
    json_path = _write_json_report(report, REPORTS_DIR)
    md_path = _write_md_report(report, REPORTS_DIR)

    print(f"Validated {summary['total']} trajectories: "
          f"pass_rate={summary['pass_rate']}, mean_score={summary['mean_score']}")
    print(f"Reports: {json_path}, {md_path}")
    print(f"Gate: {'PASSED' if gate['passed'] else 'FAILED'}")
    for reason in gate["reasons"]:
        print(f"  - {reason}")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
