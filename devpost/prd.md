---
doc: prd
status: approved
---

# Repo Referee: Product Requirements

Repo Referee helps a university student team of about five turn one project assignment and its grading criteria into clear, fairly shared tasks in their GitHub repo, and then shows by itself whether they are on track and whether the work is fair.
Source: `scope.md > Who It's For`, `scope.md > The Unique Kernel`.

Two principles guide every behavior below:
- **Status updates itself.** Nobody updates a board by hand; progress comes from GitHub. (`scope.md > The Unique Kernel`, `scope.md > Explicitly Cut`)
- **AI guides and helps, it doesn't take over.** The AI proposes; the team decides and can change everything.

## The Core Journey
Source: `scope.md > The Core Loop`, `scope.md > What "Working" Looks Like`.

The team sits together behind one screen for the setup. One person operates the app.

**Setup (once per assignment):**
1. **Create a project.** Open the app and create a new project by giving it a name (for example "Churn Prediction – Assignment 2").
2. **Add team members.** Enter each team member's name and GitHub username (any number of people).
3. **Paste the assignment.** Paste the assignment text and its grading criteria. The AI turns it into small tasks, each linked to a grading criterion.
4. **Connect the GitHub repo.** Enter the team's GitHub repo.
5. **Review, edit and choose tasks.** See all proposed tasks. Edit anything. Team members choose their own tasks; every task must have a person. The app shows each person's fair share and gives a friendly heads-up when someone goes over it.
6. **Send to GitHub.** Once every task has a person, one click creates every task as a GitHub issue, assigned to the person who chose it.

**Then, over and over:**
7. The team works in GitHub as they already do and closes issues there (by hand or with a commit that closes them).
8. Anyone opens the **dashboard** and sees, without updating anything: friendly feedback first, then progress per criterion, then the weekly summary, then each person's contribution.

**Success:** the team can answer "are we on track, and is the work fair?" from the dashboard alone.

## Screens and Layout

The app is a short step-by-step setup that ends in a dashboard. It leads the user through clear, small steps instead of dropping them in front of an empty text box.

1. **Create project:** a name field and a button to start.
2. **Team members:** a list where you add names and GitHub usernames.
3. **Paste assignment:** a large text box for the assignment and grading criteria, and a button to generate tasks.
4. **Connect repo:** a field for the GitHub repo.
5. **Review tasks:** the proposed tasks, each showing its title, description, weight, linked criterion and who does it, all editable. At the top: a fair-share bar per team member (for example "Sara: 7 / 10 points"). A "Send to GitHub" button.
6. **Dashboard:** top to bottom:
   1. **Feedback:** friendly tips and celebrations about what matters now.
   2. **Progress per criterion.**
   3. **Weekly summary** button and its result.
   4. **Contribution per person**, weighted by task size.
   5. At the bottom, a quiet **"Start a new project"** link (added in `4-spec`).

## Look and Feel

- **Minimal and clean, light theme:** generous white space, thin borders, rounded corners, and one accent color: GitHub-style green, which stands for progress and "done". Chosen in `4-spec` after comparing several visual directions; it replaces the earlier "soft colors, a little playful" direction.
- **GitHub-inspired details:** each person's contribution is shown as small green squares (one per task, darker for heavier tasks), and GitHub identifiers (usernames, repo name, issue numbers) use a monospace font, so the app visibly belongs next to GitHub.
- **Friendly through words, not decoration:** the friendliness lives in supportive copy and small celebrations ("Criterion 2 is complete! 🎉").
- It must feel like a finished, coherent product, not a technical demo, and avoid generic "AI app" styling (`scope.md > Inspiration & Identity`).
- The name "Repo Referee" could suggest a strict referee; here the referee is a friendly coach. All wording is supportive and positive, never confronting or blaming, in line with "AI guides, it doesn't take over".
- Exact colors, fonts and spacing: see `spec.md > Look and Feel`.

## Features and Behavior

### Project Setup
Source: `scope.md > The Core Loop`.

- As the team member who sets things up, I want to create a named project and add my teammates, so that the app knows whose work it is dividing.
  - [ ] A new project can be created by entering a name; the name is shown in the app from then on.
  - [ ] Team members can be added with a name and GitHub username, and removed again.
  - [ ] The steps happen in this order: name project → team members → paste assignment → connect repo → review tasks → send to GitHub.

### Task Generation
Source: `scope.md > The POC Boundary`.

