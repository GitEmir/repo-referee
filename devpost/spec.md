---
doc: spec
status: approved
---

# Repo Referee — Technical Spec

## How This Works, In Plain Language

Repo Referee is a small web app that runs on your own laptop. It has two halves.

- **The backend** is a Python program built with Flask. It is the only part that talks to the outside world. It asks Claude to turn the assignment into tasks, it creates and reads issues in GitHub, and it saves the project in one file on your laptop: `data/project.json`.
- **The frontend** is a set of HTML pages, styled with CSS and given a little behavior with JavaScript, shown in your browser. The pages never talk to Claude or GitHub themselves. They ask the backend, and the backend answers with data.

A typical moment: you paste the assignment and press "Generate tasks". The page sends the text to the backend. The backend sends it to Claude with clear instructions and gets back the grading criteria and a list of tasks in a fixed format (JSON). The backend saves that list in `project.json` and shows you the review page.

The dashboard works by **polling**: while it is open, the page asks the backend every 10 seconds, "how are we doing?". The backend asks GitHub which Repo Referee issues are closed, combines that with what it saved (who chose which task, how heavy it is, which criterion it belongs to), calculates progress, contribution and feedback, and sends the result back. The page redraws the bars and squares. Nobody updates anything by hand: whether a task is done is only ever read from GitHub.

Why this shape: one Python program and one data file is the smallest setup that still proves the core idea, "tasks live in GitHub and status updates itself". It runs locally, so the API keys stay in a `.env` file on your laptop, and there is no server, database or login to maintain. The demo video is recorded from this local app.

## The Core Journey Through the System

Implements `prd.md > The Core Journey`.

```
 Browser (HTML/CSS/JS)            Flask backend (Python)                 Outside services
┌──────────────────────┐  HTTP   ┌───────────────────────────┐  HTTPS  ┌──────────────┐
│ setup pages (forms)  │ ──────▶ │ app.py        (routes)    │ ──────▶ │ Claude API   │
│ review.js            │ ◀────── │  ├ referee/ai.py          │ ◀────── └──────────────┘
│ dashboard.js         │  HTML/  │  ├ referee/github_client  │ ──────▶ ┌──────────────┐
│  (asks every 10 s)   │  JSON   │  ├ referee/logic.py (math)│ ◀────── │ GitHub API   │
└──────────────────────┘         │  └ referee/store.py       │         └──────────────┘
                                 └─────────────┬─────────────┘
                                               ▼
                                      data/project.json
```

