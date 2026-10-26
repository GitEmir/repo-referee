"""Load and save the projects and profiles in data/, the app's only saved state.

data/projects/<key>.json   one file per project
data/profiles.json         the profiles on this laptop (a name and a GitHub username, no password)
data/state.json            which project is open and who is signed in

Most of the app works on "the open project": load(), save() and update() read and
write that one. Every change is written to a temporary file first and then swapped
in, so a crash never leaves a half-written file behind.
"""

import json
import logging
import os
import re
import secrets
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEGACY_FILE = "project.json"  # where the one project lived before there were several
VERSION = 1

log = logging.getLogger(__name__)

# One lock for every read-modify-write, because Flask serves requests on threads.
_lock = threading.RLock()


def _projects_dir() -> Path:
    return DATA_DIR / "projects"


def _project_file(key: str) -> Path:
    return _projects_dir() / f"{key}.json"


def _state_file() -> Path:
    return DATA_DIR / "state.json"


def _profiles_file() -> Path:
    return DATA_DIR / "profiles.json"


def now_iso() -> str:
    """Current UTC time as an ISO 8601 string without microseconds, e.g. 2026-10-20T09:12:00Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_key() -> str:
    """A short random key that tells this project's GitHub issues apart from other projects'."""
    return secrets.token_hex(4)


def new_project(name: str, owner_profile: str | None = None) -> dict:
    """A fresh project with only a name, in the shape of spec.md > Data Model.

    `owner_profile` is the profile it is saved to; None means it isn't saved to a profile yet.
    """
    return {
        "version": VERSION,
        "project": {"name": name, "created_at": now_iso(), "key": new_key()},
        "owner_profile": owner_profile,
        "team": [],
        "assignment_text": "",
        "criteria": [],
        "repo": None,
        "tasks": [],
        "sent_at": None,
        "summary": None,
        "share_token": None,  # the secret part of the view-only board link, made when it's first needed
        "next_ids": {},
    }


# --- Small file helpers ------------------------------------------------------------------


def _read_json(path: Path):
    """The parsed file, or None when it is missing or can't be read as JSON."""
    if not path.exists():
        return None
    try:
        # utf-8-sig also accepts a file that an editor saved with a byte order mark.
        with path.open(encoding="utf-8-sig") as f:
            return json.load(f)
    except ValueError:
        return None


def _write_json(path: Path, data) -> None:
    """Write safely: temporary file first, then replace the real file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _state() -> dict:
    data = _read_json(_state_file())
    state = {"active": None, "profile_id": None}
    if isinstance(data, dict):
        state.update({key: data.get(key) for key in state})
    return state


def _set_state(**changes) -> None:
    state = _state()
    state.update(changes)
    _write_json(_state_file(), state)


def _migrate_legacy() -> None:
    """Move a data/project.json from before there were several projects into data/projects/."""
    legacy = DATA_DIR / LEGACY_FILE
    if not legacy.exists():
        return
    data = _read_json(legacy)
    if not isinstance(data, dict) or not isinstance(data.get("project", {}), dict):
        target = _move_to_archive(legacy, "project-unreadable")
        log.warning("data/project.json could not be read; moved it to %s", target)
        return
    project = data.setdefault("project", {})
    if not project.get("key"):
        project["key"] = new_key()
    _write_json(_project_file(project["key"]), data)
    legacy.unlink()
    if not _state()["active"]:
        _set_state(active=project["key"])


def _load_file(key: str) -> dict | None:
    """One project file, with any missing fields filled in; None when it is missing.

    A file that can't be read as a project (for example after editing it by hand) is
    moved into data/archive/ and treated as no project, so the app keeps working.
    """
    path = _project_file(key)
    if not path.exists():
        return None
    data = _read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("project", {}), dict):
        target = _move_to_archive(path, "project-unreadable")
        log.warning("%s could not be read; moved it to %s", path.name, target)
        return None
    # Fill in anything a hand-edited file is missing, so every page can rely on the shape.
    project = new_project("")
    project["project"] = {"name": "", "created_at": None, "key": key, **(data.get("project") or {})}
    project.update({field: value for field, value in data.items() if field != "project"})
    return project


# --- The open project ----------------------------------------------------------------------


def load() -> dict | None:
    """Return the open project, or None when no project is open (first use, or a new one)."""
    with _lock:
        _migrate_legacy()
        key = _state()["active"]
        if not key:
            return None
        project = _load_file(key)
        if project is None:
            _set_state(active=None)
        return project


def save(project: dict) -> None:
    """Write the project to its own file and make it the open project."""
    with _lock:
        info = project.setdefault("project", {})
        if not info.get("key"):
            info["key"] = new_key()
        _write_json(_project_file(info["key"]), project)
        if _state()["active"] != info["key"]:
            _set_state(active=info["key"])


@contextmanager
def update():
    """Load the open project, let the caller change it, and save it again as one step.

    Yields None when no project is open; nothing is saved in that case.
    """
    with _lock:
        project = load()
        yield project
        if project is not None:
            save(project)


def close_project() -> None:
    """Close the open project without deleting it (it stays in "Your projects")."""
    with _lock:
        _set_state(active=None)


def archive() -> Path | None:
    """Move the open project into data/archive/ and close it (a project not saved to a profile)."""
    with _lock:
        key = _state()["active"]
        _set_state(active=None)
        if not key or not _project_file(key).exists():
            return None
        return _move_to_archive(_project_file(key), "project")


def delete_project(key: str, profile_id: str) -> Path | None:
    """Remove one of the profile's saved projects from "Your projects".

    Nothing is deleted for good: the file moves into data/archive/. Returns where it went,
    or None when the project isn't theirs or doesn't exist.
    """
    with _lock:
        project = _load_file(key) if re.fullmatch(r"[0-9a-f]{8}", key or "") else None
        if project is None or project.get("owner_profile") != profile_id:
            return None
        if _state()["active"] == key:
            _set_state(active=None)
        return _move_to_archive(_project_file(key), "project-deleted")


def open_project(key: str, profile_id: str) -> dict | None:
    """Open one of the profile's saved projects; None when it isn't theirs or doesn't exist."""
    with _lock:
        project = _load_file(key) if re.fullmatch(r"[0-9a-f]{8}", key or "") else None
        if project is None or project.get("owner_profile") != profile_id:
            return None
        _set_state(active=key)
        return project