- As a student team, I want the AI to turn our assignment into small, concrete tasks linked to the grading criteria, so that we don't depend on one or two people translating it.
  - [ ] After pasting a (fictional) data science assignment with criteria, a list of tasks appears.
  - [ ] Every task has a title, a short description of what "done" means, a weight, and a linked grading criterion.
  - [ ] Every grading criterion from the pasted text has at least one task linked to it.
  - [ ] The tasks are only about this one assignment; nothing from the wider data science lifecycle is mixed in.

### Reviewing and Editing Tasks
Source: `scope.md > Open Questions for the PRD` ("can the team edit the tasks before they go to GitHub?").

- As a team, we want to change anything the AI proposed, so that the plan is ours and not the AI's.
  - [ ] Title, description, weight, linked criterion and person can all be changed for every task.
  - [ ] Tasks can be deleted, and new tasks can be added under a criterion. *(Added in `4-spec`.)*
  - [ ] Changes are visible right away and are what gets sent to GitHub.

### Choosing Tasks Fairly
Source: `scope.md > Who It's For` ("tasks are split by who speaks up, not by who fits"; "the work ends up unevenly divided"), `scope.md > Open Questions for the PRD` ("what exactly counts as fair").

- As a team member, I want to choose my own tasks while seeing my fair share, so that I pick what suits me and the work still ends up evenly divided.
  - [ ] Each person's fair share is shown: the total weight of all tasks divided by the number of team members (for example 50 points / 5 people = 10 points each).
  - [ ] Each person has a bar showing the weight they have chosen against their fair share (for example "Sara: 7 / 10").
  - [ ] When someone chooses a task that puts them over their fair share, the app shows a friendly heads-up (for example "Ali is now at 14 / 10. Someone else has room for this task.") but still allows it.
  - [ ] "Send to GitHub" only becomes available once every task has a person.

### Sending Tasks to GitHub
Source: `scope.md > What "Working" Looks Like` step 2.

- As a team, we want one click to put all tasks into our repo, so that the tasks live where the work already happens.
  - [ ] One click on "Send to GitHub" creates every task as an issue in the connected test repo.
  - [ ] Each issue shows the task's title, description, weight and linked criterion, and is assigned to the person who chose it.
  - [ ] If a team member can't be assigned yet (for example, they haven't accepted the repo invitation), the app says so before anything is created and offers to send anyway. That person's issues are then created without an assignee, but they still say who chose them, and the dashboard still credits that person. *(Added in `4-spec`.)*
  - [ ] After sending, the user lands on the dashboard.

### Dashboard: Automatic Status
Source: `scope.md > The Unique Kernel`, `scope.md > What "Working" Looks Like` step 3.

- As a team member, I want the dashboard to follow GitHub by itself, so that nobody has to update anything.
  - [ ] When an issue is closed in GitHub (by hand or through a commit that closes it), the dashboard shows it as done without anyone touching the app. *(How quickly: see Open Questions.)*
  - [ ] There is no way to change a task's status inside the app; status only comes from GitHub.
  - [ ] An issue closed as "not planned" or "duplicate" doesn't count as done: that task is left out of progress and contribution. *(Added in `4-spec`.)*

### Dashboard: Feedback
Source: `scope.md > The Core Loop`, `scope.md > What "Working" Looks Like` step 4. Refined from scope's "warnings": the learner wants supportive feedback, not confronting warnings.

- As a team, we want friendly feedback at the top of the dashboard, so that we know what to do next and feel good about progress, without anyone being blamed.
  - [ ] Feedback is shown at the top of the dashboard, worded positively; it never names someone as falling behind.
  - [ ] **Team balance tip:** when a team member has (almost) finished the tasks they chose, the dashboard suggests they could help where it's busiest, for example "Sara is almost done with their tasks. Modelling has the most open work — maybe Sara can help out there?" The tip uses names, never gendered pronouns. *("Almost" and "busiest": see Open Questions.)*
  - [ ] **Celebration:** when every task of a criterion is closed, the dashboard celebrates it, for example "Criterion 2 is complete! 🎉"
  - [ ] When there is nothing new to say, the feedback area shows a short friendly message instead of disappearing.

### Dashboard: Progress per Criterion
Source: `scope.md > The POC Boundary`.

- As a team, we want to see how far we are on each grading criterion, so that at the end every criterion has actually been met.
  - [ ] Each grading criterion shows its progress, based on the weight of its closed tasks (for example "Criterion 3: Data quality – 60% done").
  - [ ] Closing a task in GitHub visibly moves the progress of its criterion.

