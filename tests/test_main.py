"""Tests for the pipeline wiring in src/__main__.py.

The network is never touched: `fetch_fixtures` and `get_teams` are replaced.
"""

import json

import pytest

from src import __main__ as main_module
from src.__main__ import (
    find_team_id,
    load_or_fetch_schedule,
    load_or_fetch_teams,
    normalise_keys,
)


TEAMS = {
    "la_liga": {"FC Barcelona": 81, "Real Madrid CF": 86},
    "premier_league": {"Arsenal FC": 57},
}

FIXTURE = {
    "match_date": "2026-08-29T00:00:00Z",
    "matchday": 3,
    "venue_status": "home",
    "opponent_name": "Real Madrid CF",
    "opponent_id": 86,
    "competition_name": "La Liga",
    "competition_id": 2014,
}


@pytest.fixture
def in_tmp_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestFindTeamId:
    def test_finds_a_team_in_the_first_league(self):
        assert find_team_id(TEAMS, "FC Barcelona") == 81

    def test_finds_a_team_in_any_other_league(self):
        """The lookup must not assume the team plays in La Liga."""
        assert find_team_id(TEAMS, "Arsenal FC") == 57

    def test_an_unknown_team_fails_with_a_legible_error(self):
        with pytest.raises(RuntimeError) as excinfo:
            find_team_id(TEAMS, "Wrexham AFC")
        assert "Wrexham AFC" in str(excinfo.value)


class TestNormaliseKeys:
    def test_int_match_ids_become_strings(self):
        """json turns dict keys into strings; the cache comes back that way."""
        assert list(normalise_keys({564650: FIXTURE})) == ["564650"]

    def test_string_keys_are_left_alone(self):
        assert list(normalise_keys({"564650": FIXTURE})) == ["564650"]


class TestLoadOrFetchSchedule:
    def test_first_run_fetches_the_whole_season(self, in_tmp_dir, monkeypatch):
        calls = []

        def fake_fetch(team_id, initial_run):
            calls.append(initial_run)
            return {564650: FIXTURE}

        monkeypatch.setattr(main_module, "fetch_fixtures", fake_fetch)
        schedule = load_or_fetch_schedule(81)
        assert calls == [True]
        assert schedule == {"564650": FIXTURE}

    def test_first_run_writes_the_cache(self, in_tmp_dir, monkeypatch):
        monkeypatch.setattr(
            main_module, "fetch_fixtures", lambda team_id, initial_run: {564650: FIXTURE}
        )
        load_or_fetch_schedule(81)
        assert json.loads((in_tmp_dir / "teams_schedule.json").read_text()) == {
            "564650": FIXTURE
        }

    def test_later_runs_refresh_the_near_window(self, in_tmp_dir, monkeypatch):
        (in_tmp_dir / "teams_schedule.json").write_text(json.dumps({"564650": FIXTURE}))
        calls = []

        def fake_fetch(team_id, initial_run):
            calls.append(initial_run)
            return {}

        monkeypatch.setattr(main_module, "fetch_fixtures", fake_fetch)
        load_or_fetch_schedule(81)
        assert calls == [False]

    def test_a_refresh_updates_a_match_in_place(self, in_tmp_dir, monkeypatch):
        """An announced kickoff must replace the placeholder, not add a fixture."""
        (in_tmp_dir / "teams_schedule.json").write_text(json.dumps({"564650": FIXTURE}))
        announced = dict(FIXTURE, match_date="2026-08-29T19:00:00Z")
        monkeypatch.setattr(
            main_module,
            "fetch_fixtures",
            lambda team_id, initial_run: {564650: announced},
        )
        schedule = load_or_fetch_schedule(81)
        assert len(schedule) == 1
        assert schedule["564650"]["match_date"] == "2026-08-29T19:00:00Z"

    def test_a_refresh_keeps_matches_outside_the_window(self, in_tmp_dir, monkeypatch):
        """Absent from a two-week refresh means out of range, not cancelled."""
        cached = {"564650": FIXTURE, "999999": dict(FIXTURE, matchday=30)}
        (in_tmp_dir / "teams_schedule.json").write_text(json.dumps(cached))
        monkeypatch.setattr(
            main_module, "fetch_fixtures", lambda team_id, initial_run: {564650: FIXTURE}
        )
        assert set(load_or_fetch_schedule(81)) == {"564650", "999999"}

    def test_a_refresh_adds_a_newly_scheduled_match(self, in_tmp_dir, monkeypatch):
        (in_tmp_dir / "teams_schedule.json").write_text(json.dumps({"564650": FIXTURE}))
        monkeypatch.setattr(
            main_module, "fetch_fixtures", lambda team_id, initial_run: {777777: FIXTURE}
        )
        assert set(load_or_fetch_schedule(81)) == {"564650", "777777"}

    def test_a_refresh_does_not_duplicate_a_match_under_both_key_types(
        self, in_tmp_dir, monkeypatch
    ):
        """fetch returns int ids, the cache holds strings; merging must not split."""
        (in_tmp_dir / "teams_schedule.json").write_text(json.dumps({"564650": FIXTURE}))
        monkeypatch.setattr(
            main_module, "fetch_fixtures", lambda team_id, initial_run: {564650: FIXTURE}
        )
        assert list(load_or_fetch_schedule(81)) == ["564650"]


class TestLoadOrFetchTeams:
    def test_fetches_once_then_reads_the_cache(self, in_tmp_dir, monkeypatch):
        calls = []
        monkeypatch.setattr(
            main_module, "get_teams", lambda: calls.append(1) or TEAMS
        )
        assert load_or_fetch_teams() == TEAMS
        assert load_or_fetch_teams() == TEAMS
        assert len(calls) == 1, "the cached file must not be refetched"
