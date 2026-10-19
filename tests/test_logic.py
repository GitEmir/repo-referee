"""Tests for referee/logic.py: the pure functions behind the plan, fairness and progress."""

import itertools

from referee import logic
from referee.ai import Criterion, Plan, PlannedTask


def make_plan(criteria, tasks, usable=True):
    return Plan(
        usable=usable,
        criteria=[Criterion(id=cid, title=title, description=f"About {title}") for cid, title in criteria],
        tasks=[PlannedTask(title=title, done_when="Done.", weight=weight, criterion_id=cid) for title, weight, cid in tasks],
    )


def id_maker(prefix, start=1):
    counter = itertools.count(start)
    return lambda: f"{prefix}{next(counter)}"


# --- Checking Claude's plan --------------------------------------------------------------


def test_plan_without_problems():
    plan = make_plan([("c1", "Data"), ("c2", "Model")], [("Clean", 3, "c1"), ("Train", 4, "c2")])
    assert logic.plan_problems(plan) == []


def test_plan_problems_name_uncovered_criteria():
    plan = make_plan([("c1", "Data"), ("c2", "Model"), ("c3", "Report")], [("Clean", 3, "c1")])
    problems = logic.plan_problems(plan)
    assert len(problems) == 1
    assert "c2 (Model)" in problems[0] and "c3 (Report)" in problems[0]


def test_plan_problems_name_unknown_criteria():
    plan = make_plan([("c1", "Data")], [("Clean", 3, "c1"), ("Deploy", 2, "c9")])
    assert any("c9" in problem for problem in logic.plan_problems(plan))


def test_plan_to_records_numbers_criteria_and_remaps_ids():
    plan = make_plan(
        [("c1", "Business understanding"), ("c2", "Data quality")],
        [("Interview the client", 2, "c1"), ("Clean missing values", 3, "c2"), ("Check outliers", 1, "c2")],
    )
    criteria, tasks = logic.plan_to_records(plan, id_maker("c", 7), id_maker("t", 20))
    assert [(c["id"], c["number"], c["title"]) for c in criteria] == [
        ("c7", 1, "Business understanding"),
        ("c8", 2, "Data quality"),
    ]
    assert [(t["id"], t["criterion_id"], t["weight"]) for t in tasks] == [("t20", "c7", 2), ("t21", "c8", 3), ("t22", "c8", 1)]
    assert all(t["owner_id"] is None and t["issue_number"] is None and t["issue_url"] is None for t in tasks)


def test_plan_to_records_drops_tasks_with_unknown_criteria():
    plan = make_plan([("c1", "Data")], [("Clean", 3, "c1"), ("Deploy", 2, "c9")])
    criteria, tasks = logic.plan_to_records(plan, id_maker("c"), id_maker("t"))
    assert [t["title"] for t in tasks] == ["Clean"]


def test_plan_to_records_skips_duplicate_criterion_ids():
    plan = make_plan([("c1", "Data"), ("c1", "Data again"), ("c2", "Model")], [("Clean", 3, "c1"), ("Train", 2, "c2")])
    criteria, _ = logic.plan_to_records(plan, id_maker("c"), id_maker("t"))
    assert [(c["title"], c["number"]) for c in criteria] == [("Data", 1), ("Model", 2)]


def test_plan_score_prefers_fewer_uncovered_criteria():
    first = make_plan([("c1", "A"), ("c2", "B"), ("c3", "C"), ("c4", "D")],
                      [("x", 1, "c1"), ("y", 1, "c1"), ("z", 1, "c2"), ("w", 1, "c3")])  # 1 uncovered
    second = make_plan([("c1", "A"), ("c2", "B"), ("c3", "C"), ("c4", "D")], [("x", 1, "c1")])  # 3 uncovered
    assert logic.plan_score(first) < logic.plan_score(second)
    covered = make_plan([("c1", "A")], [("x", 1, "c1"), ("y", 1, "c1")])
    fewer = make_plan([("c1", "A")], [("x", 1, "c1")])
    assert logic.plan_score(covered) < logic.plan_score(fewer)  # same coverage: more tasks wins


def test_plan_to_records_keeps_claude_text_within_the_limits():
    plan = make_plan([("c1", "Data")], [("T" * 250, 3, "c1")])
    plan.tasks[0].done_when = "D" * 1500
    _, tasks = logic.plan_to_records(plan, id_maker("c"), id_maker("t"))
    assert len(tasks[0]["title"]) == logic.TITLE_MAX and tasks[0]["title"].endswith("…")
    assert len(tasks[0]["done_when"]) == logic.DONE_WHEN_MAX


