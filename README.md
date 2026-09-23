# agent-validation-suite

**Unit tests for AI agent trajectories.** I built this as a QA Lead moving into AI QA: when your "system under test" is a ReAct agent instead of a web app, you still need the same things I rely on in traditional QA — a contract, deterministic fixtures, targeted validators, a rubric, and a quality gate in CI.

This suite takes recorded agent trajectories (thought → action → observation steps plus a final answer), checks them against four validators, scores each run 1–5, and fails the build when the pass rate drops below the gate.

No API keys, no network, fully deterministic. Everything runs offline.

## Architecture

```
                        +-------------------+
                        |  trajectory       |
                        |  producer         |
                        |  (your ReAct      |
                        |   agent, logger,  |
                        |   replay harness) |
                        +--------+----------+
                                 |  writes JSON in
                                 |  the schema below
                                 v
+----------------+     +--------------------+     +------------------+
| golden tasks   |     |  run_validation.py |     |  reports/        |
| data/          |---->|  CLI               +---->|  validation_     |
| agent_tasks    |     |                    |     |  report.json/md  |
| .jsonl         |     |  validators.py  x4 |     +------------------+
+----------------+     |  scorer.py  (1-5)  |
                       |  quality gate      |
                       +---------+----------+
                                 ^
                                 |  seeded fixtures
                        +--------+----------+
                        | generate_samples  |
                        | .py -> data/      |
                        | sample_trajector- |
                        | ies/*.json        |
                        +-------------------+
```

Flow: the CLI loads golden tasks and trajectory files, runs each trajectory through the four validators (`src/validators.py`), scores it with the rubric (`src/scorer.py`), aggregates suite metrics, writes JSON + Markdown reports, and exits non-zero if the gate fails.

## The trajectory schema (the contract)

This is the exact contract between a trajectory producer and this suite. A trajectory is one JSON object per file:

```json
{
  "run_id": "string",
  "task": "string",
  "steps": [
    {
      "step": 1,
      "thought": "string",
      "action": {"tool": "string", "args": {}},
      "observation": "string"
    }
  ],
  "final_answer": "string",
  "status": "success|failed|max_steps_exceeded|loop_detected"
}
```

Rules the validators enforce against this schema:

- `action.tool` must be a string present in the task's `known_tools`.
- `action.args` must be an object, with tool-specific required string args: `calculator.expression`, `file_reader.path`, `web_search.query`, `memory.key` (all non-empty).
- Every tool in the task's `expected_tools` must appear at least once in `steps`.
- `len(steps) <= task.max_steps` **and** `status == "success"`.
- No run of 3+ consecutive steps with the identical `(tool, canonical args)` pair.

## Golden tasks

`data/agent_tasks.jsonl` holds 15 golden tasks, one JSON object per line:

```json
{"task_id": "task_001", "task": "...", "known_tools": ["web_search","calculator","file_reader","memory"], "expected_tools": ["file_reader","memory"], "max_steps": 12, "must_contain": ["triage", "P1"]}
```

The set varies deliberately: search+calculate tasks, file+memory tasks, calculator-only tasks, a four-tool task, and two trap tasks (`task_014` tempts a nonexistent `scraper` tool; `task_015` tempts an endless poll loop) so the bad samples exercise every validator.

## Quickstart

```bash
git clone <this-repo> && cd agent-validation-suite
pip install -r requirements.txt

# 1. Generate deterministic sample trajectories (13 good, 2 bad)
python src/generate_samples.py

# 2. Validate them against the golden tasks
python src/run_validation.py --trajectories data/sample_trajectories

# 3. Run the unit tests
pytest -q
```

Reports land in `reports/validation_report.json` and `reports/validation_report.md`.

### CLI options

