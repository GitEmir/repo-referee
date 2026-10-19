"""Pure functions: no network and no files, so they are easy to test with pytest.

All the "is the plan complete, is it fair, how far are we" logic lives here.
"""

import re
from datetime import datetime, timedelta

TITLE_MAX = 200  # characters; the review page and the API use the same limits
DONE_WHEN_MAX = 1000

# --- Checking Claude's plan (setup step 3) ---------------------------------------------


def plan_problems(plan) -> list[str]:
    """What is wrong with a plan from Claude, in words Claude can act on. Empty when fine.

    Checks that every task points to a criterion that exists and that every criterion
    has at least one task. (Weights 1-5 are already guaranteed by the output format.)
    """
    criterion_ids = {criterion.id for criterion in plan.criteria}
    problems = []
    unknown = sorted({task.criterion_id for task in plan.tasks} - criterion_ids)
    if unknown:
        problems.append(f"These tasks point to criteria that don't exist: {', '.join(unknown)}.")
    covered = {task.criterion_id for task in plan.tasks}
    uncovered = [f"{criterion.id} ({criterion.title})" for criterion in plan.criteria if criterion.id not in covered]
    if uncovered:
        problems.append(f"These criteria have no task yet: {', '.join(uncovered)}. Give each of them at least one task.")
    return problems


def plan_score(plan) -> tuple[int, int]:
    """How far a plan is from complete, for picking the better of two answers. Lower is better.

    (criteria without a task + tasks pointing to a missing criterion, minus the number of
    usable tasks as a tie-breaker)
    """
    criterion_ids = {criterion.id for criterion in plan.criteria}
    covered = {task.criterion_id for task in plan.tasks}
    uncovered = sum(1 for criterion in plan.criteria if criterion.id not in covered)
    unknown = sum(1 for task in plan.tasks if task.criterion_id not in criterion_ids)
    usable = len(plan.tasks) - unknown
    return uncovered + unknown, -usable


def _clip(text: str, limit: int) -> str:
    """Keep Claude's text within the limits the review page accepts."""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def plan_to_records(plan, new_criterion_id, new_task_id) -> tuple[list[dict], list[dict]]:
    """Turn Claude's plan into the criteria and tasks saved in project.json.

    Criteria get their position as `number` (1, 2, 3...) and fresh IDs from
    `new_criterion_id()`; tasks get IDs from `new_task_id()`, no person yet and no
    issue yet. Tasks that point to a criterion that doesn't exist are left out.
    """
    criteria = []
    id_map = {}
    for number, criterion in enumerate(plan.criteria, start=1):
        if criterion.id in id_map:
            continue  # a duplicate ID: keep the first criterion with it
        new_id = new_criterion_id()
        id_map[criterion.id] = new_id
        criteria.append({
            "id": new_id,
            "number": len(criteria) + 1,
            "title": criterion.title.strip(),
            "description": criterion.description.strip(),
        })
    tasks = []
    for task in plan.tasks:
        if task.criterion_id not in id_map or not task.title.strip():
            continue
        tasks.append({
            "id": new_task_id(),
            "title": _clip(" ".join(task.title.split()), TITLE_MAX),
            "done_when": _clip(task.done_when.strip(), DONE_WHEN_MAX),
            "weight": int(task.weight),
            "criterion_id": id_map[task.criterion_id],
            "owner_id": None,
            "issue_number": None,
            "issue_url": None,
        })
    return criteria, tasks


def criteria_without_tasks(criteria: list[dict], tasks: list[dict]) -> list[dict]:
    """The criteria that no task points to, in their own order."""
    covered = {task.get("criterion_id") for task in tasks}
    return [criterion for criterion in criteria if criterion["id"] not in covered]


# --- Fair share and over-share (spec.md > Fair Share and Over-Share) --------------------
# review.js does the same sums in the browser, so the bars update on every change.


def fair_share(tasks: list[dict], team: list[dict]) -> float:
    """Total weight of all tasks divided by the number of team members."""
    if not team:
        return 0.0
    return sum(task["weight"] for task in tasks) / len(team)


def format_points(value: float) -> str:
    """Whole numbers as "10", anything else with one decimal, e.g. "9.4"."""
    rounded = round(value, 1)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:.1f}"


