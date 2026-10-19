---
doc: scope
status: approved
---

# Repo Referee (working title)

Paste a project assignment and its grading criteria. The app turns them into clear tasks in your team's GitHub repo, then tracks progress by itself, so nobody has to keep a board up to date.

## The Unique Kernel
**Tasks live where the work already happens, and status updates itself.** AI turns a vague assignment into small, weighted tasks per project phase (for a data science project, the phases of the data science lifecycle), each linked to a grading criterion, and puts them in GitHub as issues. When someone closes an issue or pushes a commit that closes it, the dashboard updates on its own. There is no separate board that nobody maintains.

## Who It's For
University student teams of about five in data science or programming project courses: teams that already work in GitHub. The learner's own case is a data science team working through the full data science lifecycle for a client assignment that lists tasks, tools and grading criteria. The demo uses a data science project.

What they do today: everyone reads the assignment, then 1–2 people translate it into tasks and hand them out. Tasks go on a Trello board, but nobody uses it, because:
- updating it is extra work next to the real work,
- the real work happens in GitHub (code) and a shared Word doc (report), and the chat happens elsewhere,
- the tasks on the board are too vague to be worth updating,
- nobody looks at the board, so there is no reason to keep it current.

The result, in the learner's words and choices:
- tasks are split by who speaks up, not by who fits,
- nobody knows how far anyone is,
- the work ends up unevenly divided,
- at the end it is unclear whether every grading criterion was actually met.

## The Core Loop
**Once, at the start:** one team member pastes the assignment and criteria. They get concrete tasks per project phase, with a weight and a linked criterion. With one click the tasks become GitHub issues, split fairly by weight across the team.

**Then, over and over:** the team works in GitHub as they already do and closes tasks there. Anyone opens the dashboard to see:
- progress per criterion,
- how much each person has contributed, weighted by task size,
- warnings about what is slipping.

Once a week, one click produces a short summary of what the team did.

**Why they come back:** it is the only place that answers "are we on track, and is the work fair?" without anyone having to update anything.

## Inspiration & Identity
Not discussed yet. It must feel like a finished, coherent product rather than a technical demo (Design is the tie-breaker), and avoid generic "AI app" styling. `3-prd` will ask.

## Why This Matters to the Learner
They lived this problem in two long team projects at university: "1–2 people gave out the rest of the assignment and the rest just did it, which wasn't the most efficient", and "we used Trello but nobody used it." They also want a project that shows their data and AI skills and counts as a real achievement for future employers in data and AI.

## What "Working" Looks Like
A demo under 3 minutes, using a self-written fictional assignment and a test GitHub repo:
1. **Paste the assignment:** a self-written data science assignment with criteria. Tasks appear per lifecycle phase, each with a weight and a criterion.
2. **Send to GitHub:** one click, and the tasks appear as issues in a test repo, split fairly by weight across 5 team members.
3. **The "oh, that's cool" moment:** someone closes a task in GitHub, and the dashboard updates by itself. Criterion progress moves and the contribution chart changes.
4. **Warning:** for example "Criterion 4 hasn't been picked up by anyone."
5. **Weekly summary:** one button gives a short report of what the team did.

## The POC Boundary
In:
- Paste assignment text and grading criteria. AI produces small tasks per project phase (data science lifecycle phases for a data science project), each with a weight and a linked criterion.
- One click creates the tasks as issues in one GitHub repo, split fairly by weight across the team members.
- Status is read from GitHub automatically (issues closed in GitHub, including via a commit that closes them). No manual status updates in the app.
- Dashboard: progress per criterion, plus a contribution chart per person weighted by task size.
- Warnings, for example a criterion nobody has picked up, or too little done for how close the deadline is.
- A weekly summary button (AI) that reports what the team did.

## Later
- Reading progress from the shared Word report (needs Microsoft sign-in; too heavy for the proof of concept).
- Smarter distribution based on each person's skills and available time.
- Anything beyond one team and one repo.

## Explicitly Cut
- **A board people have to update by hand.** This is exactly why Trello failed for this team, so status only comes from GitHub.
- **Real school assignments in the public demo.** Use a self-written fictional assignment instead, to avoid sharing course material or client details.

## Open Questions for the PRD
- Confirm the final name (the learner chose "Repo Referee" as the working title).
- Who pastes the assignment, and can the team edit the tasks before they go to GitHub?
- What exactly counts as "fair" when splitting by weight.
