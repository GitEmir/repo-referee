---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast

## Slices

- [x] **1. You can name a project and add your team in the browser**
  Becomes usable: The app runs at http://127.0.0.1:5000: you name a project, add and remove team members with their GitHub usernames, and everything survives a refresh or a restart. The header shows the project name.
  Why now: It needs no API keys, so it can be built and tried while the keys for the two spikes are being set up. The first screens set the look for every screen after them, and `data/project.json`, which they create, is what every later step reads and adds to. Project bootstrapping (environment, pinned dependencies, `.gitignore`, `.env.example`, license, first README) happens here because this is the first code that needs it.
  PRD ref: `prd.md > Features and Behavior > Project Setup`, `prd.md > States and Boundaries` (first use, coming back), `prd.md > Look and Feel`
  Spec ref: `spec.md > Components > Flask App and Routes`, `spec.md > Components > Project Store`, `spec.md > Components > Setup Step 1: Create Project`, `spec.md > Components > Setup Step 2: Team Members`, `spec.md > Components > Styling`, `spec.md > Look and Feel`, `spec.md > Data Model`, `spec.md > File Structure`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Create the uv environment and pin the latest stable dependencies in `requirements.txt`; extend `.gitignore`; add `.env.example`, an MIT `LICENSE` and a first `README.md` with setup and run steps. Add `app.py` (Flask bound to 127.0.0.1; `/` redirects to the first unfinished step), `referee/store.py` (load, safe save, short IDs), `templates/base.html` (header with logo mark, "Repo Referee" and the project name, step indicator, fonts and icons), the step 1 and step 2 pages with the spec's validation, and `static/css/style.css` with the color tokens and base components. Steps that are not built yet show a short "coming next" page.
  Verify (mechanical): Start `uv run flask --app app run` with no errors. With Flask's test client, confirm `/` redirects to step 1; an empty name shows the error; a saved name appears in the header and in `data/project.json`; `@sara-dev` is saved as `sara-dev`; an invalid username is rejected; removing a member works; after a restart `/` goes to the first unfinished step with the data intact. Take a browser screenshot and compare it with `spec.md > Look and Feel`.
  Learner check: Open http://127.0.0.1:5000, create a project, add your teammates (try pasting a username with @), remove one and add them back, then restart the server and refresh: everything is still there. Does it look and feel like the style you chose?
  Commit: `Add project setup and team steps`

- [x] **2. Claude turns the sample assignment into criteria and tasks**
  Becomes usable: A command that sends `samples/assignment-churn.md` to Claude through `generate_plan()` and prints the grading criteria and the weighted tasks, with the time taken, token usage and estimated cost.
  Why now: The riskiest unknown, as soon as the API key is in place: every later step depends on Claude returning criteria and tasks in exactly this shape, fast and cheap enough.
  PRD ref: `prd.md > Features and Behavior > Task Generation`
  Spec ref: `spec.md > Components > AI Module`, `spec.md > External Services and Dependencies > Claude API (Anthropic)`, `spec.md > Verification Approach` (Claude spike)
  Build: Write `referee/ai.py` with the `Plan` models, `PLAN_INSTRUCTIONS` and `generate_plan()` (model read from `.env`, 120-second timeout, `stop_reason` checks, the refusal fallback if the SDK supports it together with `parse()`); add `scripts/spike_claude.py`. The learner writes the fictional `samples/assignment-churn.md` and puts their own API key in `.env`.
  Verify (mechanical): Run `uv run python scripts/spike_claude.py` and confirm the result parses into `Plan` with `usable` true, 10–25 tasks, weights 1–5, only existing criterion IDs and at least one task per criterion; note the duration, token usage, estimated cost and whether the fallback works with `parse()`, and record anything that differs from the spec under Revisions.
  Learner check: Run the spike command yourself and read the printed criteria and tasks: are they concrete tasks for this one assignment that a teammate could pick up, does every criterion have tasks, and do the weights feel right?
  Commit: `Add Claude task generation spike`

