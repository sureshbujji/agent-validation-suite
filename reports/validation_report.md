# Agent Trajectory Validation Report

Generated: 2026-09-23T03:58:00.511373+00:00
Trajectories: `/home/hatch/workspace/github-projects/agent-validation-suite/data/sample_trajectories`
Tasks: `/home/hatch/workspace/github-projects/agent-validation-suite/data/agent_tasks.jsonl`

## Summary

- Total trajectories: 15
- Passed (score >= 4): 13
- Pass rate: 0.8667 (gate: >= 0.8)
- Mean score: 4.5333
- Critical trajectories: 2

## Per-validator failures

- tool_calls: 1
- plan_adherence: 1
- max_steps: 2
- loop_detection: 2

## Per-trajectory results

| run_id | task_id | score | passed | failed validators | critical |
| --- | --- | --- | --- | --- | --- |
| task_001-run-001 | task_001 | 5 | yes | - | no |
| task_002-run-001 | task_002 | 5 | yes | - | no |
| task_003-run-001 | task_003 | 5 | yes | - | no |
| task_004-run-001 | task_004 | 5 | yes | - | no |
| task_005-run-001 | task_005 | 5 | yes | - | no |
| task_006-run-001 | task_006 | 5 | yes | - | no |
| task_007-run-001 | task_007 | 5 | yes | - | no |
| task_008-run-001 | task_008 | 5 | yes | - | no |
| task_009-run-001 | task_009 | 5 | yes | - | no |
| task_010-run-001 | task_010 | 5 | yes | - | no |
| task_011-run-001 | task_011 | 5 | yes | - | no |
| task_012-run-001 | task_012 | 5 | yes | - | no |
| task_013-run-001 | task_013 | 5 | yes | - | no |
| task_014-run-001 | task_014 | 1 | no | tool_calls, plan_adherence, max_steps, loop_detection | yes |
| task_015-run-001 | task_015 | 2 | no | max_steps, loop_detection | yes |

## Gate

**FAILED**

- 2 critical trajectories (loop_detected status or score 1)
