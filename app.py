"""Repo Referee web app: the page routes and a small JSON API.

Routes only read and save through referee/store.py and call the other referee
modules; the business logic lives there.
"""

import os
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from referee import ai, github_client, logic, store

load_dotenv()

app = Flask(__name__)
# Only answer requests addressed to this laptop, so another website can't reach the app
# through a look-alike domain (DNS rebinding).
app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost"]

SETUP_STEPS = [
    {"number": 1, "title": "Create project", "endpoint": "setup_project"},
    {"number": 2, "title": "Team members", "endpoint": "setup_team"},
    {"number": 3, "title": "Paste assignment", "endpoint": "setup_assignment"},
    {"number": 4, "title": "Connect repo", "endpoint": "setup_repo"},
    {"number": 5, "title": "Review tasks", "endpoint": "setup_review"},
]

PROJECT_NAME_MAX = 80
MEMBER_NAME_MAX = 60
# GitHub usernames: letters, numbers and single hyphens, not at the start or end, at most 39.
GITHUB_USERNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")


# Held while the issues are being created, so nothing else changes the project meanwhile.
_send_lock = threading.Lock()
SENDING_NOW = "The tasks are being sent to GitHub right now. Try again in a moment."


@app.before_request
def refuse_cross_site_writes():
    """Check the Host header, and refuse changes that another website tries to make."""
    request.host  # noqa: B018 - raises 400 when the host isn't in TRUSTED_HOSTS
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        abort(403)
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc != request.host:
        abort(403)
    if _send_lock.locked() and request.endpoint != "send_tasks":
        return jsonify({"error": SENDING_NOW}), 409
    return None


# --- Which step are we on? -------------------------------------------------------------


def current_step(project: dict | None) -> int | None:
    """The first setup step whose data is missing, or None once the tasks are sent."""
    if not project or not project.get("project", {}).get("name"):
        return 1
    if project.get("sent_at"):
        return None
    if not project.get("team"):
        return 2
    if not project.get("tasks"):
        return 3
    if not project.get("repo"):
        return 4
    return 5


def sending_started(project: dict | None) -> bool:
    """True when some tasks are already issues in GitHub but sending hasn't finished.

    From then on the team, the tasks and the repo can't change any more: that would
    leave issues behind in GitHub or create them twice.
    """
    return bool(project and not project.get("sent_at") and any(task.get("issue_number") for task in project.get("tasks", [])))


def step_url(number: int | None) -> str:
    return url_for("dashboard") if number is None else url_for(SETUP_STEPS[number - 1]["endpoint"])


def open_step(number: int):
    """Load the project and check that setup step `number` may be shown.

    Returns (project, None) when it may, or (project, redirect) when an earlier step
    still needs data, the tasks were already sent, or sending has started.
    """
    project = store.load()
    step = current_step(project)
    if step is None or number > step:
        return project, redirect(step_url(step))
    if number < 5 and sending_started(project):
        return project, redirect(step_url(5))
    return project, None


def render_step(template: str, number: int, project: dict | None, status: int = 200, **context):
    page = render_template(
        template,
        project=project,
        steps=SETUP_STEPS,
        step=number,
        reachable=current_step(project) or len(SETUP_STEPS),
        steps_locked=sending_started(project),
        **context,
    )
    return page, status


def clean_text(value: str | None) -> str:
    """Trim the text and collapse runs of whitespace into single spaces."""
    return " ".join((value or "").split())


# --- Pages -----------------------------------------------------------------------------


def where_label(project: dict | None) -> str:
    """Where a project stands, for the start page: its setup step, or its repo once sent."""
    step = current_step(project)
    if step is None:
        return f"Tasks in GitHub · {project['repo']['full_name']}" if project.get("repo") else "Tasks in GitHub"
    return f"Step {step} of {len(SETUP_STEPS)} · {SETUP_STEPS[step - 1]['title']}"


STEP_ICONS = {1: "pencil", 2: "users", 3: "clipboard-text", 4: "plug-connected", 5: "list-check"}