```
python src/run_validation.py --trajectories DIR --tasks data/agent_tasks.jsonl \
    --min-pass-rate 0.8 [--fail-on-critical] [--generate-samples]
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--trajectories` | `data/sample_trajectories` | Directory of trajectory JSON files |
| `--tasks` | `data/agent_tasks.jsonl` | Golden tasks file |
| `--min-pass-rate` | `0.8` | Gate: required fraction of runs scoring ≥ 4 |
| `--fail-on-critical` | off | Also fail the gate if any run is critical (`loop_detected` status or score 1) |
| `--generate-samples` | off | Run the sample generator before validating |

Exit codes: `0` gate passed, `1` gate failed, `2` usage error (missing dir / no trajectories).

## Sample output

```
$ python src/run_validation.py --generate-samples --trajectories data/sample_trajectories
Generated 15 sample trajectories.
Validated 15 trajectories: pass_rate=0.8667, mean_score=4.5333
Reports: reports/validation_report.json, reports/validation_report.md
Gate: PASSED
```

And with the critical flag (the seeded samples include a score-1 run and a `loop_detected` run):

```
$ python src/run_validation.py --trajectories data/sample_trajectories --fail-on-critical
Validated 15 trajectories: pass_rate=0.8667, mean_score=4.5333
Gate: FAILED
  - 2 critical trajectories (loop_detected status or score 1)
```

Excerpt from `reports/validation_report.json`:

```json
{
  "summary": {
    "total": 15,
    "passed_count": 13,
    "pass_rate": 0.8667,
    "mean_score": 4.5333,
    "per_validator_failures": {
      "tool_calls": 1,
      "plan_adherence": 1,
      "max_steps": 2,
      "loop_detection": 2
    },
    "critical_count": 2
  },
  "gate": {"passed": true, "reasons": []}
}
```

## Scoring rubric

Each trajectory starts at 5 and loses 1 point per failed validator (floor 1). If any `must_contain` string is missing from `final_answer`, the score is capped at 2. A run passes at score ≥ 4. Suite metrics: pass rate, mean score, and per-validator failure counts — the failure counts are what I use to decide whether the agent or the task definition needs fixing.

## Integrating a trajectory producer (e.g. a ReAct agent)

If you run a ReAct agent, hook its loop to emit this schema: after each iteration, append `{"step", "thought", "action": {"tool", "args"}, "observation"}` to a list; when the agent stops, write one JSON file with `run_id`, the original `task` prompt, the `steps` list, the `final_answer`, and a `status` mapped from your stop reason (`success`, `failed`, `max_steps_exceeded`, `loop_detected`). Name the file `<task_id>.json` (or make `run_id` start with `<task_id>-run-`) so the CLI matches it to the right golden task, drop it in a directory, and point `--trajectories` at it. No changes to this repo are needed.

## Layout

```
agent-validation-suite/
├── src/
│   ├── validators.py        # 4 validators -> {"passed", "details"}
│   ├── scorer.py            # 1-5 rubric + suite aggregation
│   ├── generate_samples.py  # seeded synthetic trajectories (13 good, 2 bad)
│   └── run_validation.py    # CLI, reports, quality gate
├── data/
│   ├── agent_tasks.jsonl    # 15 golden tasks
│   └── sample_trajectories/ # generated fixtures (gitignored, has .gitkeep)
├── tests/                   # pytest: validators, scorer, end-to-end
├── reports/                 # generated reports (gitignored, has .gitkeep)
└── .github/workflows/ci.yml # pytest + validation smoke test
```

## Roadmap

- Trajectory diffing: compare two runs of the same task to catch regressions between agent versions.
- LLM-as-judge validator for `final_answer` quality (optional, behind a flag — the offline gate stays default).
- More tool profiles (e.g. `browser`, `sql`) with per-tool arg schemas loaded from a config file instead of hard-coded checks.
- JUnit XML report output so CI dashboards can render per-trajectory results.
- A small replay harness that re-executes trajectories against stubbed tools to verify observations are reproducible.

## License

MIT — see `LICENSE`.