def chosen_points(tasks: list[dict], team: list[dict]) -> dict:
    """{member id: sum of the weights of the tasks that person chose}."""
    points = {member["id"]: 0 for member in team}
    for task in tasks:
        if task.get("owner_id") in points:
            points[task["owner_id"]] += task["weight"]
    return points


def is_over_share(points: float, share: float) -> bool:
    """True when someone has chosen more than their fair share (a heads-up, never a block)."""
    return points > share + 1e-9


def share_rows(tasks: list[dict], team: list[dict]) -> list[dict]:
    """One fair-share bar per member: "Sara · 7 / 10", plus the heads-up text when over."""
    share = fair_share(tasks, team)
    chosen = chosen_points(tasks, team)
    rows = []
    for member in team:
        points = chosen[member["id"]]
        over = is_over_share(points, share)
        rows.append({
            "id": member["id"],
            "name": member["name"],
            "chosen": points,
            "share": format_points(share),
            "label": f"{member['name']} · {points} / {format_points(share)}",
            "over": over,
            "heads_up": f"{member['name']} is now at {points} / {format_points(share)}. Someone else has room for this task." if over else None,
        })
    return rows


# --- Sending tasks to GitHub ------------------------------------------------------------


def tasks_not_ready(tasks: list[dict]) -> dict:
    """Tasks that can't be sent yet: {"no_title": [ids], "no_person": [ids]}."""
    return {
        "no_title": [task["id"] for task in tasks if not str(task.get("title") or "").strip()],
        "no_person": [task["id"] for task in tasks if not task.get("owner_id")],
    }


def _cell(text: str) -> str:
    """Make text safe inside one Markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


MARKER = re.compile(r"<!-- repo-referee: ([0-9a-f]+)/(\w+) -->")


def issue_marker(project_key: str, task_id: str) -> str:
    """An invisible comment in the issue body that ties the issue to its task.

    If GitHub created an issue but its answer never arrived, the next "Send" finds the
    issue by this marker instead of creating a duplicate.
    """
    return f"<!-- repo-referee: {project_key}/{task_id} -->"


def adoptable_issues(issues: list[dict], project_key: str) -> dict:
    """{task id: issue} for issues whose body carries this project's marker."""
    found = {}
    for issue in issues:
        match = MARKER.search(issue.get("body") or "")
        if match and match.group(1) == project_key:
            found.setdefault(match.group(2), issue)
    return found


def issue_body(task: dict, criterion: dict, member: dict, default_branch: str = "main", marker: str = "") -> str:
    """The Markdown body of the GitHub issue for one task (see spec.md > Sending Tasks to GitHub)."""
    done_when = str(task.get("done_when") or "").strip() or "See the title."
    body = (
        f"**Done when:** {done_when}\n"
        "\n"
        "| | |\n"
        "|---|---|\n"
        f"| Weight | {int(task['weight'])} / 5 |\n"
        f"| Criterion | {criterion['number']} · {_cell(criterion['title'])} |\n"
        f"| Chosen by | {_cell(member['name'])} (@{member['github']}) |\n"
        "\n"
        "_Created by Repo Referee. Close this issue when the task is done, "
        f"or put \"Closes #\" followed by this issue's number in a commit on {default_branch}._\n"
    )
    return body + (f"\n{marker}\n" if marker else "")


def unassignable_message(people: list[dict]) -> str:
    """The heads-up shown before sending when some people can't be assigned yet."""
    labels = [f"{person['name']} (@{person['github']})" for person in people]
    names = [person["name"] for person in people]
    if len(people) == 1:
        return (
            f"{labels[0]} can't be assigned yet. Ask {names[0]} to accept the repo invitation, "
            f"or send anyway and leave {names[0]}'s tasks unassigned for now."
        )
    return (
        f"{_join(labels)} can't be assigned yet. Ask {_join(names)} to accept the repo invitation, "
        "or send anyway and leave their tasks unassigned for now."
    )


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


# --- Task status from GitHub (spec.md > Task Status from GitHub) ------------------------

DONE = "done"
DROPPED = "dropped"
OPEN = "open"
MISSING = "missing"
DROPPED_REASONS = ("not_planned", "duplicate")