### Dashboard: Weekly Summary
Source: `scope.md > The Core Loop`, `scope.md > What "Working" Looks Like` step 5.

- As a team, we want one button that writes a short summary of what we did, so that we don't have to write it ourselves.
  - [ ] One click produces a short, readable summary of what the team did, based on the tasks closed in GitHub.

### Dashboard: Contribution per Person
Source: `scope.md > The POC Boundary`.

- As a team, we want to see how much each person has contributed, weighted by task size, so that we can see whether the work is fair.
  - [ ] Each team member's contribution is shown as the weight of their closed tasks.
  - [ ] Closing a task in GitHub visibly changes the chart.

### Sharing the Board (View Only)
Source: added in the final review (learner decision), so the whole team can follow progress.

- As a teammate, I want to open the team board from a link, so that I can follow everyone's progress without being able to change the tasks.
  - [ ] "Share board" on the dashboard shows a view-only link with "Copy link".
  - [ ] The link opens the live board marked "View only", without anything that changes the project (no summary button, no start over, no account buttons).
  - [ ] Every issue sent to GitHub links to the board.
  - [ ] In the prototype the link works where Repo Referee runs (this laptop); the app is designed so it works for the whole team once Repo Referee is online.

### Starting Over
Source: added in `4-spec` (learner decision), to start a new assignment or practice the demo again.

- As the team member who set things up, I want to start a new project, so that we can begin a new assignment or rehearse the demo from the start.
  - [ ] A "Start a new project" option at the bottom of the dashboard asks for confirmation, then clears the project from the app and returns to "Create project".
  - [ ] The issues already in GitHub are left untouched.

## States and Boundaries

- **First use** — the start page says what Repo Referee does and for whom, then asks the first question: the project name. No sign-in comes first.
- **Coming back** — the project, team and tasks are kept on the laptop; the start page offers "Continue your project". With a profile, it says "Welcome back" and lists "Your projects".
- **Dashboard before anything is closed** — progress is 0% and contributions are empty, shown with a friendly message rather than an empty chart.
- **Empty or unusable assignment text** — *(assumption)* the app explains that it needs the assignment and its grading criteria and lets the user try again; no tasks are generated.
- **AI can't generate tasks** — *(assumption)* a friendly error message and a "try again" button; nothing is lost.
- **Repo can't be reached** — *(assumption)* a clear message that the repo was not found or access is missing; tasks are not sent until it works.
- **Tasks nobody chose** — "Send to GitHub" is not available yet; the review screen shows which tasks still need a person.
- **Teammate hasn't accepted the repo invitation** — the app names who can't be assigned yet and offers to send anyway (see `Sending Tasks to GitHub`).
- **One team, one screen** — the team chooses tasks together on one screen. A profile (a name and a GitHub username; the password field only shows what a real account would ask, nothing is saved or checked) only saves projects on this laptop; it is not a personal login per teammate.

## Product Decisions

- **Start by creating and naming a project** — gives the user a logical starting point and leads them through the app in clear, small steps, instead of an empty text box.
- **Setup order: team members → paste assignment → connect repo → review tasks → send** — the learner's chosen order.
- **All task fields are editable before sending** — the AI guides and helps, it doesn't take over; the team stays in control.
- **Team members choose their own tasks, guided towards a fair share** — people pick what suits them without the work becoming unevenly divided.
- **Going over your fair share gives a heads-up, not a block** — the team keeps control.
- **All tasks are divided from the start** — the team is expected to share out every task during setup, so "Send to GitHub" only works once every task has a person.
- **One screen, profiles only to save** — the team chooses together. Changed in the final review: the app now shows how a real product would let you find your projects again. You save a project by creating a profile (never as the first step), and a profile keeps several projects. Everything stays on this laptop; the screens don't say so (the learner's choice for the video), the README does; real online accounts stay deferred.
- **Calm setup cards, a live team and "Add yourself"** — added in the final review. The setup pages are plain cards without decoration; the team step shows the team growing as a row of GitHub pictures (no limit, no count), a help popover for the username and a note that people can be added until sending. "Add yourself" uses the GitHub account the token belongs to.
- **One board = one assignment** — the board treats that assignment as the whole goal and mixes in nothing else. This refines `scope.md`, which still described tasks per data science lifecycle phase: in the learner's projects, each phase is its own assignment of about three weeks.
- **Dashboard order: feedback → progress per criterion → weekly summary → contribution per person** — what matters now comes first.
- **Friendly feedback, not confronting warnings** — it should feel like good feedback from a coach, never negative or blaming.
- **The team can add and delete tasks before sending** — the AI proposes, the team decides (decided in `4-spec`).
- **Sending works even if someone hasn't accepted the invitation yet** — after a clear heads-up, that person's issues go out unassigned but still name them (decided in `4-spec`).
- **Only issues closed as "completed" count as done** — tasks closed as "not planned" or "duplicate" drop out of the totals (decided in `4-spec`).
- **A "Start a new project" option** — for a new assignment or for practicing the demo; the GitHub issues stay (decided in `4-spec`).
- **Two kinds of feedback: team balance tip and celebration** — the learner found these the most fun; the balance tip focuses on helping each other instead of on who is behind.
- **Look: minimal and light, one green accent, GitHub-inspired details** — the learner preferred a minimalist style over the soft, playful directions; friendliness comes from the copy and the celebrations (decided in `4-spec`).
- **Designed for online, the prototype runs locally** — the learner wants teammates to see the board, like an invitation in a board app. "Share board" gives a view-only link, and every issue links to it. Hosting the app online today would expose the API key and GitHub token to anyone with the address, so the prototype keeps running on this laptop and the link uses the app's online address once it has one (decided in the final review).
- **Name: Repo Referee** — kept from scope; the learner likes it.