def tile_info(project: dict) -> dict:
    """What a project tile on the start page shows: an icon and one number on its colored
    cover (the tasks in GitHub, or the step it's at), and one line under the name."""
    step = current_step(project)
    tasks = len(project.get("tasks") or [])
    people = len(project.get("team") or [])
    people_text = f"{people} {'person' if people == 1 else 'people'}" if people else "No team yet"
    if step is None:
        return {"icon": "brand-github", "number": tasks, "label": "tasks in GitHub",
                "meta": project["repo"]["full_name"] if project.get("repo") else people_text}
    meta = people_text + (f" · {tasks} {'task' if tasks == 1 else 'tasks'}" if tasks else "")
    return {"icon": STEP_ICONS[step], "number": f"{step}/{len(SETUP_STEPS)}",
            "label": SETUP_STEPS[step - 1]["title"], "meta": meta}


def render_home(status: int = 200, **context):
    """The start page: what Repo Referee does, then the first question, "Continue your
    project", or, when signed in, "Your projects" with a new project form."""
    profile = store.signed_in()
    project = store.load()
    my_projects = [
        {"key": p["project"]["key"], "name": p["project"]["name"], **tile_info(p),
         "is_open": bool(project and p["project"]["key"] == project["project"]["key"])}
        for p in store.projects_of(profile["id"])
    ] if profile else []
    page = render_template(
        "home.html", project=project, profile=profile, my_projects=my_projects,
        has_project=bool(project and project.get("project", {}).get("name")),
        continue_url=step_url(current_step(project)), where=where_label(project) if project else "",
        **context,
    )
    return page, status


@app.get("/")
def index():
    return render_home()


# --- Profiles and projects ---------------------------------------------------------------
#
# A profile is a name and a GitHub username, without a password: everything stays on this
# laptop. It lets you save projects, find them again under "Your projects" and start more.

PROFILE_NAME_MAX = 60


@app.context_processor
def account_context():
    """What the header needs on every page: who is signed in, and whether there's a project to save."""
    open_project = store.load()
    return {"account": {
        "profile": store.signed_in(),
        "can_save": bool(open_project and open_project["project"].get("name") and not open_project.get("owner_profile")),
        "has_profiles": bool(store.profiles()),
    }}


def safe_next(target: str | None) -> str:
    """Only ever go back to a page of this app after saving or signing in."""
    return target if target and target.startswith("/") and not target.startswith("//") else url_for("index")


@app.route("/account/save", methods=["GET", "POST"])
def save_project():
    """Save the open project by creating a profile, or by signing in to an existing one."""
    project = store.load()
    if store.signed_in() or not project:
        return redirect(url_for("index"))
    next_url = safe_next(request.values.get("next"))
    owner = github_client.token_owner()
    login = (owner or {}).get("login") or ""
    on_team = next((m for m in project["team"] if login and m["github"].lower() == login.lower()), None)
    form = {"name": (on_team or {}).get("name") or (owner or {}).get("name") or "", "github": login}
    error = error_field = None
    if request.method == "POST":
        form = {"name": clean_text(request.form.get("name")), "github": normalize_github(request.form.get("github"))}
        if not form["name"]:
            error, error_field = "Add your name for the profile.", "name"
        elif len(form["name"]) > PROFILE_NAME_MAX:
            error, error_field = f"Keep the name under {PROFILE_NAME_MAX} characters.", "name"
        elif form["github"] and not GITHUB_USERNAME.fullmatch(form["github"]):
            error, error_field = "That doesn't look like a GitHub username.", "github"
        else:
            profile = store.create_profile(form["name"], form["github"])
            store.sign_in(profile["id"])
            return redirect(next_url)
    page = render_template("account_save.html", project=project, form=form, error=error, error_field=error_field,
                           next_url=next_url, profiles=store.profiles(), token_login=login)
    return page, 400 if error else 200


@app.get("/signin")
def signin():
    """"Welcome back": pick your profile to see your projects again."""
    if store.signed_in() or not store.profiles():
        return redirect(url_for("index"))
    return render_template("signin.html", project=store.load(), profiles=store.profiles(),
                           next_url=safe_next(request.args.get("next")))


@app.post("/signin/<profile_id>")
def signin_as(profile_id: str):
    if store.sign_in(profile_id) is None:
        abort(404)
    return redirect(safe_next(request.form.get("next")))


@app.post("/signout")
def signout():
    store.sign_out()
    return redirect(url_for("index"))


