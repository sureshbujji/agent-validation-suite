"""Generate deterministic synthetic agent trajectories for the validation suite.

Produces mostly GOOD trajectories (correct tools, valid args, final answers
containing the task's must_contain strings) plus two deliberately BAD ones:
  - task_014: wrong tool name, invalid args, too many steps, missing
    expected tool -> fails every validator (score 1, critical)
  - task_015: repeated identical action loop, loop_detected status,
    must_contain missing from the final answer (score 2, critical)

Deterministic: fixed SEED, no network, no API keys.
"""

import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_FILE = REPO_ROOT / "data" / "agent_tasks.jsonl"
OUT_DIR = REPO_ROOT / "data" / "sample_trajectories"

SEED = 42

# Per-task step plans: (tool, args, thought, [observation variants]).
# Every good plan uses all expected_tools, valid args, and <= max_steps steps.
GOOD_PLANS = {
    "task_001": [
        ("file_reader", {"path": "incidents/p1_checkout_outage.log"},
         "I need the raw incident details first, so I'll read the P1 incident log.",
         ["Log shows checkout 500s starting 09:12, triage tag P1, owner: payments team."]),
        ("memory", {"op": "read", "key": "triage_note_checkout"},
         "Now I'll recall the previous triage note for context before summarizing.",
         ["Previous note: 'P1 triage: payment gateway timeout suspected; rollback candidate.'"]),
    ],
    "task_002": [
        ("web_search", {"query": "CVE-2026-1042 severity rating"},
         "First, look up how severe CVE-2026-1042 is.",
         ["CVE-2026-1042 rated HIGH, CVSS 8.1.", "Search result: CVE-2026-1042 is HIGH severity (CVSS 8.1)."]),
        ("calculator", {"expression": "60/240*100"},
         "Now compute the affected-host percentage.",
         ["Result: 25", "Calculator returned 25."]),
    ],
    "task_003": [
        ("file_reader", {"path": "docs/release_notes.md"},
         "Read the release notes to find the new version number.",
         ["Latest release: v3.2.1 (2026-09-18)."]),
        ("memory", {"op": "write", "key": "release_version", "value": "v3.2.1"},
         "Store the version in memory for the next run.",
         ["Stored key 'release_version' = 'v3.2.1'."]),
    ],
    "task_004": [
        ("file_reader", {"path": "metrics/nightly.json"},
         "Read the nightly metrics file to get failed/total request counts.",
         ['File contents: {"failed": 37, "total": 1480}.']),
        ("calculator", {"expression": "37/1480*100"},
         "Compute the error rate percentage.",
         ["Result: 2.5", "Calculator returned 2.5."]),
    ],
    "task_005": [
        ("web_search", {"query": "on-call rotation schedule primary"},
         "Look up who is on call, then work out the MTTR.",
         ["Primary on-call: QA rotation, S. Itha this week."]),
        ("calculator", {"expression": "(14*60+47)-(14*60+5)"},
         "MTTR is resolve minus start, in minutes.",
         ["Result: 42"]),
    ],
    "task_006": [
        ("memory", {"op": "read", "key": "api_key_alias"},
         "Recall the stored API key alias first.",
         ["Alias found: 'billing-svc-key'."]),
        ("web_search", {"query": "billing-svc-key rotation policy docs"},
         "Search the docs for that alias's rotation policy.",
         ["Docs: keys rotate every 90 days.", "Policy: rotation every 90 days."]),
    ],
    "task_007": [
        ("calculator", {"expression": "45*12+200"},
         "One calculation covers it: daily rate times days plus the bonus.",
         ["Result: 740"]),
    ],
    "task_008": [
        ("file_reader", {"path": "qa/regression_test_plan.md"},
         "Read the regression test plan.",
         ["Test plan: 214 cases across 6 suites."]),
        ("file_reader", {"path": "qa/open_bugs.csv"},
         "Read the open bug list too.",
         ["12 open bugs, 3 of them blockers."]),
        ("memory", {"op": "write", "key": "qa_summary",
                    "value": "214 cases, 12 open bugs, 3 blockers"},
         "Write a summary note to memory for the QA lead.",
         ["Stored key 'qa_summary'."]),
    ],
    "task_009": [
        ("web_search", {"query": "PostgreSQL 16 end of life date"},
         "Search for the Postgres 16 EOL date.",
         ["PostgreSQL 16 EOL: November 2028.", "EOL date is November 2028."]),
        ("memory", {"op": "write", "key": "postgres16_eol", "value": "2028-11"},
         "Remember it for the upgrade plan.",
         ["Stored key 'postgres16_eol' = '2028-11'."]),
    ],
    "task_010": [
        ("file_reader", {"path": "infra/pricing.yaml"},
         "Read the environment pricing file.",
         ["qa_env_monthly: 65"]),
        ("calculator", {"expression": "8*65"},
         "Multiply environments by unit cost.",
         ["Result: 520"]),
    ],
    "task_011": [
        ("web_search", {"query": "status page outage 2026-09-22"},
         "Check the status page for the outage report.",
         ["Status page: checkout errors under investigation."]),
        ("file_reader", {"path": "incidents/INC-2291.log"},
         "Read the incident log for hard numbers.",
         ["INC-2291: 1,204 of 48,160 users affected."]),
        ("calculator", {"expression": "1204/48160*100"},
         "Compute the affected-users percentage.",
         ["Result: 2.5"]),
        ("memory", {"op": "write", "key": "incident_id", "value": "INC-2291"},
         "Remember the incident ID.",
         ["Stored key 'incident_id' = 'INC-2291'."]),
    ],
    "task_012": [
        ("memory", {"op": "write", "key": "flaky_test_policy",
                    "value": "quarantine after 3 consecutive flakes"},
         "Write the flaky-test decision record straight to memory.",
         ["Stored key 'flaky_test_policy'."]),
    ],
    "task_013": [
        ("calculator", {"expression": "34+41+29"},
         "First total the story points.",
         ["Result: 104"]),
        ("calculator", {"expression": "104/3"},
         "Then divide by 3 sprints for the average velocity.",
         ["Result: 34.666666666666664"]),
    ],
}