def projects_of(profile_id: str) -> list[dict]:
    """Every project saved to this profile, newest first."""
    with _lock:
        _migrate_legacy()
        projects = []
        for path in sorted(_projects_dir().glob("*.json")) if _projects_dir().exists() else []:
            project = _load_file(path.stem)
            if project and project.get("owner_profile") == profile_id:
                projects.append(project)
        return sorted(projects, key=lambda p: p["project"].get("created_at") or "", reverse=True)


def find_shared(token: str) -> dict | None:
    """The project whose view-only board link has this token; None when no project has it.

    Read only: it doesn't open the project, so a teammate's visit changes nothing.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", token or ""):
        return None
    with _lock:
        _migrate_legacy()
        for path in sorted(_projects_dir().glob("*.json")) if _projects_dir().exists() else []:
            project = _load_file(path.stem)
            if project and secrets.compare_digest(str(project.get("share_token") or ""), token):
                return project
        return None


# --- Profiles ------------------------------------------------------------------------------


def profiles() -> list[dict]:
    """The profiles on this laptop, oldest first."""
    with _lock:
        data = _read_json(_profiles_file())
        return [p for p in data if isinstance(p, dict) and p.get("id")] if isinstance(data, list) else []


def signed_in() -> dict | None:
    """The profile that is signed in, or None."""
    with _lock:
        profile_id = _state()["profile_id"]
        return next((p for p in profiles() if p["id"] == profile_id), None) if profile_id else None


def create_profile(name: str, github: str | None) -> dict:
    """Add a profile (a name and an optional GitHub username) and return it."""
    with _lock:
        profile = {"id": "p" + secrets.token_hex(3), "name": name, "github": github or None, "created_at": now_iso()}
        _write_json(_profiles_file(), profiles() + [profile])
        return profile


def sign_in(profile_id: str) -> dict | None:
    """Sign in, and save the open project to this profile if it isn't saved to one yet."""
    with _lock:
        profile = next((p for p in profiles() if p["id"] == profile_id), None)
        if profile is None:
            return None
        project = load()
        if project is not None and not project.get("owner_profile"):
            project["owner_profile"] = profile_id
            save(project)
        elif project is not None and project.get("owner_profile") != profile_id:
            _set_state(active=None)  # someone else's project: don't keep it open
        _set_state(profile_id=profile_id)
        return profile


def sign_out() -> None:
    """Sign out. A project saved to the profile closes; one that isn't saved stays open."""
    with _lock:
        project = load()
        if project is not None and project.get("owner_profile"):
            _set_state(active=None)
        _set_state(profile_id=None)


# --- Reset ---------------------------------------------------------------------------------


def reset_all() -> Path | None:
    """"Reset demo": move every project, the profiles and the state into one folder in
    data/archive/, so the next page is a first visit. Nothing is deleted."""
    with _lock:
        _migrate_legacy()
        parts = [p for p in (_projects_dir(), _profiles_file(), _state_file()) if p.exists()]
        if not parts:
            return None
        target = DATA_DIR / "archive" / f"reset-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}"
        counter = 2
        while target.exists():
            target = target.with_name(f"{target.name}-{counter}")
            counter += 1
        target.mkdir(parents=True)
        for part in parts:
            os.replace(part, target / part.name)
        return target


# --- Archive and IDs -----------------------------------------------------------------------


def _move_to_archive(path: Path, name: str) -> Path:
    archive_dir = DATA_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    target = archive_dir / f"{name}-{stamp}.json"
    counter = 2
    while target.exists():
        target = archive_dir / f"{name}-{stamp}-{counter}.json"
        counter += 1
    os.replace(path, target)
    return target


def next_id(project: dict, prefix: str, items: list[dict]) -> str:
    """A new short ID such as m3 or t12 that has never been used in this project.

    IDs are never reused, so a page left open in another tab can't act on someone
    who was removed and replaced in the meantime.
    """
    numbers = [
        int(match.group(1))
        for item in items
        if (match := re.fullmatch(rf"{prefix}(\d+)", str(item.get("id", ""))))
    ]
    counters = project.setdefault("next_ids", {})
    number = max(counters.get(prefix, 1), max(numbers, default=0) + 1)
    counters[prefix] = number + 1
    return f"{prefix}{number}"