- [ ] **3. A real GitHub issue is created, assigned and read back**
  Becomes usable: A few commands that check the test repo and who can be assigned, create one labelled issue assigned to you, and read its `state` and `state_reason` back after you close it in GitHub.
  Why now: The second unknown and the heart of the kernel: the app stands or falls on assigned issues and on reading back how they were closed. Settling the open assignee question now means the send and dashboard steps build on facts, not assumptions.
  PRD ref: `prd.md > Features and Behavior > Sending Tasks to GitHub`, `prd.md > Features and Behavior > Dashboard: Automatic Status`
  Spec ref: `spec.md > Components > GitHub Client`, `spec.md > External Services and Dependencies > GitHub REST API`, `spec.md > Verification Approach` (GitHub spike), `spec.md > Decisions and Open Issues > Uncertainty to Check Early in the Build`
  Build: Write `referee/github_client.py` with the five calls from the spec (shared headers, 15-second timeout, clear errors for a bad token and a missing repo); add `scripts/spike_github.py` with small commands to check the repo, check an assignable and a non-assignable username, ensure the `repo-referee` label, create a test issue and list the Repo Referee issues. The learner creates the test repo and the fine-grained token, puts the token in `.env`, and invites the teammates.
  Verify (mechanical): Run each command and confirm: the repo check returns the full name and default branch; the owner gets 204 and a non-collaborator 404; the label exists; the test issue has the assignee and the label; after the learner closes it as completed, and later as not planned, the list shows `state_reason` `completed` and then `not_planned`. Also try creating one issue for a non-assignable username, and record GitHub's response and the token permissions that were enough under Revisions.
  Learner check: Open the test issue in GitHub and check the assignee and the green `repo-referee` label; close it as completed and run the list command, then reopen it, close it as not planned and run the list command again. Clean up the test issues afterwards.
  Commit: `Add GitHub client and spike`

