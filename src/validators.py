"""Validators for AI agent trajectories.

Each validator takes a trajectory dict and its task dict and returns
{"passed": bool, "details": str}. See README.md for the exact trajectory
schema this module validates against.
"""

import json

# Per-tool required argument checks: {tool_name: [(arg_name, expected_type)]}
_TOOL_ARG_REQUIREMENTS = {
    "web_search": [("query", str)],
    "calculator": [("expression", str)],
    "file_reader": [("path", str)],
    "memory": [("key", str)],
}

_VALIDATORS = {}


def _result(passed, details):
    return {"passed": bool(passed), "details": details}


def _steps(trajectory):
    steps = trajectory.get("steps")
    return steps if isinstance(steps, list) else []


def validate_tool_calls(trajectory, task):
    """Every action.tool must be in the task's known_tools and carry valid args.

    Checks:
      - action is a dict with a string "tool" and a dict "args"
      - tool is one of task["known_tools"]
      - tool-specific required args exist, are strings, and are non-empty
        (calculator.expression, file_reader.path, web_search.query, memory.key)
    """
    known_tools = task.get("known_tools", []) or []
    steps = _steps(trajectory)
    problems = []

    for i, step in enumerate(steps, start=1):
        action = step.get("action") if isinstance(step, dict) else None
        if not isinstance(action, dict):
            problems.append(f"Step {i}: action is missing or not an object")
            continue
        tool = action.get("tool")
        args = action.get("args")
        if not isinstance(tool, str) or not tool:
            problems.append(f"Step {i}: tool name is missing or not a string")
            continue
        if tool not in known_tools:
            problems.append(
                f"Step {i}: unknown tool '{tool}' "
                f"(known tools: {', '.join(known_tools) or 'none'})"
            )
            continue
        if not isinstance(args, dict):
            problems.append(f"Step {i}: args for tool '{tool}' is not an object")
            continue
        for arg_name, arg_type in _TOOL_ARG_REQUIREMENTS.get(tool, []):
            value = args.get(arg_name)
            if not isinstance(value, arg_type) or (
                isinstance(value, str) and not value.strip()
            ):
                problems.append(
                    f"Step {i}: tool '{tool}' requires non-empty "
                    f"string arg '{arg_name}'"
                )

    if problems:
        return _result(False, "Invalid tool calls: " + "; ".join(problems))
    return _result(True, f"All {len(steps)} tool calls valid against known tools.")


def validate_plan_adherence(trajectory, task):
    """Every tool in task["expected_tools"] must appear at least once."""
    expected = task.get("expected_tools", []) or []
    used = set()
    for step in _steps(trajectory):
        action = step.get("action") if isinstance(step, dict) else None
        if isinstance(action, dict) and isinstance(action.get("tool"), str):
            used.add(action["tool"])
    missing = [t for t in expected if t not in used]
    if missing:
        return _result(
            False,
            f"Plan not followed: expected tools never used: "
            f"{', '.join(missing)} (used: {', '.join(sorted(used)) or 'none'})",
        )
    return _result(True, f"All expected tools used: {', '.join(expected) or 'none required'}.")


def validate_max_steps(trajectory, task):
    """len(steps) <= task["max_steps"] and trajectory status is 'success'."""
    max_steps = task.get("max_steps")
    steps = _steps(trajectory)
    status = trajectory.get("status")
    problems = []
    if isinstance(max_steps, int) and len(steps) > max_steps:
        problems.append(f"{len(steps)} steps exceeds max_steps={max_steps}")
    if status != "success":
        problems.append(f"final status is '{status}', expected 'success'")
    if problems:
        return _result(False, "Step budget / status check failed: " + "; ".join(problems))
    return _result(
        True,
        f"Within budget: {len(steps)} steps (max {max_steps}), status 'success'.",
    )


def _canonical_action(step):
    """Canonical (tool, args) key used for loop detection."""
    action = step.get("action") if isinstance(step, dict) else None
    if not isinstance(action, dict):
        return ("<missing>", "<missing>")
    tool = action.get("tool")
    args = action.get("args")
    try:
        canon_args = json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        canon_args = str(args)
    return (tool, canon_args)


def validate_no_loops(trajectory, task):
    """Fail if the same (tool, canonical-args) repeats 3+ times consecutively."""
    steps = _steps(trajectory)
    if not steps:
        return _result(True, "No steps, no loop possible.")
    run_key = _canonical_action(steps[0])
    run_len = 1
    run_start = 1  # 1-based step number
    for i, step in enumerate(steps[1:], start=2):
        key = _canonical_action(step)
        if key == run_key:
            run_len += 1
        else:
            if run_len >= 3:
                break
            run_key, run_len, run_start = key, 1, i
    if run_len >= 3:
        tool, canon_args = run_key
        return _result(
            False,
            f"Loop detected: ('{tool}', {canon_args}) repeated "
            f"{run_len}x consecutively (steps {run_start}-{run_start + run_len - 1}).",
        )
    return _result(True, "No repeated-action loop (no 3+ identical consecutive calls).")


VALIDATORS = {
    "tool_calls": validate_tool_calls,
    "plan_adherence": validate_plan_adherence,
    "max_steps": validate_max_steps,
    "loop_detection": validate_no_loops,
}