def test_issue_marker_round_trip():
    marker = logic.issue_marker("ab12cd34", "t7")
    body = logic.issue_body({"weight": 2, "done_when": "x"}, {"number": 1, "title": "A"}, {"name": "Sara", "github": "sara-dev"}, "main", marker)
    assert body.rstrip().endswith(marker)
    issues = [{"number": 9, "body": body}, {"number": 10, "body": logic.issue_marker("ffff0000", "t7")}, {"number": 11, "body": None}]
    assert logic.adoptable_issues(issues, "ab12cd34") == {"t7": issues[0]}


def test_criteria_without_tasks():
    criteria = [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}]
    tasks = [{"criterion_id": "c2"}]
    assert [c["id"] for c in logic.criteria_without_tasks(criteria, tasks)] == ["c1", "c3"]


# --- Fair share and over-share -------------------------------------------------------------


def team_of(count):
    return [{"id": f"m{i}", "name": name, "github": name.lower()} for i, name in enumerate(["Sara", "Ali", "Noor", "Max", "Lin"][:count], start=1)]


def test_fair_share_whole_number():
    tasks = [{"weight": 5, "owner_id": None} for _ in range(10)]  # 50 points
    share = logic.fair_share(tasks, team_of(5))
    assert share == 10
    assert logic.format_points(share) == "10"


def test_fair_share_with_one_decimal():
    tasks = [{"weight": 5}] * 9 + [{"weight": 2}]  # 47 points / 5 people = 9.4
    assert logic.format_points(logic.fair_share(tasks, team_of(5))) == "9.4"
    assert logic.format_points(10 / 3) == "3.3"
    assert logic.format_points(0) == "0"


def test_fair_share_without_team_is_zero():
    assert logic.fair_share([{"weight": 3}], []) == 0


def test_chosen_points_ignores_tasks_without_a_person():
    team = team_of(2)
    tasks = [{"weight": 3, "owner_id": "m1"}, {"weight": 4, "owner_id": "m1"}, {"weight": 2, "owner_id": None}, {"weight": 1, "owner_id": "m2"}]
    assert logic.chosen_points(tasks, team) == {"m1": 7, "m2": 1}


def test_over_share_heads_up():
    team = team_of(2)
    tasks = [{"weight": 5, "owner_id": "m1"}, {"weight": 5, "owner_id": "m1"}, {"weight": 4, "owner_id": "m1"}, {"weight": 3, "owner_id": None}, {"weight": 3, "owner_id": "m2"}]
    rows = logic.share_rows(tasks, team)  # 20 points / 2 = 10 each
    sara, ali = rows
    assert sara["label"] == "Sara · 14 / 10" and sara["over"] is True
    assert sara["heads_up"] == "Sara is now at 14 / 10. Someone else has room for this task."
    assert ali["label"] == "Ali · 3 / 10" and ali["over"] is False and ali["heads_up"] is None


def test_exactly_the_fair_share_is_not_over():
    assert logic.is_over_share(10, 10.0) is False
    assert logic.is_over_share(10, 9.4) is True


# --- Sending tasks to GitHub -------------------------------------------------------------


def test_tasks_not_ready():
    tasks = [
        {"id": "t1", "title": "Clean", "owner_id": "m1"},
        {"id": "t2", "title": "  ", "owner_id": "m1"},
        {"id": "t3", "title": "Train", "owner_id": None},
    ]
    assert logic.tasks_not_ready(tasks) == {"no_title": ["t2"], "no_person": ["t3"]}


def test_issue_body_follows_the_spec_format():
    task = {"title": "Clean missing values", "done_when": "Missing values are handled and documented.", "weight": 3}
    criterion = {"number": 2, "title": "Data quality"}
    member = {"name": "Sara", "github": "sara-dev"}
    body = logic.issue_body(task, criterion, member, "main")
    assert body.startswith("**Done when:** Missing values are handled and documented.\n\n| | |\n|---|---|\n")
    assert "| Weight | 3 / 5 |" in body
    assert "| Criterion | 2 · Data quality |" in body
    assert "| Chosen by | Sara (@sara-dev) |" in body
    assert body.rstrip().endswith("in a commit on main._")


