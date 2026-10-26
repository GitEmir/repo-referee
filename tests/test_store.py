"""Tests for referee/store.py: several projects, profiles, and moving an old project.json over."""

import json

import pytest

from referee import store


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    return tmp_path


def test_first_use_has_no_open_project():
    assert store.load() is None
    assert store.signed_in() is None


def test_save_makes_the_project_the_open_one():
    project = store.new_project("Churn")
    store.save(project)
    assert store.load()["project"]["name"] == "Churn"
    assert (store.DATA_DIR / "projects" / f"{project['project']['key']}.json").exists()


def test_an_old_project_json_moves_into_projects(data_dir):
    old = store.new_project("Old one")
    old["project"].pop("key")
    (data_dir / "project.json").write_text(json.dumps(old), encoding="utf-8")
    project = store.load()
    assert project["project"]["name"] == "Old one" and project["project"]["key"]
    assert not (data_dir / "project.json").exists()
    assert project["owner_profile"] is None


def test_signing_in_saves_the_open_project_to_the_profile():
    store.save(store.new_project("Draft"))
    profile = store.create_profile("Emir", "GitEmir")
    store.sign_in(profile["id"])
    assert store.signed_in()["name"] == "Emir"
    assert store.load()["owner_profile"] == profile["id"]
    assert [p["project"]["name"] for p in store.projects_of(profile["id"])] == ["Draft"]


def test_signing_out_closes_a_saved_project_but_keeps_it():
    profile = store.create_profile("Emir", "GitEmir")
    store.sign_in(profile["id"])
    store.save(store.new_project("Saved", profile["id"]))
    store.sign_out()
    assert store.load() is None and store.signed_in() is None
    store.sign_in(profile["id"])
    assert [p["project"]["name"] for p in store.projects_of(profile["id"])] == ["Saved"]


def test_a_profile_keeps_several_projects_and_can_reopen_one():
    profile = store.create_profile("Emir", None)
    store.sign_in(profile["id"])
    first = store.new_project("First", profile["id"])
    store.save(first)
    store.close_project()
    store.save(store.new_project("Second", profile["id"]))
    assert {p["project"]["name"] for p in store.projects_of(profile["id"])} == {"First", "Second"}
    assert store.open_project(first["project"]["key"], profile["id"])["project"]["name"] == "First"
    assert store.load()["project"]["name"] == "First"


def test_another_profile_cannot_open_your_project():
    mine = store.create_profile("Emir", None)
    other = store.create_profile("Sara", None)
    project = store.new_project("Mine", mine["id"])
    store.save(project)
    assert store.open_project(project["project"]["key"], other["id"]) is None
    assert store.open_project("../../etc", mine["id"]) is None


def test_archive_moves_an_unsaved_project_away(data_dir):
    store.save(store.new_project("Draft"))
    target = store.archive()
    assert target.parent == data_dir / "archive" and store.load() is None


def test_reset_all_archives_everything_and_starts_fresh(data_dir):
    profile = store.create_profile("Emir", "GitEmir")
    store.sign_in(profile["id"])
    store.save(store.new_project("Saved", profile["id"]))
    target = store.reset_all()
    assert target.parent == data_dir / "archive"
    assert sorted(p.name for p in target.iterdir()) == ["profiles.json", "projects", "state.json"]
    assert store.load() is None and store.signed_in() is None and store.profiles() == []
    assert store.reset_all() is None  # nothing left to reset


def test_an_unreadable_project_file_is_moved_aside(data_dir):
    project = store.new_project("Broken")
    store.save(project)
    (data_dir / "projects" / f"{project['project']['key']}.json").write_text("{not json", encoding="utf-8")
    assert store.load() is None
    assert any((data_dir / "archive").iterdir())


def test_a_shared_board_is_found_by_its_token_only():
    project = store.new_project("Shared")
    project["share_token"] = "abcdefghijklmnop1234"
    store.save(project)
    store.close_project()
    assert store.find_shared("abcdefghijklmnop1234")["project"]["name"] == "Shared"
    assert store.load() is None  # looking at the shared board doesn't open the project
    assert store.find_shared("abcdefghijklmnop0000") is None
    assert store.find_shared("../../etc") is None
    assert store.find_shared("") is None


def test_deleting_a_project_moves_it_to_the_archive(data_dir):
    owner = store.create_profile("Emir", "GitEmir")
    other = store.create_profile("Sara", "sara-dev")
    draft = store.new_project("Draft", owner["id"])
    store.save(draft)
    key = draft["project"]["key"]
    assert store.delete_project(key, other["id"]) is None  # not theirs
    moved = store.delete_project(key, owner["id"])
    assert moved is not None and moved.exists()
    assert not (data_dir / "projects" / f"{key}.json").exists()
    assert store.load() is None  # it was the open project
    assert store.projects_of(owner["id"]) == []
    assert store.delete_project("nothere1", owner["id"]) is None