@app.post("/projects/new")
def start_project():
    """"New project": close the open project (it stays under "Your projects") and go to the
    first question, just like the first time you open the app."""
    if store.signed_in():
        store.close_project()
    return redirect(url_for("setup_project") if store.load() is None else url_for("index"))


SAMPLE_PROJECT_NAME = "Campus Room Booking – Assignment 3"


@app.post("/projects/sample")
def start_sample_project():
    """"Start from an example": a new project with the fictional sample assignment filled in."""
    profile = store.signed_in()
    if profile:
        store.close_project()
    elif store.load() is not None:
        return redirect(url_for("index"))  # never replace a project that isn't saved to a profile
    if not SAMPLE_ASSIGNMENT.exists():
        abort(404)
    project = store.new_project(SAMPLE_PROJECT_NAME, profile["id"] if profile else None)
    project["assignment_text"] = SAMPLE_ASSIGNMENT.read_text(encoding="utf-8").strip()
    store.save(project)
    return redirect(url_for("setup_team"))


@app.post("/reset-demo")
def reset_demo():
    """"Reset demo" in the footer: archive all profiles and projects and start as a first-time
    visitor. Handy between demo takes; the issues in GitHub stay."""
    store.reset_all()
    return redirect(url_for("index"))


@app.post("/projects/<key>/open")
def open_saved_project(key: str):
    profile = store.signed_in()
    if not profile or store.open_project(key, profile["id"]) is None:
        abort(404)
    return redirect(step_url(current_step(store.load())))


@app.post("/projects/<key>/delete")
def delete_saved_project(key: str):
    """Delete a project from "Your projects" (it moves into data/archive/; GitHub isn't touched)."""
    profile = store.signed_in()
    if not profile or store.delete_project(key, profile["id"]) is None:
        abort(404)
    return redirect(url_for("index"))


@app.route("/setup/project", methods=["GET", "POST"])
def setup_project():
    project, blocked = open_step(1)
    if blocked:
        return blocked

    name = project["project"]["name"] if project else ""
    error = None
    if request.method == "POST":
        name = clean_text(request.form.get("name"))
        if not name:
            error = "Give your project a name to start."
        elif len(name) > PROJECT_NAME_MAX:
            error = f"Keep the name under {PROJECT_NAME_MAX} characters."
        else:
            with store.update() as saved:
                if saved is None:
                    # Signed in: the new project is saved to the profile right away.
                    profile = store.signed_in()
                    store.save(store.new_project(name, profile["id"] if profile else None))
                else:
                    saved["project"]["name"] = name
                    saved["project"]["created_at"] = saved["project"].get("created_at") or store.now_iso()
            return redirect(url_for("setup_team"))

    return render_step("setup_project.html", 1, project, 400 if error else 200, name=name, error=error)


def self_suggestion(project: dict) -> dict | None:
    """The owner of the GitHub token as a suggested team member, unless they're on the team."""
    owner = github_client.token_owner()
    if not owner or any(member["github"].lower() == owner["login"].lower() for member in project["team"]):
        return None
    profile = store.signed_in()
    is_profile = bool(profile and (profile.get("github") or "").lower() == owner["login"].lower())
    return {"login": owner["login"], "name": profile["name"] if is_profile else owner["name"]}


@app.get("/setup/team")
def setup_team():
    project, blocked = open_step(2)
    if blocked:
        return blocked
    return render_step("setup_team.html", 2, project, form={"name": "", "github": ""}, error=None, error_field=None,
                       suggestion=self_suggestion(project))


def normalize_github(value: str | None) -> str:
    """Trim the username and drop a pasted @ in front of it."""
    return (value or "").strip().lstrip("@").strip()


def member_error(name: str, github: str, team: list[dict]) -> tuple[str, str] | None:
    """(field, friendly message) when the new member can't be added, otherwise None."""
    if not name:
        return "name", "Add a name for this team member."
    if len(name) > MEMBER_NAME_MAX:
        return "name", f"Keep the name under {MEMBER_NAME_MAX} characters."
    if not github:
        return "github", f"Add {name}'s GitHub username, so their tasks can be assigned to them."
    if not GITHUB_USERNAME.fullmatch(github):
        return "github", (
            "That doesn't look like a GitHub username. It can only contain letters, "
            "numbers and single hyphens, and is at most 39 characters long."
        )
    if any(member["github"].lower() == github.lower() for member in team):
        return "github", f"@{github} is already on the team."
    return None


