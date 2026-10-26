"""Spike: does Claude turn the sample assignment into criteria and tasks in the shape we need?

Run from the project folder:

    uv run python scripts/spike_claude.py                     # uses samples/assignment-room-booking.md
    uv run python scripts/spike_claude.py path/to/other.md

It prints the criteria and tasks, checks them against what the app needs, and reports
how long the call took, the token usage and an estimated cost.
"""

import os
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from referee import ai  # noqa: E402

# Claude Opus 5.5 prices in dollars per million tokens (thinking counts as output).
PRICE_INPUT = 4.00
PRICE_OUTPUT = 20.00


def main() -> int:
    load_dotenv(ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill in your key.")
        return 2

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "assignment-room-booking.md"
    if not path.exists():
        print(f"Can't find {path}. Write the sample assignment first, or pass another file.")
        return 2
    text = path.read_text(encoding="utf-8")

    print(f"Sending {path.name} ({len(text):,} characters) to {ai.model_name()}…")
    started = time.perf_counter()
    try:
        response = ai.request_plan(text)
    except ai.GenerationError as error:
        print(f"FAILED after {time.perf_counter() - started:.1f}s: {error}")
        return 1
    seconds = time.perf_counter() - started
    plan = response.parsed_output

    # --- The plan itself -----------------------------------------------------------------
    print(f"\nusable: {plan.usable}\n")
    by_criterion: dict[str, list] = {c.id: [] for c in plan.criteria}
    for task in plan.tasks:
        by_criterion.setdefault(task.criterion_id, []).append(task)
    for number, criterion in enumerate(plan.criteria, start=1):
        tasks = by_criterion.get(criterion.id, [])
        points = sum(t.weight for t in tasks)
        print(f"Criterion {number} · {criterion.title}  [{criterion.id}, {len(tasks)} tasks, {points} pts]")
        print(f"  {criterion.description}")
        for task in tasks:
            print(f"   - ({task.weight}) {task.title}")
            print(f"         done when: {task.done_when}")
        print()

    # --- Checks against what the app needs ------------------------------------------------
    criterion_ids = [c.id for c in plan.criteria]
    unknown = sorted({t.criterion_id for t in plan.tasks} - set(criterion_ids))
    uncovered = [c.title for c in plan.criteria if not by_criterion.get(c.id)]
    checks = [
        ("usable is true", plan.usable),
        ("at least one criterion", len(plan.criteria) > 0),
        ("criterion ids are c1, c2, … in order", criterion_ids == [f"c{i}" for i in range(1, len(criterion_ids) + 1)]),
        (f"6–15 tasks (got {len(plan.tasks)})", 6 <= len(plan.tasks) <= 15),
        ("weights are 1–5", all(1 <= t.weight <= 5 for t in plan.tasks)),
        (f"every task points to an existing criterion{' (unknown: ' + ', '.join(unknown) + ')' if unknown else ''}", not unknown),
        (f"every criterion has a task{' (missing: ' + ', '.join(uncovered) + ')' if uncovered else ''}", not uncovered),
        ("every task has a title and a 'done when'", all(t.title.strip() and t.done_when.strip() for t in plan.tasks)),
    ]
    print("Checks:")
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")

    # --- Speed, cost and the refusal fallback --------------------------------------------
    usage = response.usage
    cost = usage.input_tokens / 1e6 * PRICE_INPUT + usage.output_tokens / 1e6 * PRICE_OUTPUT
    weights = Counter(t.weight for t in plan.tasks)
    total_points = sum(t.weight for t in plan.tasks)
    fallback_ran = any(getattr(entry, "type", "") == "fallback_message" for entry in (getattr(usage, "iterations", None) or []))
    print("\nRun:")
    print(f"  duration       {seconds:.1f} s")
    print(f"  stop_reason    {response.stop_reason}")
    print(f"  served by      {response.model}{' (fallback model)' if fallback_ran else ''}")
    print(f"  tokens         {usage.input_tokens:,} in / {usage.output_tokens:,} out (output includes thinking)")
    print(f"  estimated cost ${cost:.3f}")
    print(f"  fallbacks      accepted together with parse() ('{ai.FALLBACK_BETA}', fallbacks=\"default\")")
    print(f"  weights        {dict(sorted(weights.items()))} · {total_points} points in total")

    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
