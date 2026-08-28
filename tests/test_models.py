"""Tests for src/models.py.

`make_request` is replaced throughout, so nothing here touches the network.
"""

from datetime import datetime

import pytest

from src import models
from src.models import LEAGUE_CODES, get_teams, parse_teams_response


SAMPLE_TEAMS = {
    "count": 2,
    "filters": {"season": 2026},
    "competition": {"id": 2014, "name": "Primera Division", "code": "PD"},
    "teams": [
        {"id": 81, "name": "FC Barcelona", "shortName": "Barca", "tla": "FCB"},
        {"id": 86, "name": "Real Madrid CF", "shortName": "Real Madrid", "tla": "RMA"},
    ],
}


@pytest.fixture
def recorded_requests(monkeypatch):
    """Capture every make_request call models.py makes."""
    calls = []

    def fake_make_request(resource, params=None):
        calls.append((resource, params))
        return SAMPLE_TEAMS

    monkeypatch.setattr(models, "make_request", fake_make_request)
    return calls


@pytest.fixture
def frozen_now(monkeypatch):
    def freeze(year, month, day):
        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(year, month, day, 12, 0, tzinfo=tz)

        monkeypatch.setattr(models, "datetime", FrozenDateTime)

    return freeze


class TestParseTeamsResponse:
    def test_maps_every_team_name_to_its_id(self):
        assert parse_teams_response(SAMPLE_TEAMS) == {
            "FC Barcelona": 81,
            "Real Madrid CF": 86,
        }

    def test_empty_team_list_yields_an_empty_map(self):
        assert parse_teams_response({"teams": []}) == {}

    def test_missing_teams_key_raises_a_legible_error(self):
        """An error payload must not look like a league with no teams."""
        with pytest.raises(ValueError) as excinfo:
            parse_teams_response({"message": "Not found", "errorCode": 404})
        assert "teams" in str(excinfo.value)
        assert "errorCode" in str(excinfo.value)

    def test_missing_teams_key_is_not_silently_empty(self):
        with pytest.raises(ValueError):
            parse_teams_response({})


class TestGetTeams:
    def test_requests_one_resource_per_league(self, recorded_requests, frozen_now):
        frozen_now(2026, 8, 27)
        get_teams()
        resources = [resource for resource, _ in recorded_requests]
        assert resources == [
            f"/competitions/{code}/teams" for code in LEAGUE_CODES.values()
        ]

    def test_passes_season_as_a_param_not_a_query_string(
        self, recorded_requests, frozen_now
    ):
        frozen_now(2026, 8, 27)
        get_teams()
        for _, params in recorded_requests:
            assert params == {"season": 2026}

    def test_after_july_uses_the_current_year(self, recorded_requests, frozen_now):
        frozen_now(2026, 8, 1)
        get_teams()
        assert recorded_requests[0][1] == {"season": 2026}

    def test_before_august_uses_the_previous_year(self, recorded_requests, frozen_now):
        frozen_now(2026, 7, 31)
        get_teams()
        assert recorded_requests[0][1] == {"season": 2025}

    def test_keys_results_by_league_name(self, recorded_requests, frozen_now):
        frozen_now(2026, 8, 27)
        result = get_teams()
        assert set(result) == set(LEAGUE_CODES)
        assert result["la_liga"]["FC Barcelona"] == 81