def task_status(task: dict, issues_by_number: dict) -> str:
    """done, dropped, open or missing, read from the task's GitHub issue.

    done: closed as completed, or closed without a reason (older or API-closed issues).
    dropped: closed as not planned or duplicate; left out of every total.
    open: open, including reopened issues.
    missing: the issue isn't in GitHub's list (deleted or transferred); counts as open.
    """
    issue = issues_by_number.get(task.get("issue_number"))
    if issue is None:
        return MISSING
    if issue.get("state") == "closed":
        return DROPPED if issue.get("state_reason") in DROPPED_REASONS else DONE
    return OPEN


def statuses(tasks: list[dict], issues: list[dict]) -> dict:
    """{task id: status} for every task."""
    by_number = {issue["number"]: issue for issue in issues}
    return {task["id"]: task_status(task, by_number) for task in tasks}


def percent(done: int, total: int) -> int | None:
    """Whole-number percentage, rounding halves up; None when there is nothing to count."""
    if total <= 0:
        return None
    return int(done * 100 / total + 0.5)


# --- Progress per criterion (spec.md > Progress per Criterion) ---------------------------


def criterion_progress(criteria: list[dict], tasks: list[dict], status: dict) -> list[dict]:
    """Done points out of total points per criterion, counting only tasks that aren't dropped."""
    rows = []
    for criterion in criteria:
        counted = [t for t in tasks if t["criterion_id"] == criterion["id"] and status.get(t["id"]) != DROPPED]
        done = [t for t in counted if status.get(t["id"]) == DONE]
        done_points = sum(t["weight"] for t in done)
        total_points = sum(t["weight"] for t in counted)
        rows.append({
            "id": criterion["id"],
            "number": criterion["number"],
            "title": criterion["title"],
            "done_points": done_points,
            "total_points": total_points,
            "percent": percent(done_points, total_points),
            "tasks_done": len(done),
            "tasks_total": len(counted),
        })
    return rows


def totals(tasks: list[dict], status: dict) -> dict:
    """The overall line: points and tasks closed, across all tasks that aren't dropped."""
    counted = [t for t in tasks if status.get(t["id"]) != DROPPED]
    done = [t for t in counted if status.get(t["id"]) == DONE]
    done_points = sum(t["weight"] for t in done)
    total_points = sum(t["weight"] for t in counted)
    return {
        "done_points": done_points,
        "total_points": total_points,
        "percent": percent(done_points, total_points),
        "tasks_closed": len(done),
        "tasks_total": len(counted),
        "tasks_dropped": len(tasks) - len(counted),
    }


# --- Contribution per person (spec.md > Contribution per Person) -------------------------


def contribution(team: list[dict], tasks: list[dict], status: dict) -> list[dict]:
    """Per person: points of their done tasks, and one square per counted task they chose."""
    people = []
    for member in team:
        own = [t for t in tasks if t.get("owner_id") == member["id"] and status.get(t["id"]) != DROPPED]
        people.append({
            "id": member["id"],
            "name": member["name"],
            "github": member["github"],
            "done_points": sum(t["weight"] for t in own if status.get(t["id"]) == DONE),
            "chosen_points": sum(t["weight"] for t in own),
            "tasks": [
                {
                    "id": t["id"],
                    "issue_number": t.get("issue_number"),
                    "title": t["title"],
                    "weight": t["weight"],
                    "state": status.get(t["id"], MISSING),
                    "url": t.get("issue_url"),
                }
                for t in own
            ],
        })
    return people


# --- Feedback (spec.md > Feedback Rules) -------------------------------------------------

NOTHING_CLOSED = "Nothing closed yet. Close an issue in GitHub and it shows up here within seconds."
STEADY = "Steady progress. Keep closing issues in GitHub and this dashboard follows along."
MAX_MESSAGES = 3