@app.post("/setup/team/add")
def add_member():
    project, blocked = open_step(2)
    if blocked:
        return blocked

    name = clean_text(request.form.get("name"))
    github = normalize_github(request.form.get("github"))
    with store.update() as saved:
        project = saved
        problem = member_error(name, github, saved["team"])
        if not problem:
            member_id = store.next_id(saved, "m", saved["team"])
            saved["team"].append({"id": member_id, "name": name, "github": github})
    if problem:
        field, message = problem
        form = {"name": name, "github": (request.form.get("github") or "").strip()}
        return render_step("setup_team.html", 2, project, 400, form=form, error=message, error_field=field,
                           suggestion=self_suggestion(project))
    return redirect(url_for("setup_team"))


@app.post("/setup/team/remove/<member_id>")
def remove_member(member_id: str):
    project, blocked = open_step(2)
    if blocked:
        return blocked

    with store.update() as saved:
        saved["team"] = [member for member in saved["team"] if member["id"] != member_id]
        # Tasks this person had chosen go back to having nobody.
        for task in saved["tasks"]:
            if task.get("owner_id") == member_id:
                task["owner_id"] = None
    return redirect(url_for("setup_team"))


ASSIGNMENT_MAX = 60_000  # characters; a long assignment is a few thousand
SAMPLE_ASSIGNMENT = Path(app.root_path) / "samples" / "assignment-room-booking.md"
NO_CRITERIA_MESSAGE = (
    "We couldn't find grading criteria in this text. "
    "Paste the assignment together with its grading criteria and try again."
)
GENERATION_FAILED_MESSAGE = "Generating tasks didn't work this time. Your text is saved — try again."


@app.route("/setup/assignment", methods=["GET", "POST"])
def setup_assignment():
    project, blocked = open_step(3)
    if blocked:
        return blocked

    def page(text: str, status: int = 200, **context):
        return render_step("setup_assignment.html", 3, project, status, text=text,
                           has_tasks=bool(project["tasks"]), **context)

    if request.method == "GET":
        text = project["assignment_text"]
        # "Use the sample assignment": fill in the fictional sample; nothing is sent until Generate.
        if request.args.get("sample") == "1" and not text.strip() and SAMPLE_ASSIGNMENT.exists():
            text = SAMPLE_ASSIGNMENT.read_text(encoding="utf-8").strip()
        return page(text)

    text = (request.form.get("assignment") or "").strip()
    if len(text) > ASSIGNMENT_MAX:
        return page(text, 400, error="too_long",
                    message=f"This text is longer than {ASSIGNMENT_MAX:,} characters. Paste only the assignment and its grading criteria.")
    if project["tasks"] and request.form.get("confirm_replace") != "yes":
        return page(text, confirm_replace=True)

    # Save the text first, so nothing is lost if Claude fails.
    with store.update() as saved:
        saved["assignment_text"] = text
    if not text:
        return page(text, 400, error="no_criteria", message=NO_CRITERIA_MESSAGE)

    try:
        plan = ai.generate_plan(text)
    except ai.GenerationError as error:
        app.logger.warning("Task generation failed: %s", error)
        return page(text, 502, error="failed", message=GENERATION_FAILED_MESSAGE)
    if not plan.usable or not plan.criteria:
        return page(text, 422, error="no_criteria", message=NO_CRITERIA_MESSAGE)

    problems = logic.plan_problems(plan)
    if problems:
        # One automatic second try, telling Claude exactly what to fix.
        try:
            second = ai.generate_plan(text, feedback=" ".join(problems))
            if second.usable and second.criteria and logic.plan_score(second) < logic.plan_score(plan):
                plan = second
        except ai.GenerationError as error:
            app.logger.warning("Second try for uncovered criteria failed: %s", error)

    with store.update() as saved:
        criteria, tasks = logic.plan_to_records(
            plan,
            new_criterion_id=lambda: store.next_id(saved, "c", saved["criteria"]),
            new_task_id=lambda: store.next_id(saved, "t", saved["tasks"]),
        )
        if tasks:
            saved["criteria"] = criteria
            saved["tasks"] = tasks
    if not tasks:
        return page(text, 502, error="failed", message=GENERATION_FAILED_MESSAGE)
    return redirect(url_for("setup_repo"))