FINAL_ANSWERS = {
    "task_001": "Triage complete: the P1 incident is the checkout outage (500s since 09:12). Matches the prior P1 triage note pointing at the payment gateway; rollback is the recommended next step.",
    "task_002": "CVE-2026-1042 is rated HIGH (CVSS 8.1). With 60 of 240 hosts vulnerable, 25% of the fleet is affected.",
    "task_003": "Release notes confirm the new version is v3.2.1. Saved to memory so the next validation run can reference it.",
    "task_004": "The nightly error rate is 2.5%: 37 failed requests out of 1480 total.",
    "task_005": "MTTR for the incident was 42 minutes (started 14:05, resolved 14:47).",
    "task_006": "The stored alias is billing-svc-key; per the docs its rotation policy is every 90 days.",
    "task_007": "Total on-call stipend: $740 ($45 x 12 days + $200 incident bonus).",
    "task_008": "Wrote a summary of the test plan to memory: 214 cases, 12 open bugs (3 blockers).",
    "task_009": "Postgres 16 EOL is November 2028. Saved for the upgrade plan.",
    "task_010": "Monthly cost for 8 QA environments at $65 each: $520.",
    "task_011": "Incident INC-2291: 2.5% of users affected (1,204 of 48,160). Incident ID remembered.",
    "task_012": "Decision recorded: flaky tests go to quarantine after 3 consecutive flakes on the release branch.",
    "task_013": "Sprint velocity: 104 story points over 3 sprints, average 34.67 per sprint.",
}


def _build_good(task, rng):
    plan = GOOD_PLANS[task["task_id"]]
    steps = []
    for i, (tool, args, thought, observations) in enumerate(plan, start=1):
        steps.append({
            "step": i,
            "thought": thought,
            "action": {"tool": tool, "args": args},
            "observation": rng.choice(observations),
        })
    return {
        "run_id": f"{task['task_id']}-run-001",
        "task": task["task"],
        "steps": steps,
        "final_answer": FINAL_ANSWERS[task["task_id"]],
        "status": "success",
    }


def _build_bad_wrong_tool(task):
    """task_014: unknown tool, invalid args, too many steps, expected tool
    missing, failed status -> every validator fails (score 1)."""
    steps = []
    for i in range(1, 9):
        steps.append({
            "step": i,
            "thought": "I'll scrape the pricing page directly.",
            "action": {"tool": "scraper", "args": {"url": "https://competitor.example/pricing"}},
            "observation": "Error: tool 'scraper' is not available.",
        })
    steps.append({  # invalid args: not a dict
        "step": 9,
        "thought": "Trying the scraper a different way.",
        "action": {"tool": "scraper", "args": "https://competitor.example/pricing"},
        "observation": "Error: args must be an object.",
    })
    for i in (10, 11, 12):
        steps.append({
            "step": i,
            "thought": "Retrying the scrape once more.",
            "action": {"tool": "scraper", "args": {"url": "https://competitor.example/pricing"}},
            "observation": "Error: tool 'scraper' is not available.",
        })
    return {
        "run_id": f"{task['task_id']}-run-001",
        "task": task["task"],
        "steps": steps,  # 12 steps > max_steps=10, expected web_search never used
        "final_answer": "The cheapest competitor plan I found is $29/mo.",
        "status": "failed",
    }


def _build_bad_loop(task):
    """task_015: same action 4x in a row, loop_detected, final answer misses
    must_contain -> loop + max_steps validators fail, score capped at 2."""
    steps = [
        {
            "step": i,
            "thought": "Poll the deploy status file again.",
            "action": {"tool": "file_reader", "args": {"path": "deploy_status.txt"}},
            "observation": "Status: deploying (not done yet).",
        }
        for i in range(1, 5)
    ]
    return {
        "run_id": f"{task['task_id']}-run-001",
        "task": task["task"],
        "steps": steps,
        "final_answer": "Polling timed out before the deploy finished; final status unknown.",
        "status": "loop_detected",
    }


_BAD_BUILDERS = {
    "task_014": _build_bad_wrong_tool,
    "task_015": _build_bad_loop,
}


def load_tasks(path=TASKS_FILE):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def generate(out_dir=OUT_DIR, tasks_file=TASKS_FILE, seed=SEED):
    rng = random.Random(seed)
    tasks = load_tasks(tasks_file)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        builder = _BAD_BUILDERS.get(task["task_id"])
        trajectory = builder(task) if builder else _build_good(task, rng)
        with open(out_dir / f"{task['task_id']}.json", "w", encoding="utf-8") as f:
            json.dump(trajectory, f, indent=2)
            f.write("\n")
    return len(tasks)


def main():
    count = generate()
    print(f"Generated {count} trajectories in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