def test_issue_body_keeps_the_table_intact():
    task = {"title": "x", "done_when": "", "weight": 1}
    body = logic.issue_body(task, {"number": 1, "title": "A | B"}, {"name": "Sam\nLee", "github": "sam"}, "trunk")
    assert r"| Criterion | 1 · A \| B |" in body
    assert "| Chosen by | Sam Lee (@sam) |" in body
    assert "**Done when:** See the title." in body
    assert "commit on trunk" in body


def test_unassignable_message_uses_names_not_pronouns():
    one = logic.unassignable_message([{"name": "Ali", "github": "ali-dev"}])
    assert one == ("Ali (@ali-dev) can't be assigned yet. Ask Ali to accept the repo invitation, "
                   "or send anyway and leave Ali's tasks unassigned for now.")
    two = logic.unassignable_message([{"name": "Ali", "github": "ali-dev"}, {"name": "Noor", "github": "noor-ds"}])
    assert two.startswith("Ali (@ali-dev) and Noor (@noor-ds) can't be assigned yet. Ask Ali and Noor")
    for word in (" he ", " she ", " his ", " her "):
        assert word not in f" {one} {two} "


# --- Status, progress and contribution ----------------------------------------------------


def issue(number, state="open", reason=None, closed_at=None):
    return {"number": number, "state": state, "state_reason": reason, "closed_at": closed_at, "html_url": f"u{number}"}


def test_task_status_mapping():
    by_number = {
        1: issue(1),
        2: issue(2, "closed", "completed"),
        3: issue(3, "closed", "not_planned"),
        4: issue(4, "closed", "duplicate"),
        5: issue(5, "open", "reopened"),
        6: issue(6, "closed", None),
    }
    expected = {1: "open", 2: "done", 3: "dropped", 4: "dropped", 5: "open", 6: "done", 7: "missing"}
    for number, state in expected.items():
        assert logic.task_status({"issue_number": number}, by_number) == state, number
    assert logic.task_status({"issue_number": None}, by_number) == "missing"


def sample_board():
    criteria = [
        {"id": "c1", "number": 1, "title": "Data"},
        {"id": "c2", "number": 2, "title": "Model"},
        {"id": "c3", "number": 3, "title": "Report"},
    ]
    tasks = [
        {"id": "t1", "title": "Clean", "weight": 3, "criterion_id": "c1", "owner_id": "m1", "issue_number": 1, "issue_url": "u1"},
        {"id": "t2", "title": "Outliers", "weight": 2, "criterion_id": "c1", "owner_id": "m2", "issue_number": 2, "issue_url": "u2"},
        {"id": "t3", "title": "Train", "weight": 4, "criterion_id": "c2", "owner_id": "m1", "issue_number": 3, "issue_url": "u3"},
        {"id": "t4", "title": "Tune", "weight": 1, "criterion_id": "c2", "owner_id": "m2", "issue_number": 4, "issue_url": "u4"},
        {"id": "t5", "title": "Old idea", "weight": 5, "criterion_id": "c2", "owner_id": "m1", "issue_number": 5, "issue_url": "u5"},
    ]
    team = [{"id": "m1", "name": "Sara", "github": "sara-dev"}, {"id": "m2", "name": "Ali", "github": "ali-dev"}]
    issues = [issue(1, "closed", "completed"), issue(2), issue(3, "closed", "completed"), issue(4), issue(5, "closed", "not_planned")]
    return criteria, tasks, team, issues


def test_progress_per_criterion_leaves_dropped_tasks_out():
    criteria, tasks, team, issues = sample_board()
    rows = logic.criterion_progress(criteria, tasks, logic.statuses(tasks, issues))
    assert [(r["done_points"], r["total_points"], r["percent"]) for r in rows] == [(3, 5, 60), (4, 5, 80), (0, 0, None)]
    assert rows[1]["tasks_total"] == 2


def test_totals():
    criteria, tasks, team, issues = sample_board()
    result = logic.totals(tasks, logic.statuses(tasks, issues))
    assert result == {"done_points": 7, "total_points": 10, "percent": 70, "tasks_closed": 2, "tasks_total": 4, "tasks_dropped": 1}


def test_percent_rounds_half_up_and_handles_zero():
    assert logic.percent(1, 8) == 13  # 12.5 rounds up
    assert logic.percent(5, 8) == 63  # 62.5 rounds up
    assert logic.percent(2, 3) == 67
    assert logic.percent(0, 0) is None