## What We're Building

- Step-by-step setup: create and name a project, add team members, paste assignment and criteria, connect one GitHub repo.
- AI-generated tasks for that one assignment, each with title, description, weight and linked criterion.
- A review screen where every task field is editable, tasks can be added or deleted, and team members choose their tasks, with a fair-share bar per person and a friendly over-share heads-up; sending only once every task has a person.
- One click to create all tasks as assigned GitHub issues, with a "send anyway" option when someone hasn't accepted the repo invitation yet.
- A dashboard that reads status from GitHub by itself, with friendly feedback (team balance tip and celebration), progress per criterion, a weekly summary button, and contribution per person.
- A "Start a new project" option to begin again.
- A start page, a profile to save projects ("Save project", "Welcome back", "Your projects", "New project"), a live team strip, and "Add yourself" (added in the final review).
- "Share board": a view-only board for teammates, linked from every issue (added in the final review).

## Deferred From the POC

- **Online accounts, logins and hosting** — profiles stay on this laptop, and the password field on "Save project" is not saved or checked (the learner wanted the screens to look like the finished product for the video, so they don't mention the prototype; the README explains it); real accounts would need hosting, a database and secure sign-in. The view-only board link is designed for an online app, but in the prototype it works on this laptop.
- **Several repos per project** — each project still connects one repo (`scope.md > Later`).
- **Order between tasks ("task C waits for task A")** — parked during the PRD interview; `4-spec` confirmed it stays out of the proof of concept.
- **Other feedback types** (next-focus tip, big-tasks tip, and others) — keep the proof of concept small; only the team balance tip and the celebration are in.

## Possible Later Enhancements

- Reading progress from the shared Word report (needs Microsoft sign-in) (`scope.md > Later`).
- Smarter task suggestions based on each person's skills and available time (`scope.md > Later`).
- More feedback types, such as a project deadline so the app can give a friendly tip when time is getting short.

## Non-Goals

- **A board people update by hand** — exactly why the old board failed; status only comes from GitHub (`scope.md > Explicitly Cut`).
- **Tracking the whole data science lifecycle** — one board is one assignment.
- **The AI deciding who does what** — people choose; the app only guides.
- **Real school assignments in the public demo** — the demo uses a self-written fictional assignment (`scope.md > Explicitly Cut`).

## Open Questions

- **Order between tasks.** Should tasks be able to wait for each other ("you can't do C before A is done")? *Decided in `4-spec`:* not part of the proof of concept.
- **Weight scale.** *Decided in `4-spec`:* whole numbers from 1 to 5 points.
- **Team balance tip details.** *Decided in `4-spec`:* "almost done" means at least 80% of the points of the tasks that person chose are closed (not 80% of the fair share, which someone who chose less could never reach); "where it's busiest" means the criterion with the most open points. See `spec.md > Feedback Rules`.
- **How quickly the dashboard follows GitHub.** *Decided in `4-spec`:* the dashboard checks GitHub every 10 seconds, and immediately when it is opened or brought back into view.
- **Name check.** Make sure "Repo Referee" isn't already a known product before submitting. Can wait until `6-ship`.