- [ ] **4. You can paste the assignment and connect the repo**
  Becomes usable: Pasting the assignment shows a calm loading state and saves Claude's criteria and tasks; connecting the repo shows, per teammate, whether they can be assigned yet. Empty or unusable text, a failed generation and a wrong repo each get a clear, friendly message.
  Why now: This connects the two proven integrations to the product, in journey order. The saved tasks and the checked repo are exactly what the review and send step needs next.
  PRD ref: `prd.md > Features and Behavior > Task Generation`, `prd.md > The Core Journey` (steps 3–4), `prd.md > States and Boundaries` (empty or unusable text, AI can't generate tasks, repo can't be reached, teammate hasn't accepted)
  Spec ref: `spec.md > Components > Setup Step 3: Paste Assignment and Generate Tasks`, `spec.md > Components > Setup Step 4: Connect Repo`, `spec.md > Important Failure Modes`
  Build: Step 3: save the text first, show the loading state, call `generate_plan()`, check weights and criteria with one automatic retry for criteria without tasks, number the criteria, save criteria and tasks, and show the spec's messages for empty, unusable and failed generation (with "Try again"), plus the replace confirmation. Step 4: accept `owner/repo` or a full link, run `check_repo()`, list each teammate as "can be assigned" or "hasn't accepted the repo invitation yet", and show the bad-token and not-found messages.
  Verify (mechanical): With the server running, submit the sample assignment and confirm numbered criteria and valid tasks are saved and the browser moves to step 4; empty text shows the message without calling Claude; unrelated text shows "We couldn't find grading criteria…"; a run with an invalid `CLAUDE_MODEL` shows the friendly failure and keeps the text; a full GitHub link is normalized and saved with the per-person check; a non-existent repo shows the not-found message.
  Learner check: Paste your sample assignment and watch the loading state, then connect the test repo with its full GitHub link and see which teammates can be assigned. Try a made-up repo name too. If you like, open `data/project.json` to see the tasks Claude saved.
  Commit: `Add assignment and repo setup steps`

- [ ] **5. You can choose who does each task and send them to GitHub**
  Becomes usable: The review page shows the tasks per criterion, everyone picks their tasks, and "Send to GitHub" becomes available once every task has a person. One click creates every task as an assigned issue and lands on a first dashboard page.
  Why now: This puts the tasks where the work happens, the first half of the kernel, with only the one choice that sending needs: a person per task. Editing and the fair-share bars come later, once the kernel works end to end.
  PRD ref: `prd.md > Features and Behavior > Sending Tasks to GitHub`, `prd.md > Features and Behavior > Choosing Tasks Fairly` (sending only once every task has a person), `prd.md > States and Boundaries` (tasks nobody chose, teammate hasn't accepted)
  Spec ref: `spec.md > Components > Setup Step 5: Review, Edit and Choose Tasks` (choosing, autosave, send button), `spec.md > Components > Sending Tasks to GitHub`, `spec.md > Components > Flask App and Routes` (step rules)
  Build: Add the review page with tasks grouped by criterion, a "Who does this?" choice per task, the empty-criterion note, autosave through `PUT /api/tasks` with server-side checks, and the send button with its "still need a person" state. Add `POST /api/send`: re-check who can be assigned (with "Send anyway" and "Wait"), ensure the label, create one issue per task in the spec's format and save each number right away, continue without duplicates after a failure, set `sent_at`, lock the setup steps and go to `/dashboard` (a simple list of the created issues until slice 6).
  Verify (mechanical): Confirm autosave writes the chosen people to `data/project.json` and rejects unknown member or criterion IDs. With a fake GitHub client, confirm a failure halfway shows "Sent N of M…" and a second send skips the issues already created. With the real test repo and a small test project, confirm the issue title, body table, assignee and label, that "Send anyway" creates an unassigned issue that still names the person, and that setup pages redirect to the dashboard afterwards.
  Learner check: On the review page, choose a person for every task and watch the button count down, refresh to see the choices kept, then press Send and open the repo's Issues tab: every task is an issue, assigned to the person who chose it, with the weight and criterion in the body.
  Commit: `Add task choosing and sending to GitHub`

- [ ] **6. The dashboard follows GitHub by itself**
  Becomes usable: The dashboard shows progress per criterion and each person's contribution squares, and when someone closes an issue in GitHub it updates on its own within 10 seconds. "Start a new project" archives the project and returns to step 1.
  Why now: This is the kernel moment, status updates itself, placed right after sending so the whole loop works as early as possible. "Start a new project" comes along because the remaining steps are tried on a fresh setup.
  PRD ref: `prd.md > Features and Behavior > Dashboard: Automatic Status`, `prd.md > Features and Behavior > Dashboard: Progress per Criterion`, `prd.md > Features and Behavior > Dashboard: Contribution per Person`, `prd.md > Features and Behavior > Starting Over`, `prd.md > States and Boundaries` (dashboard before anything is closed)
  Spec ref: `spec.md > Components > Calculations` (Task Status from GitHub, Progress per Criterion, Contribution per Person), `spec.md > Components > Dashboard`, `spec.md > Components > Starting Over`, `spec.md > Look and Feel` (motion)
  Build: Add `referee/logic.py` for status (done, dropped, open, missing), progress and contribution, with `tests/test_logic.py`; `GET /api/status` with one GitHub list call; the dashboard page and `static/js/dashboard.js`, which refresh on open, every `POLL_SECONDS` and when the tab returns, and draw the criterion bars, the overall line, the contribution squares and the "synced 8s ago" footer with its offline state; and the "Start a new project" link with its inline confirmation and `POST /api/reset`.
  Verify (mechanical): `uv run pytest` passes for the status mapping (open, completed, not planned, duplicate, reopened, missing; dropped tasks leave every total), progress and contribution. A real `/api/status` call returns the spec's response shape for the sent project, and with a stubbed GitHub list a closed issue shows up as done. In the browser, a simulated failed request keeps the last data and shows the heads-up footer. Reset moves the file into `data/archive/` and `/` goes to step 1.
  Learner check: Put the dashboard next to the repo's Issues tab, close an issue in GitHub and watch its criterion bar and the person's square change within 10 seconds; switch tabs and back for an instant refresh; close one as "not planned" and see it drop out of the totals. Finally, use "Start a new project" and check that you're back at step 1 while the issues stay in GitHub.
  Commit: `Add live dashboard and start over`

- [ ] **7. You can edit the tasks and see everyone's fair share**
  Becomes usable: On the review page every task field can be changed, tasks can be added and deleted, and a bar per person shows their chosen points against their fair share, with a friendly heads-up when someone goes over.
  Why now: With the kernel working, this makes the plan the team's own and makes fairness visible while choosing. It extends the slice 5 review page and is tried on a fresh project thanks to slice 6.
  PRD ref: `prd.md > Features and Behavior > Reviewing and Editing Tasks`, `prd.md > Features and Behavior > Choosing Tasks Fairly`
  Spec ref: `spec.md > Components > Setup Step 5: Review, Edit and Choose Tasks`, `spec.md > Components > Calculations > Fair Share and Over-Share`
  Build: Make title, "Done when", weight (1–5) and criterion editable; add "Add task" per criterion and the inline "Delete this task?"; add the live fair-share bars and the over-share heads-up at the top; extend the send button with the "needs a title" state; add fair share and over-share to `logic.py` with tests.
  Verify (mechanical): `uv run pytest` passes for fair share (including a non-whole share such as 9.4) and the over-share heads-up. Autosave keeps edited fields, gives new tasks an ID, removes deleted tasks and rejects invalid weights. A browser check shows the bars and the heads-up updating as people are chosen, and a send uses the edited values.
  Learner check: Start a new project and go through setup with your sample assignment. On the review page, change a title, a weight and a criterion, add a task and delete one, and choose people until someone goes over their fair share: does the heads-up feel friendly? Refresh to see the edits kept, then send and check one edited task in GitHub.
  Commit: `Add task editing and fair-share bars`

- [ ] **8. The dashboard gives friendly feedback**
  Becomes usable: The top of the dashboard celebrates completed criteria, suggests where someone who is (almost) done could help, and shows a friendly line when there is nothing new to say.
  Why now: The coaching layer sits on top of the status the dashboard already reads. It is pure calculation, so it can be tested on its own.
  PRD ref: `prd.md > Features and Behavior > Dashboard: Feedback`
  Spec ref: `spec.md > Components > Calculations > Feedback Rules`, `spec.md > Components > Dashboard`
  Build: Add the feedback rules to `logic.py` (celebration; team balance tip at 80% of the points that person chose, pointing to the busiest criterion; nothing closed yet; steady progress; at most three, celebrations first) with tests, include them in `/api/status`, and show them at the top of the dashboard in the celebration and heads-up styles.
  Verify (mechanical): `uv run pytest` passes for each rule, including the 80% boundary, someone without tasks never getting the tip, and a tie for the busiest criterion. `/api/status` returns the expected messages for a stubbed set of closed issues, and a screenshot shows them in the right order and colors.
  Learner check: Close every issue of one criterion in GitHub and wait for the celebration; then close most of one person's tasks and look for the balance tip with their name. Does it sound like a friendly coach?
  Commit: `Add dashboard feedback messages`

- [ ] **9. One click writes the weekly summary**
  Becomes usable: "Write weekly summary" produces a short, positive summary of the tasks closed in the last 7 days, credited by name, and the latest one stays on the dashboard.
  Why now: The last feature and the least risky: a second, simpler Claude call that only reads what the dashboard already knows.
  PRD ref: `prd.md > Features and Behavior > Dashboard: Weekly Summary`
  Spec ref: `spec.md > Components > AI Module` (`write_summary`), `spec.md > Components > Calculations > Weekly Summary Input`, `spec.md > Components > Dashboard`
  Build: Add `write_summary()` to `referee/ai.py`, the 7-day window to `logic.py` with a test, `POST /api/summary` (no Claude call when nothing was closed; saves the summary with its period), and the dashboard section with the button, loading state, saved result, the "Written by Claude from your closed issues" note and a friendly error.
  Verify (mechanical): `uv run pytest` passes for the 7-day window. `POST /api/summary` returns 3–6 sentences that mention only closed tasks, and the summary is still shown after a restart. With nothing closed it returns the fixed message without calling Claude; a forced failure (invalid model) shows the friendly error.
  Learner check: Press "Write weekly summary" and read it: does it credit people by name, mention only what was really closed, and sound positive? Refresh to see it kept.
  Commit: `Add weekly summary`

## Hands-on Checkpoints

- [ ] Early usable behavior explored — after slice 1: the first screens in the browser; feedback on the look and the setup flow shapes every later screen
- [ ] Core journey explored — after slice 6: the whole loop from setup to a dashboard that follows GitHub; feedback shapes slices 7–9
- [ ] Final kick-the-tires exploration and feedback completed — a full demo rehearsal from an empty `data/`: sample assignment, test repo, close an issue, the dashboard moves within 10 seconds, start over

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete — guided route, focused alternative, prior practice connected, or brief recap
- [ ] Optional edit and transfer reflection addressed — offered/declined/already covered/not applicable as appropriate
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: [what actually happened; real document/test/code references; unfinished work if interrupted]
Route and stops: [actual paths and symbols; guided stops completed, or reference-only route]
Edit outcome: [tried/kept/reverted/declined/not applicable; verification if changed]
Reflection: [offered/answered/declined/already covered — personal answer belongs only in the ignored profile]
Activity mode: [live app and editor, explicit static fallback, focused alternative, prior practice, or recap]

## Revisions

- Moved the project and team slice ahead of the two spikes, and project bootstrapping with it — when the build started there was no Anthropic API key or GitHub token yet, and this slice needs neither; the spikes follow as soon as the keys are in `.env`.
- Added `scripts/` with the two spike scripts to `spec.md > File Structure` — the spikes in `spec.md > Verification Approach` needed a place in the repo that the file structure didn't list.
- `generate_plan()` calls `client.beta.messages.parse()` instead of `client.messages.parse()` — in the installed SDK (anthropic 1.15) only the beta variant accepts the `betas` and `fallbacks` parameters that the refusal fallback needs.
- Switched from learn mode to fast mode at the learner's request to let the agent run and test everything and carry the build through all steps; the hands-on checkpoints and the final review still wait for the learner.
- Slices 4–9 are built while the Anthropic key and the GitHub token are still missing: each is committed once its offline checks pass against fake Claude and GitHub responses that follow the documented API shapes, and its box is ticked only after the real-service part of its Verify line passes, right after the spikes (slices 2–3) have run.
- Slice 1's review (four independent reviewers, each finding checked by a skeptic) led to: IDs are never reused (`next_ids` counter in `project.json`), an unreadable `project.json` is moved to `data/archive/` instead of breaking every page, only the field that failed is marked invalid, and larger, labelled step dots and stronger input borders for accessibility.
- Slices 4–9 are built. Offline checks pass for each: the flows run against a fake Claude and a fake GitHub that follow the documented responses, the review page and dashboard were driven in a real browser against those fakes, and the request bodies for Claude were captured with a mocked HTTP transport. Their boxes stay unchecked until the real-service parts of their Verify lines pass.
- Added `pytest.ini` (`pythonpath = .`) so `uv run pytest` finds the `referee` package from the project folder, as `spec.md > Where It Runs and How Someone Tries It` documents.
- Two more independent reviews (slices 4–5 and 6–9, each finding checked by a skeptic) confirmed 28 findings; all were fixed. The ones that change behavior are recorded in `spec.md`: setup locks once some tasks are issues, issued tasks can't change, a hidden marker in each issue body prevents duplicates after a lost answer, and a project keeps at least one task. Each issue body now ends with that marker, and `project.json` stores a short project `key` for it.
- Restarted the git history at the learner’s request: the first commit holds all project texts (planning documents, README, license, configuration examples), and the learner commits the code. The earlier per-slice history is kept outside the repository as a git bundle.
- Claude spike on the learner’s `samples/assignment-churn.md`: a valid `Plan` with 5 criteria and 20 tasks, every criterion covered, weights 2–4 (49 points); 21.6 s, 2,187 input and 2,128 output tokens, about $0.05 per generation, below the spec’s estimate of $0.08–0.15. The server-side refusal fallback (`fallbacks="default"`) is accepted together with `parse()`.