1. **Open the app.** The browser asks for `/`, the start page. The backend reads `project.json`: no project yet → the start page asks for the project name; a project in progress → "Continue your project" leads to the step you were on, or to the dashboard once the tasks are sent. (`prd.md > States and Boundaries`: first use, coming back.)
2. **Create a project.** The name form posts to `/setup/project`. The store saves the name. (`prd.md > Project Setup`)
3. **Add team members.** Each add or remove posts a small form. The store saves the list right away. (`prd.md > Project Setup`)
4. **Paste the assignment.** The form posts to `/setup/assignment`. The backend saves the text first, so nothing is lost, then calls `ai.generate_plan()`. Claude returns criteria and tasks; the backend checks them and saves them. Meanwhile the page shows a loading state. (`prd.md > Task Generation`)
5. **Connect the repo.** The form posts to `/setup/repo`. The GitHub client checks that the repo exists and that each team member can be assigned, and the page shows the result per person. (`prd.md > The Core Journey` step 4)
6. **Review, edit and choose.** `/setup/review` shows all tasks, which can be edited, added or deleted. `review.js` updates the fair-share bars on every change and saves edits automatically through `PUT /api/tasks`. (`prd.md > Reviewing and Editing Tasks`, `prd.md > Choosing Tasks Fairly`)
7. **Send to GitHub.** `POST /api/send` checks that every task has a person, checks that everyone can be assigned (offering "send anyway" if someone can't be yet), creates one issue per task, saves each issue number, and sends the browser to the dashboard. (`prd.md > Sending Tasks to GitHub`)
8. **Work happens in GitHub.** The team closes issues there, by hand or with a commit message such as "Closes #12" on the default branch.
9. **Dashboard.** `dashboard.js` calls `GET /api/status` on open, every 10 seconds, and whenever the tab comes back into view. The backend makes one GitHub call, `logic.py` turns the result into progress, contribution and feedback, and the page redraws. (`prd.md > Dashboard: Automatic Status`)
10. **Weekly summary.** The button posts to `/api/summary`. The backend collects the tasks closed in the last 7 days and asks Claude for a short summary, which is saved and shown. (`prd.md > Dashboard: Weekly Summary`)
11. **Start over.** "Start a new project" at the bottom of the dashboard asks for confirmation and posts to `/api/reset`. The backend moves `project.json` into `data/archive/` and the browser returns to the start page. The issues stay in GitHub. (`prd.md > Starting Over`)

## Stack

| Piece | Choice | Why, and the accepted tradeoff | Docs |
|---|---|---|---|
| Language | Python 3.12 or newer | The learner's familiar language. | https://docs.python.org/3/ |
| Python runner | `uv` (already installed on the learner's laptop) | Plain `python` is not on the PATH on this laptop: it opens the Microsoft Store. `uv` creates the project's own environment and runs the app without touching Anaconda. Tradeoff: two new commands to learn. The README also documents the plain `pip` route for others. | https://docs.astral.sh/uv/ |
| Web framework | Flask 3 (with its Jinja templates) | Learner accepted the recommendation. It is the simplest way to serve a few pages plus a small JSON API. Tradeoff: no automatic request validation, so the routes check input themselves. | https://flask.palletsprojects.com/en/stable/ |
| Frontend | Plain HTML, CSS and JavaScript, no framework, no build step | The learner's choice. It gives full control over the look, which matters for the Design criterion. Tradeoff: a little hand-written DOM code in two scripts (`review.js`, `dashboard.js`). | https://developer.mozilla.org/en-US/docs/Web |
| AI | Claude API through the official `anthropic` Python SDK, model `claude-opus-5-5`, structured outputs with Pydantic | The learner chose Claude. Opus 5.5 is Anthropic's current default model, and structured outputs return tasks in a guaranteed shape. Tradeoff: paid per call, and one generation can take tens of seconds. The model name is read from `.env`, so it can be swapped without code changes. | https://platform.claude.com/docs/en/build-with-claude/structured-outputs, https://github.com/anthropics/anthropic-sdk-python |
| GitHub | REST API through `requests`, with a fine-grained personal access token | Plain HTTP calls are easy to read and debug, and only five calls are needed. Tradeoff: we write a small client ourselves. | https://docs.github.com/en/rest/issues/issues, https://requests.readthedocs.io/ |
| Storage | One JSON file, `data/project.json` | The learner's choice: simple and readable, and enough for one team and one project. Tradeoff: no multiple projects. | — |
| Configuration | `python-dotenv` reads `.env` | Keeps keys out of the code and out of git. | https://pypi.org/project/python-dotenv/ |
| Tests | `pytest` for the calculation logic | Learner accepted. It tests the math that decides fairness and progress. | https://docs.pytest.org/ |
| Fonts | Plus Jakarta Sans and JetBrains Mono (Google Fonts, Open Font License) | The learner's chosen look. | https://fonts.google.com/specimen/Plus+Jakarta+Sans, https://fonts.google.com/specimen/JetBrains+Mono |
| Icons | Tabler Icons webfont (MIT), outline style | Clean line icons that match the minimal look. | https://tabler.io/icons |

**Not verified yet:** exact library versions were not looked up for this spec. The first build step installs the latest stable versions and pins them in `requirements.txt` (with `uv pip freeze`). The Anthropic SDK needs Python 3.10 or newer, so 3.12+ is safe.

## Where It Runs and How Someone Tries It

**Runtime:** a local Flask server on the learner's Windows 11 laptop, at `http://127.0.0.1:5000`, opened in a normal browser (Chrome or Edge). The server listens only on `127.0.0.1`, so nobody else on the network can use the API keys through it. It needs an internet connection for Claude and GitHub.

**Environment variables** (in `.env`, never committed; `.env.example` shows the names):

```
ANTHROPIC_API_KEY=        # from the Claude Console, with a few dollars of credit
GITHUB_TOKEN=             # fine-grained token: only the test repo, Issues read and write
CLAUDE_MODEL=claude-opus-5-5   # optional
POLL_SECONDS=10                # optional
PUBLIC_URL=                    # optional: the app's address once it runs online, used for the team board link
```

**Start it** (PowerShell, in the project folder):

```
uv venv
uv pip install -r requirements.txt
Copy-Item .env.example .env      # then fill in the two keys
uv run flask --app app run
```

Then open `http://127.0.0.1:5000`. Run the tests with `uv run pytest`.

Without `uv` (for other people's machines): `python -m venv .venv`, `.venv\Scripts\Activate.ps1`, `pip install -r requirements.txt`, `flask --app app run`.

**Start over:** use "Start a new project" at the bottom of the dashboard. It moves the current `project.json` into `data/archive/`, so nothing is permanently deleted, and returns to the start page. The issues already created stay in GitHub. This is also how you reset between demo takes.

**Recording the demo** (required: a public video under 3 minutes, plus the public repository):
- Test repo, for example `<your-account>/repo-referee-demo`, with four invited collaborators who have accepted the invitation. Together with the owner that makes the team of five.
- The fictional demo assignment in `samples/assignment-room-booking.md`: a small coding assignment (a room booking API) with four grading criteria. It replaced the learner's first sample, a data science churn assignment, because the learner wanted a simpler, code-only example; drafted by Claude at the learner's request.
- Two windows side by side: the dashboard, and a GitHub issue. Close the issue, and the dashboard follows within 10 seconds. Switching back to the dashboard tab refreshes it immediately.
- To show "closed by a commit", the commit message must contain "Closes #N" and the commit must land on the default branch (`main`). Closing keywords do nothing on other branches.

**Deployment:** none. The learner chose to run locally and record the video. This can be reconsidered in `6-ship`, but it is not part of the plan.

## Look and Feel

Carries forward `prd.md > Look and Feel`: minimal and clean, light theme, one green accent, GitHub-inspired details, friendliness through words.

**Color tokens** (defined once as CSS custom properties in `static/css/style.css`):

| Token | Value | Used for |
|---|---|---|
| `--bg-page` | `#F6F8FA` | Page background |
| `--bg-card` | `#FFFFFF` | Cards and panels |
| `--border` | `#E7EAF0` | 1px borders (instead of shadows) |
| `--text` | `#1F2328` | Main text |
| `--text-muted` | `#656D76` | Secondary text, captions |
| `--green` | `#2DA44E` | Progress fills, the "synced" dot |
| `--green-strong` | `#1F883D` | Logo mark, links |
| `--celebrate-bg` / `--celebrate-text` | `#DAFBE1` / `#116329` | Celebration messages |
| `--heads-up-bg` / `--heads-up-text` | `#FFF8C5` / `#7D4E00` | Over-share heads-up (friendly, never red) |
| `--error-bg` / `--error-text` | `#FFEBE9` / `#82071E` | Real errors only (AI or GitHub failures) |
| `--button-bg` / `--button-text` | `#1F2328` / `#FFFFFF` | Main buttons (dark, so green keeps meaning "done") |
| `--track` | `#EEF1F5` | Empty part of progress bars |
| `--sq-0` … `--sq-4` | `#EBEDF0`, `#9BE9A8`, `#40C463`, `#30A14E`, `#216E39` | Contribution squares: open task, then done tasks of weight 1, 2, 3, 4–5 |

**Typography:** Plus Jakarta Sans (400, 600, 700) for everything readable. Sizes 13, 15, 18, 24 and 32 px. JetBrains Mono (400, 500) at 12–13 px for GitHub identifiers only: `@username`, `owner/repo`, `#12`, and the "synced 8s ago" line.

**Shape and space:** cards with a 14px radius and 24px padding; buttons, inputs and inner blocks with a 10px radius; bars and pills fully rounded. A spacing scale of 4, 8, 12, 16, 24, 32 and 48 px. Content centered with a maximum width of 880 px. Plenty of white space; borders instead of shadows.

**Backdrop:** behind every page sits a quiet dot grid (like a whiteboard) with soft, flat shapes in pastel colors: eight shapes in all (circles, a rounded square, a pill, a ring, a half circle). They stay in the empty space beside the page: never over the content, the header or the footer (the learner's rule), and on a screen too narrow for that they stay off screen. Every shape keeps to its own side, so it never passes behind the content. Each page shows four of them (two on each side), each on its own spot, and keeps the rest just off screen. So going to another step is a small surprise: some shapes glide to a new spot, some fly out of the screen and new ones fly in, each at its own pace with a small overshoot. On the first page of a visit they fly in. They drift slowly, and the drift keeps one clock across pages, so it carries on instead of restarting.

**Motion:** progress bars animate their width over 400 ms when the status changes, and a square that just turned green "pops" in (300 ms). This is what makes the demo moment visible. When a button or link takes you to another step, the part you work in (the "workspace": the card on steps 1–4, the page content elsewhere) slides out while the next step's workspace slides in, from the side you're heading to (from the right going forward, from the left going back). This is a view transition; the header, step bar and backdrop switch without a fade, so the shapes keep gliding smoothly underneath. Browsers without view transitions get a plain slide-in of the new page. A button that keeps you on the same step (adding a teammate, a message after a mistake) just shows the result, with no transition. The first page of a visit fades up. Animations are switched off for people who set "reduce motion" in their system.

**Layout per screen:** every page shows the logo mark, "Repo Referee" and the project name in the header (`prd.md > Project Setup`: "the name is shown in the app from then on"). Setup pages and the dashboard show a step bar with every step by name (done steps with a green check, the current step dark, the dashboard last; on a phone only the current step keeps its name). The dashboard runs top to bottom in the PRD order: feedback, the board (progress per criterion), weekly summary, contribution per person (`prd.md > Screens and Layout`). The board gives the app a calm, Trello-like feel: white columns with one color per criterion and light task cards.

**Copy rules:** English; sentence case; short verbs on buttons ("Generate tasks", "Send to GitHub", "Write weekly summary"). Supportive coach tone: celebrate, suggest, never blame or name someone as behind. Use people's names, never gendered pronouns, because the app doesn't know anyone's pronouns. The only emoji is the celebration 🎉.

**Avoid:** gradients, purple or indigo "AI" accents, glassmorphism, heavy shadows, and dark mode (light only in the proof of concept).

## Components

### Flask App and Routes (`app.py`)

The entry point. It holds the routes and nothing else: each route reads or saves through `store.py`, calls `ai.py`, `github_client.py` or `logic.py`, and returns a page or JSON.

| Method | Path | What it does | PRD |
|---|---|---|---|
| GET | `/` | The start page: what Repo Referee does and for whom, then the first question (name your project) or, with a project in progress, "Continue your project" to the current step or the dashboard. The name in the header leads here. The page is one calm, centered question, with three cards under it (paste the assignment, pick tasks fairly, watch the board follow GitHub) and the line that there is no extra app to keep up to date by hand. | `States and Boundaries` |
| GET, POST | `/setup/project` | Step 1: name the project | `Project Setup` |
| GET | `/setup/team` | Step 2: the team list | `Project Setup` |
| POST | `/setup/team/add`, `/setup/team/remove/<member_id>` | Add or remove a member | `Project Setup` |
| GET, POST | `/setup/assignment` | Step 3: paste the text, generate tasks | `Task Generation` |
| GET, POST | `/setup/repo` | Step 4: connect and check the repo | `The Core Journey` |
| GET | `/setup/review` | Step 5: review, edit and choose | `Reviewing and Editing Tasks`, `Choosing Tasks Fairly` |
| PUT | `/api/tasks` | Autosave the edited task list (JSON) | `Reviewing and Editing Tasks` |
| POST | `/api/send` | Create the issues; body `{"send_anyway": true}` after the learner confirms | `Sending Tasks to GitHub` |
| GET | `/dashboard` | The dashboard page | `Screens and Layout` |
| GET | `/api/status` | Live status as JSON | `Dashboard: Automatic Status` |
| GET | `/board/<token>` | The view-only board from the shared link: the live dashboard without anything that changes the project | `Sharing the Board (View Only)` |
| GET | `/api/board/<token>/status` | Live status for the view-only board (the same JSON as `/api/status`) | `Sharing the Board (View Only)` |
| POST | `/api/summary` | Write the weekly summary | `Dashboard: Weekly Summary` |
| POST | `/api/reset` | Start a new project: a saved project closes, one that isn't saved is archived | `Starting Over` |
| GET, POST | `/account/save` | "Save your project": create a profile (name, GitHub username suggested from the token) or pick an existing one; the open project is saved to it | `States and Boundaries` |
| GET | `/signin` | "Welcome back": choose your profile | `States and Boundaries` |
| POST | `/signin/<profile_id>`, `/signout` | Sign in to a profile, or sign out | `States and Boundaries` |
| POST | `/projects/new` | "New project" (signed in): close the open project, which stays under "Your projects", and go to the first question, just like the first time | `States and Boundaries` |
| POST | `/projects/sample` | "Start from an example": a new project with the fictional sample assignment filled in, at the team step (never replaces a project that isn't saved) | `States and Boundaries` |
| POST | `/reset-demo` | "Reset demo" in the footer of every page: move all profiles, projects and the state into `data/archive/reset-<date>-<time>/` and start as a first-time visitor (between demo takes); GitHub is not touched | `Starting Over` |
| POST | `/projects/<key>/open` | Open one of your saved projects at its current step | `States and Boundaries` |
| POST | `/projects/<key>/delete` | Delete one of your saved projects ("⋯" on its tile): the file moves into `data/archive/`, an open project is closed; GitHub is not touched | `States and Boundaries` |

**Step rules:**
- The current step is derived from what is saved, so there is no separate "stage" to keep in sync:
  - no project → step 1;
  - no team → step 2;
  - no tasks → step 3;
  - no repo → step 4;
  - not sent → step 5;
  - `sent_at` set → dashboard.
- A setup step can only be opened once the earlier steps have their data. Earlier steps stay reachable through the step indicator until the tasks are sent.
- After sending (`sent_at` is set), all setup routes redirect to the dashboard. The tasks are locked: sending again would duplicate issues, and status comes only from GitHub.
- Removing a team member clears the person on that member's tasks.
- Submitting step 3 again replaces the criteria and tasks, after a confirmation ("This replaces the current tasks").
- The app runs with `host="127.0.0.1"`. Debug mode is on only when `FLASK_DEBUG=1` is set.

### Project Store (`referee/store.py`)

Reads and writes the files in `data/`, the app's only saved state (see `Data Model`). Most of the app works on "the open project".

- `load()` returns the open project, or `None` when none is open (first use, or after "New project"). A `data/project.json` from before there were several projects is moved into `data/projects/` the first time.
- `save(project)` writes the project to its own file and makes it the open project. Every write goes to a temporary file first and then replaces the real file, so a crash never leaves a half-written file. It creates `data/` if needed.
- `archive()` moves the open project to `data/archive/project-<date>-<time>.json` (a project that isn't saved to a profile, on "Start a new project"); `close_project()` just closes a saved one.
- Profiles: `create_profile()`, `sign_in()` (which saves the open project to the profile if it isn't saved yet), `sign_out()` (which closes a saved project), `projects_of(profile)` and `open_project(key, profile)` (only your own projects).
- Every setup action saves immediately. A refresh or restart never loses work (`prd.md > States and Boundaries`: "nothing is lost").
- IDs are short strings: `m1`, `m2` for members, `c1` for criteria, `t1` for tasks.

### Setup Step 1: Create Project

A single name field and a "Start" button, also shown on the start page. An empty name shows "Give your project a name to start." Saves `project.name` and moves on to the team step; when someone is signed in, the new project is saved to their profile right away. Implements `prd.md > Project Setup`.

**Calm cards:** steps 1–4 are one plain, centered card with a soft shadow; no bubbles around it. Step 3 has a quiet "Use the sample assignment" link under the text box, which fills in `samples/assignment-room-booking.md` without calling the AI. Step 5 shows the board without extra labels above it: the learner found the three labels (the AI's first draft, the weight scale, the fair-share sum) and the fair-share sum line unnecessary; the weight scale stays in the tooltips of the weight buttons and each person's share next to their bar. The app never names the AI provider on screen: it says "AI" (the learner's choice).

### Setup Step 2: Team Members

A list with a name field and a GitHub username field, plus "Add". Each row has a remove button. Validation: a name is required, and the GitHub username must look valid (letters, numbers and single hyphens, at most 39 characters; a pasted `@` is stripped). "Continue" appears once there is at least one member. There is no limit on the team size. Implements `prd.md > Project Setup`.

**The live team:** to the right of the card, one face per person (their GitHub picture, with their first letter underneath), no limit and no count, with a plus at the end that jumps to the name field. Next to "GitHub username" a "?" opens a small popover that shows which part of `github.com/<username>` is the username, and that it is not an email or a full name. Under the form a quiet line says people can be added until the tasks are sent.

**Add yourself:** when the GitHub token's owner (`github_client.token_owner()`, `GET /user`) isn't on the team yet, a green box offers "Add yourself" with their GitHub picture and username, and a name field. Avatars use `https://github.com/<username>.png`, with the first letter underneath when the picture can't load.

### Setup Step 3: Paste Assignment and Generate Tasks

A large text area and a "Generate tasks" button. On submit:

1. The text is saved first.
2. The button changes to "Reading your assignment…" and a bar with a countdown appears: "About 20 seconds left", then "Almost there…", then "Taking a bit longer than usual…". The 20 seconds is an estimate from the measured Claude spike (about 21 s); while waiting the bar never reaches 100%, so it never claims to be done. The form is sent in the background (`fetch`), so the page knows when the answer is in: when the tasks are ready (the backend redirects to the next step), the countdown runs down fast and the bar fills to 100% in about 0.7 s ("Done: your tasks are ready") before the next step opens, also when the AI was quicker than the estimate (the learner wanted the bar always to finish). Any other answer (a message on this page, such as "try again" or "this replaces the current tasks") is shown right away. (A little JavaScript, because the page waits for the backend.)
3. The backend calls `ai.generate_plan(text)` (see `AI Module`) and checks the result:
   - every task has a weight from 1 to 5 and a criterion that exists;
   - every criterion has at least one task. If not, it retries once automatically, telling Claude which criteria are uncovered. If that still fails, it saves the result and the review page notes "Criterion 3 doesn't have a task yet."
4. On success: criteria and tasks are saved, and the browser goes to step 4.

The outcomes for `prd.md > States and Boundaries`:
- **No criteria found** (Claude marks the text as not usable, or finds zero criteria): "We couldn't find grading criteria in this text. Paste the assignment together with its grading criteria and try again." Nothing is generated.
- **Empty text:** the same message, without calling Claude.
- **Claude fails, times out or declines:** "Generating tasks didn't work this time. Your text is saved — try again." with a "Try again" button.

Tasks are written in the language of the pasted assignment. The demo assignment is in English. Implements `prd.md > Task Generation`.

### Setup Step 4: Connect Repo

One field that accepts `owner/repo` or a full `https://github.com/owner/repo` link and normalizes it. On submit, `github_client.check_repo()` runs:
- **Found:** the page lists every team member with a check: "can be assigned" (green) or "hasn't accepted the repo invitation yet" (heads-up color). Continuing is allowed, because people may accept later. The check runs again when sending.
- **Token invalid (401):** "The GitHub token in .env isn't valid. Create a new one and restart the app."
- **Not found (404):** "We couldn't find that repo, or the token doesn't have access to it."

Implements `prd.md > The Core Journey` step 4 and `prd.md > States and Boundaries` ("repo can't be reached").

### Setup Step 5: Review, Edit and Choose Tasks

Implements `prd.md > Reviewing and Editing Tasks` and `prd.md > Choosing Tasks Fairly`.

- **How choosing works** (added in the final review, so nobody is thrown in without an explanation; picked from six ideas): a strip above the board with three steps. Check the tasks (change titles and weights, move or add tasks). Pick your tasks (the numbers 1 to 5 are the weight: 1 ≈ an hour, 3 ≈ a day, 5 ≈ several days; the fair share is all points ÷ the team size, so "2 / 6" means 2 of a fair 6 points). Send to GitHub (each task becomes an assigned issue). It is open on a first visit; × closes it and the browser remembers that (`localStorage`), leaving a small "How this works" link that opens it again.
- **Layout: a board.** Changed in the final review so the generated tasks are easier to take in: one column per grading criterion (its color, number, description and "4 tasks · 11 points"), with compact task cards. A card shows the title, the weight as five small buttons and who does it: the person's colored initial and name, or an empty dashed face with "Who?". Clicking that face opens a row of the team's faces on the card, each with their name and points so far against the fair share (in the heads-up color once someone is at their share), plus "No one"; one click picks a person and closes the row (Escape or a click elsewhere closes it too). This replaced a plain dropdown the learner found unattractive (picked from ten page designs). The columns are light grey with white cards, like a board. "Done when", the criterion and delete sit under "Details". The board scrolls sideways when the columns don't fit. The page is the wide layout, with the fair share next to the title.
- **Top: fair-share bars.** One bar per member, "Sara · 7 / 10", with their GitHub picture, using the math in `Calculations > Fair Share and Over-Share`. They update live as people choose tasks.
- **Over-share heads-up** under the bar, in the heads-up color: "Ali is now at 14 / 10. Someone else has room for this task." It never blocks.
- **Tasks grouped by criterion.** Each task card has editable fields:
  - title (text);
  - "Done when" description (text area);
  - weight (1–5, a small segmented control);
  - criterion (dropdown);
  - "Who does this?" (dropdown of members, empty at first).
- **Add task:** an "Add task" button at the end of each criterion group creates an empty task under that criterion (weight 1, no person yet).
- **Delete task:** a delete icon on each card asks inline, "Delete this task?", with Yes and No. The last remaining task can't be deleted: a project keeps at least one task.
- **Empty criterion:** if a criterion ends up without tasks, its group shows "Criterion 3 doesn't have a task yet." This doesn't block sending. On the dashboard that criterion shows "No tasks".
- **Autosave:** `review.js` sends the full task list to `PUT /api/tasks` 500 ms after the last change. The server checks weights (1–5), criterion IDs and member IDs, gives new tasks an ID, then saves. A small "Saved" note confirms it. These saved values are exactly what gets sent to GitHub.
- **The send button** reads "Send 18 tasks to GitHub". It is ready only when every task has a title and a person. Otherwise it looks inactive and reads "3 tasks still need a person" (or "1 task needs a title"). Those tasks are outlined, and clicking the button scrolls to the first one.

### Sending Tasks to GitHub

`POST /api/send`, implementing `prd.md > Sending Tasks to GitHub`:

1. Reload the project. If any task has no title or no person, stop with that list (normally impossible, because the button guards it).
2. For every member who owns tasks, check again that they can be assigned. If someone can't be, stop before creating anything and show: "Ali (@ali-dev) can't be assigned yet. Ask Ali to accept the repo invitation, or send anyway and leave Ali's tasks unassigned for now." It offers two buttons: "Send anyway" and "Wait". "Send anyway" repeats the request with `{"send_anyway": true}`. Issues for those people are then created **without an assignee**; the body still says "Chosen by: Ali (@ali-dev)", and the dashboard still credits Ali, because it uses the app's own record of who chose what.
3. Make sure the label `repo-referee` exists in the repo (create it if missing).
4. For each task without an issue number, in order and one at a time: create the issue, then **save its number and link immediately**.
5. When all are created: save `sent_at` and send the browser to `/dashboard`.

If something fails halfway, the page says "Sent 6 of 18 tasks. Something went wrong with the rest — press Send again to continue." Sending again skips tasks that already have an issue, so there are no duplicates. While sending, the button shows "Sending tasks to GitHub…".

Keeping the app and GitHub in step (added after the build review):
- While issues are being created, the review page is inert and every other change is refused.
- Once some tasks are issues, setup steps 1–4 are locked (no new tasks, repo or team changes), and those tasks show "#12 in GitHub" and can't change or be deleted. The button then reads "Send the remaining 12 tasks to GitHub".
- Each issue body ends with an invisible marker, `<!-- repo-referee: <project key>/<task id> -->`. Before creating issues, the app lists the Repo Referee issues once and adopts any issue that carries a marker for a task without a number. So an issue whose answer from GitHub was lost is not created twice.

**Issue format.** The title is the task title. The body (Markdown):

```
**Done when:** Missing values in the customer table are handled and the choices are documented in the report.

| | |
|---|---|
| Weight | 3 / 5 |
| Criterion | 2 · Data quality |
| Chosen by | Sara (@sara-dev) |

_Created by Repo Referee. Close this issue when the task is done, or put "Closes #<number>" in a commit on main._
```

Assignee: the chosen person's GitHub username. Label: `repo-referee`.

### AI Module (`referee/ai.py`)

The only code that talks to Claude. It exposes two plain functions, so the model or even the provider can be swapped in one place.

```python
def generate_plan(assignment_text: str) -> Plan: ...
def write_summary(project_name: str, closed_tasks: list[dict],
                  period_start: str, period_end: str) -> str: ...
```

**`generate_plan`** uses structured outputs with Pydantic models:

```python
class Criterion(BaseModel):
    id: str            # "c1", "c2", ... in the order they appear in the text
    title: str         # e.g. "Data quality"
    description: str   # one sentence: what the grader looks for

class PlannedTask(BaseModel):
    title: str                      # short, starts with a verb
    done_when: str                  # one or two sentences: what "done" means
    weight: Literal[1, 2, 3, 4, 5]  # 1 ≈ an hour, 3 ≈ a day, 5 ≈ several days
    criterion_id: str

class Plan(BaseModel):
    usable: bool                    # false if the text has no assignment or criteria
    criteria: list[Criterion]
    tasks: list[PlannedTask]
```

```python
response = client.beta.messages.parse(
    model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"),
    max_tokens=16000,
    system=PLAN_INSTRUCTIONS,
    messages=[{"role": "user", "content": assignment_text}],
    output_format=Plan,
    betas=["server-side-fallback-2026-07-01"],
    fallbacks="default",
)
plan = response.parsed_output
```

The instructions (`PLAN_INSTRUCTIONS`) tell Claude to:
- take the grading criteria from the text, keeping their names and order;
- create small, concrete tasks only for this one assignment, with nothing from outside it (`prd.md > Task Generation`);
- make only the tasks the assignment really needs, each a logical piece of work one teammate can pick up: usually 6–15, fewer for a small assignment, never tiny steps (the learner wanted fewer, logical tasks); use the weight scale above;
- link each task to exactly one criterion, and give every criterion at least one task;
- write in the language of the assignment;
- set `usable` to false when the text has no recognizable assignment or criteria.

Effort stays at the model's default (`medium` on Opus 5.5). It changes only if the first spike shows quality or speed problems.

**`write_summary`** is a plain `client.messages.create` call (`max_tokens=8000`). It gets the project name, the period, and the list of tasks closed in that period (title, criterion, weight, person, closed date). It returns 3–6 sentences in English: what the team finished, which criteria moved, credit by name. It is positive, never blaming, and mentions nothing that isn't in the list. If no tasks were closed in the period, the backend doesn't call Claude and shows "No tasks were closed in the last 7 days yet. Once your team closes issues, this summary fills in."

**Both calls:**
- Check `stop_reason` before using the result. `refusal` or `max_tokens` counts as a failure, which shows the friendly error.
- Use a 120-second timeout.
- The server-side refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) is enabled if the installed SDK supports it together with `parse()`. Check this in the first spike.

**Cost estimate:** Opus 5.5 costs $4 per million input tokens and $20 per million output tokens. One generation (about 3k input tokens and 3–6k output tokens including thinking) costs roughly $0.08–0.15. A summary costs a few cents.

### GitHub Client (`referee/github_client.py`)

The only code that talks to GitHub. Every request sends:

```
Authorization: Bearer <GITHUB_TOKEN>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

It uses a 15-second timeout.

| Function | Request | Result used |
|---|---|---|
| `check_repo(full_name)` | `GET /repos/{owner}/{repo}` | 200 → `full_name`, `html_url`, `default_branch`; 401 → bad token; 404 → not found or no access |
| `can_be_assigned(full_name, login)` | `GET /repos/{owner}/{repo}/assignees/{login}` | 204 → yes; 404 → no (not a collaborator, or invitation not accepted yet) |
| `ensure_label(full_name)` | `GET /repos/{owner}/{repo}/labels/repo-referee`; if 404, `POST /repos/{owner}/{repo}/labels` with `{"name": "repo-referee", "color": "2DA44E", "description": "Task created by Repo Referee"}` | — |
| `create_issue(full_name, title, body, login)` | `POST /repos/{owner}/{repo}/issues` with `{"title", "body", "assignees": [login], "labels": ["repo-referee"]}` | 201 → `number`, `html_url` |
| `list_referee_issues(full_name)` | `GET /repos/{owner}/{repo}/issues?state=all&labels=repo-referee&per_page=100` | Per item: `number`, `state`, `state_reason`, `closed_at`, `html_url`. Items with a `pull_request` key are skipped. |

The dashboard needs **one** `list_referee_issues` call per refresh, not one call per task. That keeps polling far below GitHub's limit.

### Calculations (`referee/logic.py`)

Pure functions with no network and no files, so they are easy to test with `pytest`. All the "is it fair, how far are we" math lives here.

#### Fair Share and Over-Share

Implements `prd.md > Choosing Tasks Fairly`.
- `total_points` = sum of all task weights.
- `fair_share` = `total_points / number_of_members`. It is shown as a whole number when it is one, and otherwise with one decimal ("9.4").
- `chosen_points[person]` = sum of the weights of the tasks that person chose.
- Over-share heads-up when `chosen_points[person] > fair_share`.

#### Task Status from GitHub

Implements `prd.md > Dashboard: Automatic Status`. Each task is matched to its issue by issue number.
- **done:** the issue is `closed` with `state_reason` `completed`, or with no reason (older or API-closed issues).
- **dropped:** the issue is `closed` with `state_reason` `not_planned` or `duplicate`. Dropped tasks are left out of **every** total: criterion progress, contribution, squares and the balance tip. The dashboard shows a muted line such as "1 task was closed as not planned and isn't counted."
- **open:** the issue is `open`, including reopened issues.
- **missing:** the issue isn't in the list (deleted or transferred). It counts as open and is marked "issue not found" on the dashboard.

#### Progress per Criterion

Implements `prd.md > Dashboard: Progress per Criterion`.
- `percent(criterion)` = done points ÷ total points of its counted (not dropped) tasks × 100, rounded to a whole number, for example "Data quality · 60%". A criterion without counted tasks shows "No tasks" instead of a percentage.
- The overall line shows the same for all tasks, plus "9 / 16 tasks closed".

#### Contribution per Person

Implements `prd.md > Dashboard: Contribution per Person`.
- `contribution[person]` = sum of the weights of that person's done tasks ("7 pts").
- Squares: one per counted (not dropped) task the person chose, in task order. A done task gets a green shade by weight (`--sq-1` … `--sq-4`); an open task is light gray (`--sq-0`). Hovering shows "#12 Clean missing values · weight 3", and clicking opens the issue in GitHub.

#### Feedback Rules

Implements `prd.md > Dashboard: Feedback`. The dashboard shows at most three messages, celebrations first, newest completion first.
- **Celebration:** a criterion whose tasks are all done. Copy: "Criterion 2 · Data quality is complete! 🎉"
- **Team balance tip:** a person who has closed at least 80% of the points of the (counted) tasks **they chose**, while some criterion still has open points. Someone with no tasks never gets the tip. The "busiest" criterion is the one with the most open points; a tie goes to the first in order. Copy:
  - below 100%: "Sara is almost done with their tasks. Modelling has the most open work — maybe Sara can help out there?"
  - at 100%: "Sara has finished all their tasks! Modelling has the most open work — maybe Sara can help out there?"
- **Nothing closed yet:** "Nothing closed yet. Close an issue in GitHub and it shows up here within seconds."
- **Nothing new to say** (things are closed but no rule fires): "Steady progress. Keep closing issues in GitHub and this dashboard follows along."

#### Weekly Summary Input

Implements `prd.md > Dashboard: Weekly Summary`. Done tasks whose issue `closed_at` falls in the last 7 × 24 hours, with title, criterion, weight and person.

### Dashboard (`templates/dashboard.html`, `static/js/dashboard.js`)

Implements `prd.md > Screens and Layout` item 6 and the four dashboard headings in `prd.md > Features and Behavior`.

**Refreshing:**
- `dashboard.js` calls `GET /api/status` when the page opens, every `POLL_SECONDS` (10), and when the tab becomes visible again.
- It never starts a new request while one is still running.

**Response shape:**

```json
{
  "synced_at": "2026-10-20T14:03:10Z",
  "totals": {"done_points": 18, "total_points": 29, "percent": 62, "tasks_closed": 9, "tasks_total": 16, "tasks_dropped": 1},
  "feedback": [{"kind": "celebration", "text": "Criterion 2 · Data quality is complete! 🎉"}],
  "criteria": [{"id": "c2", "number": 2, "title": "Data quality", "done_points": 6, "total_points": 6, "percent": 100}],
  "board": {"c2": [{"id": "t3", "issue_number": 12, "title": "Clean missing values", "weight": 3, "state": "done",
                    "url": "https://github.com/...", "person": "Sara", "person_index": 0}]},
  "people": [{"id": "m1", "name": "Sara", "github": "sara-dev", "done_points": 7,
              "tasks": [{"issue_number": 12, "title": "Clean missing values", "weight": 3, "state": "done", "url": "https://github.com/..."}]}],
  "summary": {"text": "…", "period_start": "2026-10-13", "period_end": "2026-10-20"}
}
```

**Sections, top to bottom:**
1. Feedback messages.
2. The board, with the overall line above it: one column per grading criterion, each with a colored top line and a "done/total" count, and one card per task with the person's initial and a green check once its issue is closed. Dropped tasks stay on the board, muted and struck through. Cards link to their issue and are never dragged. The board scrolls sideways on a narrow screen.
3. Weekly summary: the "Write weekly summary" button, then the latest summary with its period and the note "Written by Claude from your closed issues".
4. Contribution per person: each row shows `@github`, the name, the squares, and the points.

**Footer:** "synced 8s ago" with a green dot, counting up every second. When GitHub can't be reached, the last data stays on screen and the dot turns to the heads-up color: "Couldn't reach GitHub · showing the status from 2 min ago".

**There is no control that changes a task's status** (`prd.md > Dashboard: Automatic Status`).

**Bottom of the page:** a quiet "Start a new project" link (see `Starting Over`).

**Share board** (`prd.md > Sharing the Board (View Only)`): a button at the top right opens a panel with the view-only link, "Copy link" and "Open the view-only board". The panel talks as the finished product would (the learner's choice); the README explains that the link works where Repo Referee runs, which in the prototype is this laptop. The link is `<address>/board/<share_token>`: `PUBLIC_URL` when the app runs online, otherwise the address the app answers on now. The token (`secrets.token_urlsafe(16)`) is made the first time the dashboard opens or the tasks are sent, and every issue body gets a line "**Team board:** [see everyone's progress](…) (view only)". The view-only page is the same dashboard with `viewer`: "View only" in the header instead of the account buttons, no summary button, no start over, no Reset demo, and its own status URL. Opening it doesn't open the project or change anything; a wrong token gives a 404.

**Before anything is closed** (`prd.md > States and Boundaries`): 0% bars, all squares gray, and the "Nothing closed yet" message. The squares already show everyone's chosen work, so the page never looks empty.

### Starting Over

`POST /api/reset`, implementing `prd.md > Starting Over`.
- **Confirmation** (inline, not a browser pop-up), with the buttons "Start new project" and "Cancel". For a project saved to a profile: "This one stays under "Your projects"." For one that isn't: "This one isn't saved to a profile, so it's cleared from Repo Referee", with a link to save it first. Both add "Your issues stay in GitHub."
- **On confirm:** a saved project closes and stays under "Your projects"; an unsaved one is moved to `data/archive/`. The browser goes to the start page.
- Nothing in GitHub is touched, and nothing is permanently deleted: an archived file can be moved back by hand if needed.

### Styling (`static/css/style.css`)

One stylesheet. It starts with the tokens from `Look and Feel` as CSS custom properties, followed by a few reusable pieces: card, button, input, step indicator, progress bar, square, message (celebration, heads-up, error), and loading state. Fonts are loaded from Google Fonts in `base.html`, and icons from the Tabler webfont. If they can't load, the system font and text labels still work.

## Data Model

Each project lives in `data/projects/<key>.json`. Next to it, `data/profiles.json` holds the profiles (`{"id": "p3f9a1c", "name": "Emir", "github": "GitEmir", "created_at": …}`; the password field on "Save project" has no `name`, so the browser never sends it and nothing about it is stored) and `data/state.json` says which project is open and who is signed in (`{"active": "3f9a1c07", "profile_id": "p3f9a1c"}`). Task status is **not** stored: it is read from GitHub on every refresh, because GitHub is the only source of truth for done or open.

```json
{
  "version": 1,
  "project": {"name": "Churn Prediction – Assignment 2", "created_at": "2026-10-20T09:12:00Z", "key": "3f9a1c07"},
  "owner_profile": "p3f9a1c",
  "team": [
    {"id": "m1", "name": "Sara", "github": "sara-dev"},
    {"id": "m2", "name": "Ali", "github": "ali-dev"}
  ],
  "assignment_text": "…the pasted assignment…",
  "criteria": [
    {"id": "c1", "number": 1, "title": "Business understanding", "description": "…"},
    {"id": "c2", "number": 2, "title": "Data quality", "description": "…"}
  ],
  "repo": {"full_name": "owner/repo-referee-demo", "html_url": "https://github.com/owner/repo-referee-demo"},
  "tasks": [
    {"id": "t1", "title": "Clean missing values", "done_when": "…", "weight": 3,
     "criterion_id": "c2", "owner_id": "m1", "issue_number": null, "issue_url": null}
  ],
  "sent_at": null,
  "summary": null,
  "share_token": null,
  "next_ids": {"m": 3, "t": 2}
}
```

No open project means "first use" or "start another one". `owner_profile` is `null` until the project is saved to a profile. `next_ids` holds the next number for each kind of ID, so an ID is never reused after a removal (a page left open in another tab can't act on the wrong person or task). A file that can't be read as a project is moved to `data/archive/` and treated as first use. Which setup step to show is derived from which fields are filled in (see `Components > Flask App and Routes`). `share_token` is the secret part of the view-only board link; it is `null` until the dashboard first opens or the tasks are sent. A criterion's `number` is its position in the assignment (1, 2, 3…). It is added by the backend and used in labels like "Criterion 2 · Data quality".

| Data | Comes from | Updated when | After leaving and coming back |
|---|---|---|---|
| Project name, team | Setup forms | Each add, remove or save | Kept; header and lists show it |
| Assignment text | Step 3 form | On submit, before calling Claude | Kept, so "Try again" works |
| Criteria, tasks | Claude, then the team's edits | Generation; every autosave | Kept; review page shows the latest edits |
| Repo | Step 4 form | On a successful check | Kept |
| Issue numbers and links | GitHub's reply when sending | Right after each issue is created | Kept; a retry skips tasks that have them |
| Done or open | GitHub, every refresh | Never stored | Read fresh from GitHub |
| Weekly summary | Claude | Each button press | The latest one is kept and shown |

`data/` is in `.gitignore`: it holds teammates' names and GitHub usernames.

## File Structure

```
build-with-ai-basics/
├── app.py                     # Flask entry point: page routes + small JSON API; no business logic
├── referee/
│   ├── __init__.py
│   ├── store.py               # Projects, profiles and the open project in data/ (safe writes)
│   ├── ai.py                  # Only code that talks to Claude: generate_plan(), write_summary()
│   ├── github_client.py       # Only code that talks to GitHub: repo check, assignee check, label, create/list issues
│   └── logic.py               # Pure math: fair share, status mapping, progress, contribution, feedback, weekly window
├── scripts/
│   ├── spike_claude.py        # Early spike: one real generate_plan() call on the sample assignment
│   └── spike_github.py        # Early spike: repo check, assignee check, label, one test issue, list
├── templates/
│   ├── base.html              # Shared layout: header with project name and profile, fonts, icons, step bar, one calm card
│   ├── home.html              # Start page: what the app does, first question, or Welcome back + Your projects
│   ├── account_save.html      # "Save your project": create or pick a profile
│   ├── signin.html            # "Welcome back": choose your profile
│   ├── _steps.html, _aside.html, _avatar.html, _logo.html, _task_card.html  # Shared pieces
│   ├── setup_project.html     # Step 1: name the project
│   ├── setup_team.html        # Step 2: team members
│   ├── setup_assignment.html  # Step 3: paste assignment, loading state
│   ├── setup_repo.html        # Step 4: connect repo, who can be assigned
│   ├── setup_review.html      # Step 5: edit tasks, choose people, fair-share bars, send
│   └── dashboard.html         # Dashboard shell; filled in by dashboard.js
├── static/
│   ├── css/style.css          # Design tokens + components
│   └── js/
│       ├── review.js          # Live fair-share bars, autosave, send
│       └── dashboard.js       # Polling, rendering, weekly summary button
├── tests/
│   ├── test_logic.py          # pytest for referee/logic.py
│   └── test_store.py          # pytest for referee/store.py: several projects, profiles, the old project.json
├── samples/
│   └── assignment-room-booking.md  # Fictional coding assignment with grading criteria (the sample)
├── data/                      # Created at runtime; gitignored (projects/, profiles.json, state.json, archive/)
├── devpost/                   # scope.md, prd.md, spec.md; later checklist.md and app-map.html
├── .env.example               # Names of the required environment variables, no values
├── .gitignore                 # .env, data/, .venv/, __pycache__/, .pytest_cache/, learner profile
├── requirements.txt           # flask, anthropic, requests, python-dotenv, pytest (pinned)
├── LICENSE                    # MIT
└── README.md                  # What it is, setup with keys, how to run, demo walkthrough
```

## External Services and Dependencies

### Claude API (Anthropic)

- **Used for:** task generation (`messages.parse` with a Pydantic output format) and the weekly summary (`messages.create`). See `Components > AI Module` for the exact calls.
- **Auth:** `ANTHROPIC_API_KEY` from `.env`, read automatically by `anthropic.Anthropic()`.
- **Cost:** `claude-opus-5-5` at $4 per million input tokens and $20 per million output tokens, about $0.08–0.15 per generation. A few dollars of credit covers the whole build and demo.
- **Limits:** account rate limits are far above this app's use (a handful of calls per session).
- **Data:** the pasted assignment is sent to Anthropic. The demo uses a fictional assignment, as `scope.md > Explicitly Cut` requires.
- **Docs:** structured outputs https://platform.claude.com/docs/en/build-with-claude/structured-outputs, pricing https://platform.claude.com/docs/en/about-claude/pricing, errors https://platform.claude.com/docs/en/api/errors, SDK https://github.com/anthropics/anthropic-sdk-python.

### GitHub REST API

- **Used for:** the five calls in `Components > GitHub Client`.
- **Auth:** a fine-grained personal access token in `GITHUB_TOKEN`. Settings:
  - repository access "Only select repositories" → the test repo;
  - permission **Issues: read and write** (Metadata read is added automatically);
  - an expiry date after the demo recording.

  The token belongs to the repo owner, who has push access, which is what assigning and labelling require.
- **Assigning:** only people who can be assigned in the repo (collaborators who accepted the invitation) can be assignees. The assignee check endpoint answers 204 or 404, so the app checks before sending instead of relying on error behavior.
- **Rate limits:** 5,000 requests per hour for a personal token. Polling every 10 seconds is about 360 per hour. Issues are created one at a time, not in parallel, to stay clear of GitHub's secondary limits for creating content.
- **Closing via commits:** keywords such as "Closes #12" close the issue only when the commit lands on the default branch.
- **Docs:** issues https://docs.github.com/en/rest/issues/issues, assignees https://docs.github.com/en/rest/issues/assignees, labels https://docs.github.com/en/rest/issues/labels, tokens https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens, rate limits https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api, closing keywords https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue.

### Google Fonts and Tabler Icons

These load from their CDNs in `base.html`. There are no keys and no cost, and both are free licenses (Open Font License and MIT). Without internet the app falls back to system fonts, but it needs internet anyway for Claude and GitHub.

## Important Failure Modes

- **Claude is slow, fails or returns something unusable** → a loading state while waiting ("Reading your assignment…"). On failure: "Generating tasks didn't work this time. Your text is saved — try again." Criteria without tasks get one automatic retry, then a visible note on the review page.
- **The repo or a teammate isn't ready** (wrong token, wrong repo, invitation not accepted) → a clear message at step 4 with a per-person check. Before sending, a re-check stops before anything is created and offers "Send anyway" for teammates who haven't accepted yet.
- **Sending fails halfway** → each created issue is saved immediately, the page says how many were sent, and "Send" again continues without duplicates.
- **GitHub can't be reached during polling** → the dashboard keeps the last known status and shows "Couldn't reach GitHub · showing the status from 2 min ago". It recovers by itself on the next successful poll.

## What Was Simplified and Why

- **Polling every 10 seconds** instead of webhooks. Webhooks need a server that GitHub can reach on the internet, and this app runs locally. The fuller version would be a hosted backend that receives GitHub webhook events and pushes updates to the browser instantly.
- **One JSON file** instead of a database. There is one team and one project. The fuller version would use a database with many projects and teams.
- **Local only, no deployment, no login.** The keys stay on the laptop and nothing has to be hosted or secured. The fuller version would have hosting, accounts, and per-team access.
- **A fine-grained personal token** instead of a GitHub App or "sign in with GitHub". One person sets it up once. The fuller version would be a GitHub App that teams install on their repo.
- **At most 100 tasks per project** (one page of GitHub results), with no pagination. Real assignments produce about 6–15 tasks.
- **Weekly summary on demand** (a button) instead of a scheduled weekly message.
- **Equal fair share by points**, without skills or availability, as `scope.md > Later` says.
- **Light theme only.**

## Verification Approach

- **Automated (`uv run pytest`):** `tests/test_logic.py` covers:
  - fair share, including non-whole numbers;
  - the over-share heads-up;
  - the status mapping (open, completed, not planned, duplicate, reopened, missing), including dropped tasks leaving every total;
  - progress per criterion;
  - contribution;
  - each feedback rule (celebration, balance tip, nothing closed, calm);
  - the 7-day window.
- **Two early spikes**, small experiments at the start of the build that check the riskiest parts first:
  1. **Claude spike:** run `generate_plan` on `samples/assignment-churn.md`. Check that the shape is valid, every criterion is covered, there are 10–25 sensible tasks, and how long it takes and what it costs (token usage). Also check whether the refusal fallback works with `parse()`.
  2. **GitHub spike:** with the real token and test repo, run each of these and note the result:
     - check the repo;
     - check that a collaborator can be assigned (expect 204) and that a non-collaborator can't (expect 404), and which token permission that needs;
     - create one issue with an assignee and the label;
     - list it;
     - close it in GitHub as "completed" and once as "not planned", and read `state_reason`.

     Clean up the test issue afterwards.
- **Manual:** after each build step, the learner checks the matching acceptance criteria from `prd.md > Features and Behavior` in the browser. These become `checklist.md` in `5-build`.
- **Demo rehearsal:** start from an empty `data/`, run the full journey with the sample assignment and the test repo, close an issue in GitHub, and see the dashboard move within 10 seconds. Use "Start a new project" between takes.

**Suggested build order** (for `5-build` to refine):
1. project skeleton and store, steps 1–2;
2. both spikes;
3. step 3 (AI);
4. step 4 (repo);
5. step 5 (review);
6. sending;
7. dashboard status and polling;
8. feedback;
9. weekly summary;
10. polish, README and demo assignment.

## Decisions and Open Issues

### Decisions

| Decision | Chosen | Why | Tradeoff accepted | Who |
|---|---|---|---|---|
| App shape and language | Python backend, own HTML/CSS/JS frontend | Familiar language; full control over the design | More hand-written frontend code than Streamlit | Learner |
| Where it runs | Locally, recorded for the demo | Keys stay local; no hosting work | Judges can't click a live link | Learner |
| How the dashboard follows GitHub | Polling every 10 s, plus on open and when the tab returns | Works on localhost; simple and reliable | Up to 10 s delay | Agent recommendation; the learner asked the agent to choose and accepted it |
| AI provider | Claude API | Learner's choice | Paid per call | Learner |
| Model | `claude-opus-5-5`, configurable in `.env` | Anthropic's current default; reliable structured output | Slower and more expensive than Haiku | Agent recommendation, learner accepted |
| Storage | `data/project.json` | Simple, readable, enough for one project | One project only | Learner |
| Team in GitHub | Real collaborators, invited to the test repo | Issues are truly assigned in the demo | Invitations must be accepted before recording | Learner |
| Look | Light, minimal, green accent, GitHub-inspired details | Learner preferred minimalist; chosen after comparing three rounds of visual directions | Less "playful" than the PRD first described (PRD updated) | Learner |
| Backend framework | Flask | Simplest way to serve pages plus a small JSON API | Manual input checks | Agent recommendation, learner accepted |
| Frontend tech | No framework, no build step | Small app; nothing to configure | Some hand-written DOM code | Agent recommendation, learner accepted |
| Weight scale | Whole numbers 1–5 | Confirms the PRD assumption | — | Learner accepted |
| Balance tip | Shown when someone has closed 80% of the points they chose; busiest = criterion with most open points; names, no pronouns | Someone who chose less than the fair share still gets the tip once nearly done (the earlier assumption, 80% of the fair share, could never trigger for them) | — | Learner, following the agent's advice (self-review P5) |
| Weekly summary period | Last 7 days | Matches "weekly" | — | Learner accepted |
| Order between tasks | Not in the proof of concept | Keeps it small | — | Learner accepted |
| Testing | pytest for logic, two early spikes, manual checks per step | Tests the math and the two risky integrations first | — | Learner accepted |
| Demo assignment | Fictional, written by the learner, in `samples/` | No real course material in public | Learner writes it | Learner accepted |
| Running Python | `uv` | `python` isn't on this laptop's PATH; `uv` is already installed | Two new commands | Agent, from the environment check; learner accepted with the spec approval |
| Adding and deleting tasks | Allowed on the review screen | The AI proposes, the team decides | A little more review-screen code | Learner (self-review P1) |
| Starting over | "Start a new project" link on the dashboard; the project is archived, the issues stay | Demo practice and new assignments | — | Learner (self-review P2) |
| Teammate not yet assignable | Clear heads-up plus "Send anyway" | The demo never gets stuck on one invitation | Some issues may go out unassigned | Learner (self-review P3) |
| Issues closed as "not planned" or "duplicate" | Not done, and left out of every total | Only finished work counts, and dropped work doesn't block 100% | — | Learner, following the agent's advice (self-review P4) |

Implementation details the agent derived from these choices: the `repo-referee` label, saving each issue number right after it is created, autosave on the review page, refreshing when the tab returns, safe file writes, binding to `127.0.0.1`, one GitHub list call per refresh, and tasks in the assignment's language.

### Learner Question Clarified

**"What is Streamlit?"** The learner asked this when choosing the stack. It was clarified with a five-line example of a Streamlit page and a comparison: Streamlit is very quick for data demos, but its look is largely fixed (it would look like many other AI demos) and it reruns the whole page on every click, which suits a multi-step product badly. The learner kept their choice of Python plus their own HTML.

**"Is the feedback personal, per login?"** While deciding P5, the learner expected the feedback and tips to be general, for everyone. This was clarified: there are no logins, so the dashboard is one shared screen and everyone who opens it sees the same messages. The balance tip names a person only to suggest who has room to help. The learner chose to keep the named tip.

### Uncertainty to Check Early in the Build

GitHub's documentation doesn't say exactly what happens when an issue is created with an assignee who can't be assigned (only a general 422 "validation failed"). It also doesn't say which token permission the assignee check needs. **Agreed approach:** check with `GET /repos/{owner}/{repo}/assignees/{login}` (documented: 204 or 404) before sending, and confirm the behavior and the permission in the GitHub spike.

### Self-Review Decisions

The spec self-review raised five points the PRD didn't cover. The learner decided all of them, and they are recorded in the table above and in `prd.md`:
- P1: adding and deleting tasks;
- P2: starting over;
- P3: "Send anyway";
- P4: "not planned" and "duplicate" don't count;
- P5: when the balance tip appears.

### Carried Over from `prd.md > Open Questions`

- Order between tasks, weight scale, balance tip details and dashboard speed are decided above, and `prd.md` is updated to match.
- **Name check:** make sure "Repo Referee" isn't already a known product. This waits until `6-ship`.

### Housekeeping for `5-build` and `6-ship`

- Before the first commit, decide with the learner what happens to `.agents/`, `.claude/`, `agent/` and `skills-lock.json`. The skills are linked with absolute-path symlinks that won't work on other machines (project `CLAUDE.md`).
- Extend `.gitignore` with `data/`, `.venv/`, `__pycache__/` and `.pytest_cache/`. `.env` and the learner profile are already ignored.
- Add an MIT `LICENSE`, and set the license in the GitHub "About" section when publishing.
- **Learner to-dos before the build needs them:**
  - an Anthropic API key with a few dollars of credit;
  - a fine-grained GitHub token;
  - the test repo, with collaborators invited early. Ask them whether they agree to their GitHub usernames appearing in the public video and repo.