GITHUB_MESSAGES = {
    "missing_token": "Add your GitHub token to .env as GITHUB_TOKEN, then restart the app.",
    "bad_token": "The GitHub token in .env isn't valid. Create a new one and restart the app.",
    "not_found": "We couldn't find that repo, or the token doesn't have access to it.",
    "forbidden": "The GitHub token isn't allowed to do this. Give it access to this repo with the permission “Issues: Read and write”.",
    "rate_limited": "GitHub is limiting requests right now. Wait a few minutes and try again.",
    "unreachable": "We couldn't reach GitHub. Check your internet connection and try again.",
    "issues_disabled": "Issues are turned off for this repo. Turn them on in the repo's settings and try again.",
}


def github_message(error: github_client.GitHubError) -> str:
    return GITHUB_MESSAGES.get(error.kind, "Something went wrong while talking to GitHub. Try again.")


@app.route("/setup/repo", methods=["GET", "POST"])
def setup_repo():
    project, blocked = open_step(4)
    if blocked:
        return blocked

    if request.method == "POST":
        typed = (request.form.get("repo") or "").strip()
        full_name = github_client.parse_repo_name(typed)
        if not full_name:
            return render_step("setup_repo.html", 4, project, 400, typed=typed, error_kind="format",
                               message="That doesn't look like a GitHub repo. Use owner/repo, or paste the repo's link.")
        try:
            info = github_client.check_repo(full_name)
        except github_client.GitHubError as error:
            return render_step("setup_repo.html", 4, project, 400, typed=typed, error_kind=error.kind,
                               message=github_message(error))
        with store.update() as saved:
            saved["repo"] = info
        return redirect(url_for("setup_repo"))

    # With a repo saved, check every teammate again: people may accept the invitation later.
    members, message = [], None
    if project["repo"]:
        try:
            for member in project["team"]:
                assignable = github_client.can_be_assigned(project["repo"]["full_name"], member["github"])
                members.append({**member, "assignable": assignable})
        except github_client.GitHubError as error:
            members, message = [], github_message(error)
    typed = project["repo"]["full_name"] if project["repo"] else ""
    return render_step("setup_repo.html", 4, project, typed=typed, members=members, message=message,
                       error_kind="check" if message else None)


@app.get("/setup/review")
def setup_review():
    project, blocked = open_step(5)
    if blocked:
        return blocked
    groups = [
        {"criterion": criterion, "tasks": [task for task in project["tasks"] if task["criterion_id"] == criterion["id"]]}
        for criterion in project["criteria"]
    ]
    return render_step(
        "setup_review.html", 5, project,
        groups=groups,
        share_rows=logic.share_rows(project["tasks"], project["team"]),
        total_points=sum(task["weight"] for task in project["tasks"]),
        share=logic.format_points(logic.fair_share(project["tasks"], project["team"])),
    )


# --- JSON API for the review page ------------------------------------------------------

TITLE_MAX = logic.TITLE_MAX
DONE_WHEN_MAX = logic.DONE_WHEN_MAX
ALREADY_IN_GITHUB = "This task is already an issue in GitHub, so it can't change any more."


def api_error(message: str, status: int, **extra):
    return jsonify({"error": message, **extra}), status


