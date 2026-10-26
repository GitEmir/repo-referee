"""The only code that talks to Claude.

generate_plan() turns a pasted assignment into grading criteria and weighted tasks.
Keeping every Claude call in this one module means the model, or even the provider,
can be swapped in one place.
"""

import os
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

DEFAULT_MODEL = "claude-opus-5-5"
TIMEOUT_SECONDS = 120.0
PLAN_MAX_TOKENS = 16000
# Server-side refusal fallback: if Claude declines, the API re-runs the request on a
# suitable fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class Criterion(BaseModel):
    id: str  # "c1", "c2", ... in the order they appear in the text
    title: str  # e.g. "Data quality"
    description: str  # one sentence: what the grader looks for


class PlannedTask(BaseModel):
    title: str  # short, starts with a verb
    done_when: str  # one or two sentences: what "done" means
    weight: Literal[1, 2, 3, 4, 5]  # 1 ≈ an hour, 3 ≈ a day, 5 ≈ several days
    criterion_id: str


class Plan(BaseModel):
    usable: bool  # false if the text has no assignment or criteria
    criteria: list[Criterion]
    tasks: list[PlannedTask]


PLAN_INSTRUCTIONS = """\
You help a university student team of about five people divide one project assignment \
into clear, fairly sized tasks. The user message is the assignment text, including its \
grading criteria.

Grading criteria:
- Take the grading criteria from the text. Keep their names and their order.
- Give them the ids c1, c2, c3, ... in the order they appear.
- Describe each one in one sentence: what the grader looks for.

Tasks:
- Create small, concrete tasks for this one assignment only. Include nothing the \
assignment doesn't ask for: no steps from a wider project lifecycle and no generic \
project-management tasks.
- Make only the tasks the assignment really needs, each a logical piece of work one \
teammate can pick up: usually 6 to 15 in total, fewer for a small assignment. Don't split \
the work into tiny steps.
- Title: short, and starting with a verb.
- done_when: one or two sentences that tell a teammate exactly when the task is done.
- weight: a whole number for the effort. 1 is about an hour, 2 about half a day, \
3 about a day, 4 about two days, 5 several days.
- Link each task to exactly one criterion with criterion_id, and give every criterion \
at least one task.

Write the criteria and tasks in the language of the assignment.

If the text has no recognizable assignment or no grading criteria, set usable to false \
and return empty lists."""


class GenerationError(Exception):
    """Claude couldn't produce a usable answer. `reason` says why, for logging."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def model_name() -> str:
    return os.getenv("CLAUDE_MODEL") or DEFAULT_MODEL


def _client() -> anthropic.Anthropic:
    # One retry for rate limits, overloads and dropped connections; the page offers
    # "Try again" for anything beyond that.
    return anthropic.Anthropic(timeout=TIMEOUT_SECONDS, max_retries=1)


def request_plan(assignment_text: str, feedback: str | None = None):
    """Send the assignment to Claude and return the full response.

    `feedback` is an extra note for a second attempt, for example which criteria
    still have no task. Raises GenerationError when the call fails or the answer
    can't be used.
    """
    content = assignment_text
    if feedback:
        content = f"{assignment_text}\n\n---\nNote about your previous answer: {feedback}"
    try:
        response = _client().beta.messages.parse(
            model=model_name(),
            max_tokens=PLAN_MAX_TOKENS,
            system=PLAN_INSTRUCTIONS,
            messages=[{"role": "user", "content": content}],
            output_format=Plan,
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.APITimeoutError as error:
        raise GenerationError("timeout", str(error)) from error
    except anthropic.APIConnectionError as error:
        raise GenerationError("connection", str(error)) from error
    except anthropic.AuthenticationError as error:
        raise GenerationError("authentication", str(error)) from error
    except anthropic.APIStatusError as error:
        raise GenerationError(f"http_{error.status_code}", str(error)) from error
    except anthropic.APIError as error:
        raise GenerationError("api", str(error)) from error
    except ValidationError as error:
        # parse() checks the answer against Plan itself: an answer that was cut off or
        # declined in plain text isn't valid JSON and ends up here.
        raise GenerationError("unparsed", str(error)) from error

    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None) if response.stop_details else None
        raise GenerationError("refusal", f"category={category}")
    if response.stop_reason == "max_tokens":
        raise GenerationError("max_tokens", "the answer was cut off")
    if response.parsed_output is None:
        raise GenerationError("unparsed", f"stop_reason={response.stop_reason}")
    return response


def generate_plan(assignment_text: str, feedback: str | None = None) -> Plan:
    """Turn the assignment text into grading criteria and weighted tasks."""
    return request_plan(assignment_text, feedback).parsed_output


SUMMARY_MAX_TOKENS = 8000

SUMMARY_INSTRUCTIONS = """\
You write the weekly summary on a student team's project dashboard. The user message lists \
the tasks the team closed in GitHub during the period.

Write 3 to 6 sentences in English, as one short paragraph:
- what the team finished, and which grading criteria moved forward;
- credit people by name for what they closed.

Tone: a positive, supportive coach. Never blame anyone, and never point out who did less.
Use people's names, never gendered pronouns.
Mention only what is in the list: no guesses about other work, plans or deadlines.
Plain sentences only: no heading, no bullet points, no emoji."""


def write_summary(project_name: str, closed_tasks: list[dict], period_start: str, period_end: str) -> str:
    """A short, positive summary of the tasks closed in the period. Raises GenerationError."""
    lines = [
        f"- {task['title']} (criterion {task['criterion']}, weight {task['weight']}, "
        f"closed by {task['person']} on {task['closed_at']})"
        for task in closed_tasks
    ]
    content = f"Project: {project_name}\nPeriod: {period_start} to {period_end}\n\nClosed tasks:\n" + "\n".join(lines)
    try:
        response = _client().beta.messages.create(
            model=model_name(),
            max_tokens=SUMMARY_MAX_TOKENS,
            system=SUMMARY_INSTRUCTIONS,
            messages=[{"role": "user", "content": content}],
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.APITimeoutError as error:
        raise GenerationError("timeout", str(error)) from error
    except anthropic.APIConnectionError as error:
        raise GenerationError("connection", str(error)) from error
    except anthropic.AuthenticationError as error:
        raise GenerationError("authentication", str(error)) from error
    except anthropic.APIStatusError as error:
        raise GenerationError(f"http_{error.status_code}", str(error)) from error
    except anthropic.APIError as error:
        raise GenerationError("api", str(error)) from error

    if response.stop_reason == "refusal":
        raise GenerationError("refusal")
    if response.stop_reason == "max_tokens":
        raise GenerationError("max_tokens", "the summary was cut off")
    text = " ".join(block.text.strip() for block in response.content if block.type == "text").strip()
    if not text:
        raise GenerationError("empty", f"stop_reason={response.stop_reason}")
    return text
