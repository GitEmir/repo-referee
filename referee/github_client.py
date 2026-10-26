"""The only code that talks to GitHub.

Five small REST calls: check the repo, check who can be assigned, make sure the
`repo-referee` label exists, create an issue, and list the Repo Referee issues.
One more tells whose token it is, to suggest "Add yourself".
"""

import os
import re
from urllib.parse import urlsplit

import requests

API = "https://api.github.com"
TIMEOUT_SECONDS = 15
LABEL = "repo-referee"
LABEL_COLOR = "2DA44E"
LABEL_DESCRIPTION = "Task created by Repo Referee"


class GitHubError(Exception):
    """A GitHub call failed. `kind` tells the app which friendly message to show.

    Kinds: missing_token, bad_token, forbidden, rate_limited, not_found,
    issues_disabled, invalid, unreachable, other.
    """

    def __init__(self, kind: str, message: str = "", status: int | None = None):
        super().__init__(f"{kind} ({status}): {message}" if status else f"{kind}: {message}")
        self.kind = kind
        self.status = status
        self.message = message


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise GitHubError("missing_token", "GITHUB_TOKEN is not set in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _request(method: str, path: str, *, expected: tuple[int, ...], **kwargs) -> requests.Response:
    """Send one request; return the response when its status is in `expected`, else raise."""
    try:
        response = requests.request(method, f"{API}{path}", headers=_headers(), timeout=TIMEOUT_SECONDS, **kwargs)
    except requests.RequestException as error:
        raise GitHubError("unreachable", str(error)) from error

    if response.status_code in expected:
        return response
    raise _error_for(response)


def _error_for(response: requests.Response) -> GitHubError:
    status = response.status_code
    try:
        message = response.json().get("message", "")
    except ValueError:
        message = response.text[:200]
    if status == 401:
        return GitHubError("bad_token", message, status)
    if status in (403, 429) and (response.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in message.lower()):
        return GitHubError("rate_limited", message, status)
    if status == 403:
        return GitHubError("forbidden", message, status)
    if status == 404:
        return GitHubError("not_found", message, status)
    if status == 410:
        return GitHubError("issues_disabled", message, status)
    if status == 422:
        return GitHubError("invalid", message, status)
    return GitHubError("other", message, status)


_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}"
_REPO = r"[A-Za-z0-9._-]{1,100}"
_FULL_NAME = re.compile(rf"({_OWNER})/({_REPO})")


def parse_repo_name(text: str | None) -> str | None:
    """Turn "owner/repo" or a github.com link into "owner/repo"; None when it isn't one.

    Accepts https://github.com/owner/repo, with or without .git, a trailing slash or a
    deeper path such as /issues.
    """
    value = (text or "").strip()
    if not value:
        return None
    if "github.com" in value.lower():
        if "://" not in value:
            value = "https://" + value
        parts = urlsplit(value)
        if parts.hostname not in ("github.com", "www.github.com"):
            return None
        segments = [segment for segment in parts.path.split("/") if segment]
        if len(segments) < 2:
            return None
        value = f"{segments[0]}/{segments[1]}"
    value = value.strip("/")
    if value.lower().endswith(".git"):
        value = value[:-4]
    match = _FULL_NAME.fullmatch(value)
    if not match or match.group(2) in (".", ".."):
        return None
    return value


_owner_cache: dict = {}


def token_owner() -> dict | None:
    """Whose GitHub token is in .env: {"login", "name"}, or None when that can't be told.

    Used only to suggest "Add yourself" and the profile's GitHub username, so any problem
    just means no suggestion. A good answer is kept until the app restarts (as is .env).
    """
    if "owner" in _owner_cache:
        return _owner_cache["owner"]
    try:
        response = requests.get(f"{API}/user", headers=_headers(), timeout=5)
    except (GitHubError, requests.RequestException):
        return None
    if response.status_code != 200:
        return None
    data = response.json()
    owner = {"login": data.get("login"), "name": data.get("name") or ""}
    if owner["login"]:
        _owner_cache["owner"] = owner
        return owner
    return None


def check_repo(full_name: str) -> dict:
    """Check that the repo exists and the token can see it.

    Returns {"full_name", "html_url", "default_branch"}. Raises GitHubError with kind
    bad_token (401) or not_found (404: missing, or no access for this token).
    """
    data = _request("GET", f"/repos/{full_name}", expected=(200,)).json()
    return {"full_name": data["full_name"], "html_url": data["html_url"], "default_branch": data["default_branch"]}


def can_be_assigned(full_name: str, login: str) -> bool:
    """True when `login` can be assigned issues in the repo (204), False when not (404).

    404 means: not a collaborator, or the repo invitation hasn't been accepted yet.
    """
    try:
        _request("GET", f"/repos/{full_name}/assignees/{login}", expected=(204,))
    except GitHubError as error:
        if error.kind == "not_found":
            return False
        raise
    return True


def ensure_label(full_name: str) -> None:
    """Create the green `repo-referee` label unless the repo already has it."""
    try:
        _request("GET", f"/repos/{full_name}/labels/{LABEL}", expected=(200,))
        return
    except GitHubError as error:
        if error.kind != "not_found":
            raise
    payload = {"name": LABEL, "color": LABEL_COLOR, "description": LABEL_DESCRIPTION}
    try:
        _request("POST", f"/repos/{full_name}/labels", expected=(201,), json=payload)
    except GitHubError as error:
        # 422 "already_exists": someone created it in the meantime, which is fine.
        if error.kind != "invalid":
            raise


def create_issue(full_name: str, title: str, body: str, login: str | None) -> dict:
    """Create one labelled issue, assigned to `login` (or to nobody when login is None).

    Returns {"number", "html_url"}.
    """
    payload = {"title": title, "body": body, "labels": [LABEL]}
    if login:
        payload["assignees"] = [login]
    data = _request("POST", f"/repos/{full_name}/issues", expected=(201,), json=payload).json()
    return {"number": data["number"], "html_url": data["html_url"]}


def list_referee_issues(full_name: str) -> list[dict]:
    """All Repo Referee issues in the repo, open and closed, in one call (up to 100).

    Each item: {"number", "state", "state_reason", "closed_at", "html_url", "body"}.
    Pull requests that happen to carry the label are skipped.
    """
    params = {"state": "all", "labels": LABEL, "per_page": 100}
    items = _request("GET", f"/repos/{full_name}/issues", expected=(200,), params=params).json()
    return [
        {
            "number": item["number"],
            "state": item["state"],
            "state_reason": item.get("state_reason"),
            "closed_at": item.get("closed_at"),
            "html_url": item["html_url"],
            "body": item.get("body") or "",
        }
        for item in items
        if "pull_request" not in item
    ]