@app.put("/api/tasks")
def save_tasks():
    """Autosave from the review page: the full task list, checked before it is saved."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
        return api_error("Send the tasks as {\"tasks\": [...]}.", 400)
    if not payload["tasks"]:
        return api_error("Keep at least one task. Add a new task first, then delete this one.", 400)

    with store.update() as saved:
        step = current_step(saved)
        if step is None:
            return api_error("The tasks were already sent to GitHub, so they can't change any more.", 409)
        if step < 5:
            return api_error(STALE_PAGE, 409)
        existing = {task["id"]: task for task in saved["tasks"]}
        criterion_ids = {criterion["id"] for criterion in saved["criteria"]}
        member_ids = {member["id"] for member in saved["team"]}
        seen = set()
        # Check everything first, so a bad task never leaves a half-saved list behind.
        for item in payload["tasks"]:
            problem = task_problem(item, existing, criterion_ids, member_ids, seen)
            if problem:
                status, message = problem
                return api_error(message, status)
            if item.get("id"):
                seen.add(item["id"])
        # Tasks that are already issues in GitHub must stay, unchanged.
        if any(task.get("issue_number") and task["id"] not in seen for task in saved["tasks"]):
            return api_error(ALREADY_IN_GITHUB, 409)
        cleaned = []
        for item in payload["tasks"]:
            old = existing.get(item.get("id") or "", {})
            cleaned.append({
                "id": old.get("id") or store.next_id(saved, "t", saved["tasks"]),
                "title": " ".join(item.get("title", "").split()),
                "done_when": item.get("done_when", "").strip(),
                "weight": item["weight"],
                "criterion_id": item["criterion_id"],
                "owner_id": item.get("owner_id") or None,
                "issue_number": old.get("issue_number"),
                "issue_url": old.get("issue_url"),
            })
        saved["tasks"] = cleaned
    return jsonify({"ok": True, "tasks": cleaned})


STALE_PAGE = "This page is out of date. Refresh it to see the latest tasks."


def task_problem(item, existing: dict, criterion_ids: set, member_ids: set, seen: set):
    """(status, message) when one task from the review page can't be saved, else None."""
    if not isinstance(item, dict):
        return 400, "Each task must be an object."
    task_id = item.get("id") or None
    if task_id is not None and (not isinstance(task_id, str) or task_id not in existing):
        return 409, STALE_PAGE
    if task_id in seen:
        return 400, "The same task appears twice."
    title, done_when = item.get("title", ""), item.get("done_when", "")
    if not isinstance(title, str) or not isinstance(done_when, str):
        return 400, "Title and “Done when” must be text."
    if len(title) > TITLE_MAX:
        return 400, f"Keep task titles under {TITLE_MAX} characters."
    if len(done_when) > DONE_WHEN_MAX:
        return 400, f"Keep “Done when” under {DONE_WHEN_MAX} characters."
    weight = item.get("weight")
    if isinstance(weight, bool) or not isinstance(weight, int) or not 1 <= weight <= 5:
        return 400, "A task's weight must be a whole number from 1 to 5."
    if item.get("criterion_id") not in criterion_ids:
        return 409, STALE_PAGE
    owner = item.get("owner_id") or None
    if owner is not None and owner not in member_ids:
        return 409, STALE_PAGE
    old = existing.get(task_id) if task_id else None
    if old and old.get("issue_number") and (
        " ".join(title.split()) != old["title"] or done_when.strip() != old["done_when"]
        or weight != old["weight"] or item["criterion_id"] != old["criterion_id"] or owner != old["owner_id"]
    ):
        return 409, ALREADY_IN_GITHUB
    return None


@app.post("/api/send")
def send_tasks():
    """Create one GitHub issue per task. Safe to repeat: tasks that have an issue are skipped."""
    payload = request.get_json(silent=True) or {}
    send_anyway = payload.get("send_anyway") is True
    if not _send_lock.acquire(blocking=False):
        return api_error("The tasks are already being sent.", 409)
    try:
        return _send(send_anyway)
    finally:
        _send_lock.release()


