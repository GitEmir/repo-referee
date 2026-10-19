# Repo Referee

Repo Referee helps a student team turn a project assignment and its grading criteria into small, fairly shared tasks in their GitHub repo, and then shows by itself whether they are on track and whether the work is fair. Status comes from GitHub: when someone closes an issue, the dashboard follows.

It is a small local web app: a Flask backend in Python, plain HTML, CSS and JavaScript in the browser, the Claude API for task generation and the weekly summary, and the GitHub REST API for issues. Everything is saved in one file, `data/project.json`.

> **Status:** proof of concept, built for the Build With AI: Basics hackathon. The planning documents it was built from are in [`devpost/`](devpost/).

## How it works

1. **Create a project** and give it a name.
2. **Add the team**: everyone's name and GitHub username.
3. **Paste the assignment** with its grading criteria. Claude turns it into small tasks, each with a "done when", a weight from 1 to 5 and a linked criterion.
4. **Connect the GitHub repo**. The app checks which teammates can be assigned issues there.
5. **Review and choose**. Change anything Claude proposed, add or delete tasks, and let everyone pick their tasks. A bar per person shows their chosen points against the fair share (total points ÷ team size), with a friendly heads-up when someone goes over.
6. **Send to GitHub**. Every task becomes an issue, assigned to the person who chose it, with the `repo-referee` label.

Then the team works in GitHub as usual. The **dashboard** checks GitHub every 10 seconds (and whenever you come back to the tab) and shows friendly feedback, progress per criterion, a weekly summary button and each person's contribution. Nobody updates a status by hand: an issue closed as *completed* counts as done, one closed as *not planned* or *duplicate* drops out of the totals.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) (recommended), or plain `pip`
- An internet connection (for Claude, GitHub and the web fonts)
- A Claude API key and a GitHub repo with a fine-grained token (see below)

## Setup

```powershell
uv venv
uv pip install -r requirements.txt
Copy-Item .env.example .env
```

Then open `.env` and fill in the keys:

| Variable | What it is |
|---|---|
| `ANTHROPIC_API_KEY` | A Claude API key from the Claude Console, with a few dollars of credit. One task generation costs roughly $0.10. |
| `GITHUB_TOKEN` | A fine-grained personal access token. Repository access: **Only select repositories** → your test repo. Permission: **Issues: Read and write**. |
| `CLAUDE_MODEL` | Optional. Defaults to `claude-opus-5-5`. |
| `POLL_SECONDS` | Optional. How often the dashboard checks GitHub. Defaults to `10`. |

`.env` is ignored by git, so the keys never end up in the repository. Restart the app after changing `.env`.

Teammates must accept the invitation to the repo before issues can be assigned to them. The app tells you who hasn't accepted yet, and lets you send anyway: their issues then go out unassigned but still say who chose them.

## Run

```powershell
uv run flask --app app run
```

Then open <http://127.0.0.1:5000>. The app only listens on your own computer.

Without uv:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app app run
```

On macOS or Linux, activate the environment with `source .venv/bin/activate` instead.

**Start over:** "Start a new project" at the bottom of the dashboard moves `data/project.json` into `data/archive/` and returns to the first step. The issues in GitHub are left untouched.

**Closing issues from a commit:** a commit message such as `Closes #12` closes the issue only when the commit lands on the repo's default branch.

## Tests

```powershell
uv run pytest
```

The tests cover the calculations in `referee/logic.py`: fair share, task status from GitHub, progress per criterion, contribution, the feedback rules and the weekly summary window.

Two small scripts try the real APIs once the keys are in `.env`:

```powershell
uv run python scripts/spike_claude.py samples/assignment-churn.md
uv run python scripts/spike_github.py owner/repo check your-username
```

## Project files

| Path | What it holds |
|---|---|
| `app.py` | Flask routes: the setup pages, the dashboard and a small JSON API |
| `referee/store.py` | Loads and saves `data/project.json` with safe writes |
| `referee/ai.py` | The only code that talks to Claude: task generation and the weekly summary |
| `referee/github_client.py` | The only code that talks to GitHub: repo check, assignee check, label, create and list issues |
| `referee/logic.py` | Pure calculations: fair share, status, progress, contribution, feedback |
| `templates/`, `static/` | The pages, the stylesheet and the two browser scripts (`review.js`, `dashboard.js`) |
| `tests/` | pytest tests for `referee/logic.py` |
| `scripts/` | The two spike scripts for the real APIs |
| `data/` | Created at runtime and ignored by git: it holds teammates' names and GitHub usernames |
| `devpost/` | The planning documents: scope, PRD, technical spec and build checklist |

## License

[MIT](LICENSE)
