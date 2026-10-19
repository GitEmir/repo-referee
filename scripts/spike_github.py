"""Spike: can we create an assigned issue in the test repo and read back how it was closed?

Run from the project folder, one command at a time (REPO is owner/name):

    uv run python scripts/spike_github.py REPO check YOUR_LOGIN OTHER_LOGIN
    uv run python scripts/spike_github.py REPO label
    uv run python scripts/spike_github.py REPO create YOUR_LOGIN
    uv run python scripts/spike_github.py REPO list
    uv run python scripts/spike_github.py REPO try-unassignable OTHER_LOGIN

check            repo details, then whether each login can be assigned (expect yes / no)
label            make sure the green repo-referee label exists
create           create one test issue assigned to that login, with the label
list             every Repo Referee issue with its state and state_reason
try-unassignable create an issue for a login that can't be assigned, to see what GitHub does
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from referee import github_client as gh  # noqa: E402

TEST_BODY = (
    "**Done when:** this test issue has been closed once as completed and once as not planned.\n\n"
    "_Created by the Repo Referee GitHub spike. It can be deleted afterwards._"
)


def main(argv: list[str]) -> int:
    load_dotenv(ROOT / ".env")
    if len(argv) < 2:
        print(__doc__)
        return 2
    repo, command, args = argv[0], argv[1], argv[2:]

    try:
        if command == "check":
            info = gh.check_repo(repo)
            print(f"repo           {info['full_name']}  ({info['html_url']})")
            print(f"default branch {info['default_branch']}")
            for login in args:
                print(f"@{login:<14} {'can be assigned (204)' if gh.can_be_assigned(repo, login) else 'cannot be assigned (404)'}")
        elif command == "label":
            gh.ensure_label(repo)
            print(f"label '{gh.LABEL}' is present")
        elif command == "create":
            login = args[0] if args else None
            gh.ensure_label(repo)
            issue = gh.create_issue(repo, "Repo Referee spike: test issue", TEST_BODY, login)
            print(f"created #{issue['number']} assigned to {('@' + login) if login else 'nobody'}: {issue['html_url']}")
        elif command == "list":
            issues = gh.list_referee_issues(repo)
            if not issues:
                print("no Repo Referee issues yet")
            for issue in issues:
                print(f"#{issue['number']:<5} state={issue['state']:<7} state_reason={issue['state_reason']!s:<12} closed_at={issue['closed_at']}")
        elif command == "try-unassignable":
            login = args[0]
            print(f"assignable according to the check: {gh.can_be_assigned(repo, login)}")
            try:
                issue = gh.create_issue(repo, "Repo Referee spike: unassignable test", TEST_BODY, login)
                print(f"GitHub accepted it: #{issue['number']} {issue['html_url']} (open it to see whether @{login} was dropped)")
            except gh.GitHubError as error:
                print(f"GitHub refused it: {error}")
        else:
            print(f"unknown command '{command}'\n{__doc__}")
            return 2
    except gh.GitHubError as error:
        print(f"GitHub call failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