def _send(send_anyway: bool):
    project = store.load()
    step = current_step(project)
    if step is None:
        return jsonify({"ok": True, "redirect": url_for("dashboard")})
    if step < 5:
        return api_error("Finish the earlier setup steps first.", 409, redirect=step_url(step))

    tasks = project["tasks"]
    not_ready = logic.tasks_not_ready(tasks)
    if not_ready["no_title"] or not_ready["no_person"]:
        return api_error("Every task needs a title and a person before sending.", 400, **not_ready)

    repo = project["repo"]
    members = {member["id"]: member for member in project["team"]}
    criteria = {criterion["id"]: criterion for criterion in project["criteria"]}
    project_key = project["project"].get("key")
    if not project_key:  # projects saved before the key existed
        project_key = store.new_key()
        with store.update() as saved:
            saved["project"]["key"] = project_key
    # Every issue links to the view-only board, so teammates can follow everyone's progress.
    team_board = board_link(ensure_share_token())
    to_create = [task for task in tasks if not task.get("issue_number")]
    try:
        # An earlier send may have created an issue whose answer never arrived: adopt
        # those issues by their marker instead of creating them a second time.
        if to_create:
            found = logic.adoptable_issues(github_client.list_referee_issues(repo["full_name"]), project_key)
            adopted = {task["id"]: found[task["id"]] for task in to_create if task["id"] in found}
            if adopted:
                with store.update() as saved:
                    for saved_task in saved["tasks"]:
                        if saved_task["id"] in adopted and not saved_task.get("issue_number"):
                            saved_task["issue_number"] = adopted[saved_task["id"]]["number"]
                            saved_task["issue_url"] = adopted[saved_task["id"]]["html_url"]
                to_create = [task for task in to_create if task["id"] not in adopted]
        owners = {task["owner_id"] for task in to_create}
        unassignable = [members[owner] for owner in members if owner in owners
                        and not github_client.can_be_assigned(repo["full_name"], members[owner]["github"])]
        if unassignable and not send_anyway:
            return jsonify({"needs_confirmation": True, "message": logic.unassignable_message(unassignable),
                            "people": [member["id"] for member in unassignable]}), 409
        github_client.ensure_label(repo["full_name"])
    except github_client.GitHubError as error:
        return api_error(github_message(error), 502)

    skip_assignee = {member["id"] for member in unassignable}
    sent_before = len(tasks) - len(to_create)
    for count, task in enumerate(to_create):
        member = members[task["owner_id"]]
        body = logic.issue_body(task, criteria[task["criterion_id"]], member, repo.get("default_branch") or "main",
                                logic.issue_marker(project_key, task["id"]), board_url=team_board)
        login = None if member["id"] in skip_assignee else member["github"]
        try:
            issue = github_client.create_issue(repo["full_name"], task["title"], body, login)
        except github_client.GitHubError as error:
            app.logger.warning("Creating an issue failed: %s", error)
            sent = sent_before + count
            return api_error(f"Sent {sent} of {len(tasks)} tasks. Something went wrong with the rest — press Send again to continue.",
                             502, sent=sent, total=len(tasks))
        # Save each issue number right away, so a retry never creates a duplicate.
        with store.update() as saved:
            for saved_task in saved["tasks"]:
                if saved_task["id"] == task["id"]:
                    saved_task["issue_number"] = issue["number"]
                    saved_task["issue_url"] = issue["html_url"]
    with store.update() as saved:
        saved["sent_at"] = store.now_iso()
    return jsonify({"ok": True, "redirect": url_for("dashboard")})


def poll_seconds() -> int:
    """How often the dashboard asks for the status (POLL_SECONDS in .env, default 10)."""
    try:
        value = int(os.getenv("POLL_SECONDS", "10"))
    except ValueError:
        value = 10
    return min(max(value, 3), 300)


def ensure_share_token() -> str | None:
    """The open project's view-only board token, made the first time it's needed."""
    with store.update() as saved:
        if saved is None:
            return None
        if not saved.get("share_token"):
            saved["share_token"] = secrets.token_urlsafe(16)
        return saved["share_token"]


def board_link(token: str) -> str:
    """The full address of the view-only board.

    PUBLIC_URL is the app's address once it runs online; without it the link uses the address
    this app answers on now (in the prototype: this laptop).
    """
    base = (os.getenv("PUBLIC_URL") or request.host_url).rstrip("/")
    return base + url_for("shared_board", token=token)


@app.get("/dashboard")
def dashboard():
    project = store.load()
    step = current_step(project)
    if step is not None:
        return redirect(step_url(step))
    return render_template("dashboard.html", project=project, steps=SETUP_STEPS, step="dashboard",
                           reachable=len(SETUP_STEPS) + 1, steps_locked=True, poll_seconds=poll_seconds(),
                           share_link=board_link(ensure_share_token()))


@app.get("/board/<token>")
def shared_board(token: str):
    """The view-only board: anyone with the link sees the live status, but can't change anything."""
    project = store.find_shared(token)
    if project is None or current_step(project) is not None:
        abort(404)
    return render_template("dashboard.html", project=project, viewer=True, scene_name="dashboard",
                           status_url=url_for("shared_status", token=token), poll_seconds=poll_seconds())