def feedback(criteria: list[dict], tasks: list[dict], team: list[dict], status: dict, closed_at: dict) -> list[dict]:
    """At most three friendly messages for the top of the dashboard, celebrations first.

    Each message is {"kind": "celebration" | "tip" | "info", "text": ...}. `closed_at` maps
    a task id to its issue's closed_at, so the newest completed criterion comes first.
    """
    counted = [task for task in tasks if status.get(task["id"]) != DROPPED]
    if not any(status.get(task["id"]) == DONE for task in counted):
        return [{"kind": "info", "text": NOTHING_CLOSED}]

    messages = []

    # Celebration: every counted task of a criterion is done. Newest completion first.
    complete = []
    for criterion in criteria:
        own = [task for task in counted if task["criterion_id"] == criterion["id"]]
        if own and all(status.get(task["id"]) == DONE for task in own):
            completed_at = max(closed_at.get(task["id"]) or "" for task in own)
            complete.append((completed_at, criterion))
    complete.sort(key=lambda pair: pair[0], reverse=True)
    for _, criterion in complete:
        messages.append({"kind": "celebration", "text": f"Criterion {criterion['number']} · {criterion['title']} is complete! 🎉"})

    # Team balance tip: someone closed at least 80% of the points they chose, while some
    # criterion still has open work. The busiest criterion has the most open points.
    open_points = {
        criterion["id"]: sum(task["weight"] for task in counted
                             if task["criterion_id"] == criterion["id"] and status.get(task["id"]) != DONE)
        for criterion in criteria
    }
    busiest = max(criteria, key=lambda criterion: open_points[criterion["id"]]) if criteria else None
    if busiest and open_points[busiest["id"]] > 0:
        almost_done = []
        for position, member in enumerate(team):
            own = [task for task in counted if task.get("owner_id") == member["id"]]
            chosen = sum(task["weight"] for task in own)
            done = sum(task["weight"] for task in own if status.get(task["id"]) == DONE)
            if chosen > 0 and done * 5 >= chosen * 4:  # done / chosen >= 80%, without rounding errors
                almost_done.append((-done / chosen, position, member, done == chosen))
        for _, _, member, finished in sorted(almost_done, key=lambda item: (item[0], item[1])):
            name = member["name"]
            opening = f"{name} has finished all their tasks!" if finished else f"{name} is almost done with their tasks."
            messages.append({
                "kind": "tip",
                "text": f"{opening} {busiest['title']} has the most open work — maybe {name} can help out there?",
            })

    if not messages:
        return [{"kind": "info", "text": STEADY}]
    return messages[:MAX_MESSAGES]


# --- Weekly summary input (spec.md > Weekly Summary Input) -------------------------------

SUMMARY_DAYS = 7
NO_CLOSED_THIS_WEEK = "No tasks were closed in the last 7 days yet. Once your team closes issues, this summary fills in."


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def weekly_window(now: datetime) -> tuple[datetime, datetime]:
    """The last 7 x 24 hours, ending now."""
    return now - timedelta(days=SUMMARY_DAYS), now


def period_label(start: datetime, end: datetime) -> str:
    """A short, readable period such as "13 Oct – 20 Oct 2026"."""
    return f"{start.day} {start:%b} – {end.day} {end:%b %Y}"


def closed_this_week(criteria: list[dict], tasks: list[dict], team: list[dict], status: dict,
                     closed_at: dict, now: datetime) -> list[dict]:
    """Done tasks whose issue was closed in the last 7 days, with what the summary needs."""
    start, end = weekly_window(now)
    criteria_by_id = {criterion["id"]: criterion for criterion in criteria}
    names = {member["id"]: member["name"] for member in team}
    rows = []
    for task in tasks:
        closed = _parse_time(closed_at.get(task["id"]))
        if status.get(task["id"]) != DONE or closed is None or not start <= closed <= end:
            continue
        criterion = criteria_by_id.get(task["criterion_id"], {"number": "?", "title": "Unknown"})
        rows.append({
            "title": task["title"],
            "criterion": f"{criterion['number']} · {criterion['title']}",
            "weight": task["weight"],
            "person": names.get(task.get("owner_id"), "Someone"),
            "closed_at": closed.date().isoformat(),
        })
    return sorted(rows, key=lambda row: row["closed_at"])


def dropped_note(count: int) -> str | None:
    """The muted line under the progress section when some tasks were dropped."""
    if count <= 0:
        return None
    if count == 1:
        return "1 task was closed as not planned or duplicate and isn't counted."
    return f"{count} tasks were closed as not planned or duplicate and aren't counted."