def test_contribution_counts_done_weights_and_skips_dropped():
    criteria, tasks, team, issues = sample_board()
    sara, ali = logic.contribution(team, tasks, logic.statuses(tasks, issues))
    assert sara["done_points"] == 7 and sara["chosen_points"] == 7
    assert [t["issue_number"] for t in sara["tasks"]] == [1, 3]  # #5 was dropped
    assert [t["state"] for t in ali["tasks"]] == ["open", "open"]
    assert ali["done_points"] == 0


def test_missing_issue_counts_as_open():
    criteria, tasks, team, issues = sample_board()
    status = logic.statuses(tasks, issues[1:])  # issue #1 deleted
    assert status["t1"] == "missing"
    assert logic.criterion_progress(criteria, tasks, status)[0]["total_points"] == 5
    assert logic.totals(tasks, status)["tasks_closed"] == 1


def test_reopened_issue_is_open_again():
    criteria, tasks, team, issues = sample_board()
    issues[0] = issue(1, "open", "reopened")
    assert logic.statuses(tasks, issues)["t1"] == "open"


# --- Feedback rules -----------------------------------------------------------------------


def board(task_specs, team_size=3):
    """task_specs: (task id, criterion id, owner, weight, state, closed_at) tuples."""
    criteria = [{"id": "c1", "number": 1, "title": "Data quality"},
                {"id": "c2", "number": 2, "title": "Modelling"},
                {"id": "c3", "number": 3, "title": "Report"}]
    tasks = [{"id": tid, "criterion_id": cid, "owner_id": owner, "weight": weight, "title": tid}
             for tid, cid, owner, weight, _, _ in task_specs]
    status = {tid: state for tid, _, _, _, state, _ in task_specs}
    closed_at = {tid: at for tid, _, _, _, _, at in task_specs if at}
    return criteria, tasks, team_of(team_size), status, closed_at


def test_feedback_nothing_closed_yet():
    args = board([("t1", "c1", "m1", 3, "open", None), ("t2", "c2", "m2", 2, "open", None)])
    assert logic.feedback(*args) == [{"kind": "info", "text": logic.NOTHING_CLOSED}]


def test_feedback_dropped_only_still_counts_as_nothing_closed():
    args = board([("t1", "c1", "m1", 3, "dropped", "2026-10-20T10:00:00Z"), ("t2", "c2", "m2", 2, "open", None)])
    assert logic.feedback(*args)[0]["text"] == logic.NOTHING_CLOSED