@app.get("/api/board/<token>/status")
def shared_status(token: str):
    """The live status for the view-only board (the same answer as /api/status)."""
    project = store.find_shared(token)
    if project is None or current_step(project) is not None:
        return api_error("This board link doesn't work (any more).", 404)
    return status_payload(project)


@app.get("/api/status")
def status():
    """Live status for the dashboard: one GitHub call, combined with what the app saved."""
    project = store.load()
    if current_step(project) is not None:
        return api_error("The tasks haven't been sent to GitHub yet.", 409, redirect=step_url(current_step(project)))
    return status_payload(project)


def status_payload(project: dict):
    try:
        issues = github_client.list_referee_issues(project["repo"]["full_name"])
    except github_client.GitHubError as error:
        return api_error(github_message(error), 502, kind=error.kind)

    tasks = project["tasks"]
    task_status = logic.statuses(tasks, issues)
    totals = logic.totals(tasks, task_status)
    closed_at_by_number = {issue["number"]: issue.get("closed_at") for issue in issues}
    closed_at = {task["id"]: closed_at_by_number.get(task.get("issue_number")) for task in tasks}
    return jsonify({
        "synced_at": store.now_iso(),
        "totals": totals,
        "feedback": logic.feedback(project["criteria"], tasks, project["team"], task_status, closed_at),
        "dropped_note": logic.dropped_note(totals["tasks_dropped"]),
        "criteria": logic.criterion_progress(project["criteria"], tasks, task_status),
        "board": logic.board_cards(project["criteria"], tasks, project["team"], task_status),
        "people": logic.contribution(project["team"], tasks, task_status),
        "summary": project.get("summary"),
    })


SUMMARY_FAILED_MESSAGE = "Writing the summary didn't work this time. Try again."


@app.post("/api/summary")
def summary():
    """Write the weekly summary from the tasks closed in GitHub in the last 7 days."""
    project = store.load()
    if current_step(project) is not None:
        return api_error("The tasks haven't been sent to GitHub yet.", 409)
    try:
        issues = github_client.list_referee_issues(project["repo"]["full_name"])
    except github_client.GitHubError as error:
        return api_error(github_message(error), 502)

    tasks = project["tasks"]
    task_status = logic.statuses(tasks, issues)
    closed_at_by_number = {issue["number"]: issue.get("closed_at") for issue in issues}
    closed_at = {task["id"]: closed_at_by_number.get(task.get("issue_number")) for task in tasks}
    now = datetime.now(timezone.utc)
    start, end = logic.weekly_window(now)
    closed = logic.closed_this_week(project["criteria"], tasks, project["team"], task_status, closed_at, now)
    period = {"period_start": start.date().isoformat(), "period_end": end.date().isoformat(),
              "period_label": logic.period_label(start, end)}
    if not closed:
        # Nothing to summarize: no Claude call, and the last real summary stays saved.
        return jsonify({"summary": None, "message": logic.NO_CLOSED_THIS_WEEK, **period})

    try:
        text = ai.write_summary(project["project"]["name"], closed, period["period_start"], period["period_end"])
    except ai.GenerationError as error:
        app.logger.warning("Weekly summary failed: %s", error)
        return api_error(SUMMARY_FAILED_MESSAGE, 502)

    saved_summary = {"text": text, **period, "written_at": store.now_iso()}
    with store.update() as saved:
        # Claude can take a while: only save when this is still the same project.
        if saved is None or saved["project"].get("key") != project["project"].get("key")                 or saved["project"].get("created_at") != project["project"].get("created_at"):
            return api_error("This project was closed while the summary was being written.", 409)
        saved["summary"] = saved_summary
    return jsonify({"summary": saved_summary})


@app.post("/api/reset")
def reset():
    """"Start a new project". A project saved to a profile just closes and stays under
    "Your projects"; one that isn't saved moves into data/archive/. GitHub is not touched."""
    project = store.load()
    if project and project.get("owner_profile"):
        store.close_project()
    else:
        store.archive()
    return jsonify({"ok": True, "redirect": url_for("setup_project")})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
