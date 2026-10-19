"""Load and save data/project.json, the app's only saved state.

Every change is written to a temporary file first and then swapped in, so a
crash never leaves a half-written project behind.
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
FILE_NAME = "project.json"
VERSION = 1

log = logging.getLogger(__name__)

# One lock for every read-modify-write, because Flask serves requests on threads.
_lock = threading.RLock()


def _project_file() -> Path:
    return DATA_DIR / FILE_NAME


def now_iso() -> str:
    """Current UTC time as an ISO 8601 string without microseconds, e.g. 2026-10-20T09:12:00Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_key() -> str:
    """A short random key that tells this project's GitHub issues apart from other projects'."""
    return secrets.token_hex(4)


def new_project(name: str) -> dict:
    """A fresh project with only a name, in the shape of spec.md > Data Model."""
    return {
        "version": VERSION,
        "project": {"name": name, "created_at": now_iso(), "key": new_key()},
        "team": [],
        "assignment_text": "",
        "criteria": [],
        "repo": None,
        "tasks": [],
        "sent_at": None,
        "summary": None,
        "next_ids": {},
    }


def load() -> dict | None:
    """Return the saved project, or None when there is no project yet (first use).

    A file that can't be read as a project (for example after editing it by hand) is
    moved into data/archive/ and treated as no project, so the app keeps working.
    """
    path = _project_file()
    with _lock:
        if not path.exists():
            return None
        try:
            # utf-8-sig also accepts a file that an editor saved with a byte order mark.
            with path.open(encoding="utf-8-sig") as f:
                data = json.load(f)
        except ValueError:
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("project", {}), dict):
            target = _move_to_archive(path, "project-unreadable")
            log.warning("data/project.json could not be read; moved it to %s", target)
            return None
        # Fill in anything a hand-edited file is missing, so every page can rely on the shape.
        project = new_project("")
        project["project"] = {"name": "", "created_at": None, "key": None, **(data.get("project") or {})}
        project.update({key: value for key, value in data.items() if key != "project"})
        return project


def save(project: dict) -> None:
    """Write the project safely: temporary file first, then replace the real file."""
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix="project-", suffix=".tmp", dir=DATA_DIR)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump(project, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, _project_file())
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise


@contextmanager
def update():
    """Load the project, let the caller change it, and save it again as one step.

    Yields None when there is no project yet; nothing is saved in that case.
    """
    with _lock:
        project = load()
        yield project
        if project is not None:
            save(project)


def archive() -> Path | None:
    """Move project.json into data/archive/ (used by "Start a new project")."""
    with _lock:
        path = _project_file()
        if not path.exists():
            return None
        return _move_to_archive(path, "project")


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