def test_feedback_celebrates_a_complete_criterion():
    args = board([
        ("t1", "c1", "m1", 3, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c1", "m2", 2, "done", "2026-10-20T11:00:00Z"),
        ("t3", "c2", "m2", 5, "open", None),
        ("t4", "c2", "m1", 5, "open", None),
    ])
    messages = logic.feedback(*args)
    assert messages[0] == {"kind": "celebration", "text": "Criterion 1 · Data quality is complete! 🎉"}


def test_feedback_dropped_tasks_dont_block_a_celebration():
    args = board([
        ("t1", "c1", "m1", 3, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c1", "m2", 2, "dropped", "2026-10-20T11:00:00Z"),
        ("t3", "c2", "m2", 5, "open", None),
    ])
    assert logic.feedback(*args)[0]["kind"] == "celebration"


def test_feedback_newest_completion_first():
    args = board([
        ("t1", "c1", "m1", 1, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c2", "m2", 1, "done", "2026-10-21T09:00:00Z"),
        ("t3", "c3", "m3", 9, "open", None),
    ])
    texts = [m["text"] for m in logic.feedback(*args) if m["kind"] == "celebration"]
    assert texts == ["Criterion 2 · Modelling is complete! 🎉", "Criterion 1 · Data quality is complete! 🎉"]


def test_feedback_balance_tip_at_80_percent():
    args = board([
        ("t1", "c1", "m1", 4, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c1", "m1", 1, "open", None),  # Sara: 4 of 5 points = 80%
        ("t3", "c2", "m2", 5, "open", None),
        ("t4", "c3", "m3", 2, "open", None),
    ])
    tips = [m["text"] for m in logic.feedback(*args) if m["kind"] == "tip"]
    assert tips == ["Sara is almost done with their tasks. Modelling has the most open work — maybe Sara can help out there?"]


def test_feedback_no_tip_just_below_80_percent():
    args = board([
        ("t1", "c1", "m1", 3, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c1", "m1", 1, "open", None),  # 3 of 4 = 75%
        ("t3", "c2", "m2", 5, "open", None),
    ])
    assert logic.feedback(*args) == [{"kind": "info", "text": logic.STEADY}]


def test_feedback_finished_all_tasks_and_no_tip_without_tasks():
    args = board([
        ("t1", "c2", "m1", 2, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c1", "m2", 5, "open", None),
        ("t3", "c2", "m2", 1, "open", None),
    ], team_size=3)  # Noor (m3) chose nothing and never gets the tip
    tips = [m["text"] for m in logic.feedback(*args) if m["kind"] == "tip"]
    assert tips == ["Sara has finished all their tasks! Data quality has the most open work — maybe Sara can help out there?"]


def test_feedback_busiest_tie_goes_to_the_first_criterion():
    args = board([
        ("t1", "c3", "m1", 2, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c1", "m2", 3, "open", None),
        ("t3", "c2", "m3", 3, "open", None),
    ])
    tip = [m["text"] for m in logic.feedback(*args) if m["kind"] == "tip"][0]
    assert "Data quality has the most open work" in tip


def test_feedback_no_tip_when_everything_is_done():
    args = board([
        ("t1", "c1", "m1", 2, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c2", "m2", 2, "done", "2026-10-20T11:00:00Z"),
    ])
    assert [m["kind"] for m in logic.feedback(*args)] == ["celebration", "celebration"]


def test_feedback_shows_at_most_three_messages_celebrations_first():
    args = board([
        ("t1", "c1", "m1", 1, "done", "2026-10-20T10:00:00Z"),
        ("t2", "c2", "m2", 1, "done", "2026-10-20T11:00:00Z"),
        ("t3", "c3", "m3", 1, "open", None),
        ("t4", "c3", "m1", 1, "done", "2026-10-20T12:00:00Z"),
        ("t5", "c3", "m2", 1, "done", "2026-10-20T13:00:00Z"),
    ])
    messages = logic.feedback(*args)
    assert len(messages) == 3
    assert [m["kind"] for m in messages] == ["celebration", "celebration", "tip"]


def test_feedback_never_uses_gendered_pronouns():
    args = board([("t1", "c1", "m1", 4, "done", "2026-10-20T10:00:00Z"), ("t2", "c2", "m2", 5, "open", None)])
    for message in logic.feedback(*args):
        for word in (" he ", " she ", " his ", " her ", " him "):
            assert word not in f" {message['text']} "


# --- Weekly summary window ----------------------------------------------------------------


def test_closed_this_week_window():
    from datetime import datetime, timezone

    now = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
    criteria = [{"id": "c1", "number": 1, "title": "Data quality"}]
    team = team_of(2)
    tasks = [{"id": f"t{i}", "title": f"Task {i}", "weight": i, "criterion_id": "c1", "owner_id": "m1" if i % 2 else "m2"} for i in range(1, 7)]
    status = {"t1": "done", "t2": "done", "t3": "done", "t4": "open", "t5": "dropped", "t6": "done"}
    closed_at = {
        "t1": "2026-10-20T13:59:00Z",  # an hour ago
        "t2": "2026-10-13T14:00:00Z",  # exactly 7 x 24 hours ago: still in
        "t3": "2026-10-13T13:59:00Z",  # just outside the window
        "t5": "2026-10-19T10:00:00Z",  # dropped: not done
        "t6": None,                    # no close date
    }
    rows = logic.closed_this_week(criteria, tasks, team, status, closed_at, now)
    assert [row["title"] for row in rows] == ["Task 2", "Task 1"]
    assert rows[1] == {"title": "Task 1", "criterion": "1 · Data quality", "weight": 1, "person": "Sara", "closed_at": "2026-10-20"}


def test_period_label():
    from datetime import datetime, timezone

    start, end = logic.weekly_window(datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc))
    assert logic.period_label(start, end) == "13 Oct – 20 Oct 2026"


def test_dropped_note():
    assert logic.dropped_note(0) is None
    assert logic.dropped_note(1) == "1 task was closed as not planned or duplicate and isn't counted."
    assert logic.dropped_note(3) == "3 tasks were closed as not planned or duplicate and aren't counted."
