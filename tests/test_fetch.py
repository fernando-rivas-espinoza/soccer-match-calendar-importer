"""Tests for src/fetch.py against the football-data.org v4 api."""

from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from src.fetch import extract_schedule, fetch_fixtures
from tests.conftest import SAMPLE_MATCHES, FakeResponse


def query_of(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


# Both run modes hit the same resource with the same auth; only the date
# window differs, so the shared expectations are checked against each.
BOTH_MODES = pytest.mark.parametrize("initial_run", [True, False], ids=["initial", "refresh"])


class TestRequest:
    @BOTH_MODES
    def test_connects_to_the_bare_host_without_a_path(
        self, http, api_key, frozen_date, initial_run
    ):
        """HTTPSConnection takes a host only; a '/v4' suffix breaks DNS."""
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=initial_run)
        assert http.connection.host == "api.football-data.org"
        assert "/" not in http.connection.host

    @BOTH_MODES
    def test_sends_a_get_to_the_versioned_team_matches_path(
        self, http, api_key, frozen_date, initial_run
    ):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=initial_run)
        method, url, _ = http.connection.last_request
        assert method == "GET"
        assert urlparse(url).path == "/v4/teams/81/matches"

    @BOTH_MODES
    def test_team_id_is_a_path_segment_not_a_query_param(
        self, http, api_key, frozen_date, initial_run
    ):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=initial_run)
        url = http.connection.last_request[1]
        assert "/teams/81/" in urlparse(url).path
        assert "team" not in query_of(url)

    @BOTH_MODES
    def test_asks_only_for_scheduled_matches(
        self, http, api_key, frozen_date, initial_run
    ):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=initial_run)
        assert query_of(http.connection.last_request[1])["status"] == "SCHEDULED"

    @BOTH_MODES
    def test_does_not_send_a_season_filter(
        self, http, api_key, frozen_date, initial_run
    ):
        """The date window already spans every competition; season is api-football's model."""
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=initial_run)
        assert "season" not in query_of(http.connection.last_request[1])

    @BOTH_MODES
    def test_does_not_filter_by_competition(
        self, http, api_key, frozen_date, initial_run
    ):
        """README: pull "every competition a team is in"."""
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=initial_run)
        assert "competitions" not in query_of(http.connection.last_request[1])

    @BOTH_MODES
    def test_authenticates_with_the_football_data_token_header(
        self, http, api_key, frozen_date, initial_run
    ):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=initial_run)
        headers = http.connection.last_request[2]
        assert headers["X-Auth-Token"] == api_key
        assert "x-apisports-key" not in headers


class TestDateWindow:
    def test_refresh_runs_from_today_to_two_weeks_out(self, http, api_key, frozen_date):
        today = frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=False)
        params = query_of(http.connection.last_request[1])
        assert params["dateFrom"] == "2026-08-27"
        assert params["dateTo"] == "2026-09-10"
        assert date.fromisoformat(params["dateTo"]) - today == timedelta(weeks=2)

    def test_refresh_window_is_built_from_utc_not_local_time(self, http, api_key):
        """The api works in UTC, so the window edges must be UTC dates."""
        fetch_fixtures("81", initial_run=False)
        assert query_of(http.connection.last_request[1])["dateFrom"] == (
            datetime.now(timezone.utc).date().isoformat()
        )

    def test_initial_run_asks_for_the_whole_season(self, http, api_key, frozen_date):
        """A first run seeds the calendar, so it must not be capped at two weeks."""
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=True)
        params = query_of(http.connection.last_request[1])
        assert "dateFrom" not in params
        assert "dateTo" not in params


class TestResponse:
    def test_returns_the_pruned_schedule_not_the_raw_payload(
        self, http, api_key, frozen_date
    ):
        frozen_date(2026, 8, 27)
        schedule = fetch_fixtures("81", initial_run=True)
        assert list(schedule) == [497855]
        assert "matches" not in schedule

    def test_closes_the_connection_on_success(self, http, api_key, frozen_date):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81", initial_run=True)
        assert http.connection.closed

    @pytest.mark.parametrize(
        "status, reason, message",
        [
            (403, "Forbidden", "The resource you are looking for is restricted"),
            (404, "Not Found", "Team not found"),
            (429, "Too Many Requests", "You reached your request limit"),
        ],
    )
    def test_raises_on_http_error_and_surfaces_the_api_message(
        self, http, api_key, frozen_date, status, reason, message
    ):
        frozen_date(2026, 8, 27)
        http.response = FakeResponse(
            {"message": message, "errorCode": status}, status=status, reason=reason
        )
        with pytest.raises(RuntimeError) as excinfo:
            fetch_fixtures("81", initial_run=True)
        assert str(status) in str(excinfo.value)
        assert message in str(excinfo.value)

    def test_closes_the_connection_on_http_error(self, http, api_key, frozen_date):
        frozen_date(2026, 8, 27)
        http.response = FakeResponse({"message": "nope"}, status=403, reason="Forbidden")
        with pytest.raises(RuntimeError):
            fetch_fixtures("81", initial_run=True)
        assert http.connection.closed

    def test_malformed_json_raises_rather_than_exiting(self, http, api_key, frozen_date):
        frozen_date(2026, 8, 27)
        http.response = FakeResponse("<html>502 Bad Gateway</html>")
        with pytest.raises(RuntimeError) as excinfo:
            fetch_fixtures("81", initial_run=True)
        assert "malformed" in str(excinfo.value).lower()

    def test_non_json_error_body_still_reports_the_status(
        self, http, api_key, frozen_date
    ):
        """Gateway errors from a proxy are HTML, not the api's json envelope."""
        frozen_date(2026, 8, 27)
        http.response = FakeResponse(
            "<html>502 Bad Gateway</html>", status=502, reason="Bad Gateway"
        )
        with pytest.raises(RuntimeError) as excinfo:
            fetch_fixtures("81", initial_run=True)
        assert "502" in str(excinfo.value)


class TestExtractSchedule:
    def test_keys_are_the_api_match_ids(self):
        """The key becomes the calendar UID, so it must survive a reschedule."""
        assert list(extract_schedule(SAMPLE_MATCHES, "81")) == [497855]

    def test_a_rescheduled_match_keeps_its_key(self):
        """A moved kickoff must read as an update, not a second event."""
        moved = {
            "matches": [
                dict(SAMPLE_MATCHES["matches"][0], utcDate="2026-08-30T15:00:00Z")
            ]
        }
        before = extract_schedule(SAMPLE_MATCHES, "81")
        after = extract_schedule(moved, "81")
        assert list(before) == list(after) == [497855]
        assert before[497855]["match_date"] != after[497855]["match_date"]

    def test_carries_the_kickoff_time(self):
        assert extract_schedule(SAMPLE_MATCHES, "81")[497855]["match_date"] == (
            "2026-08-29T19:00:00Z"
        )

    def test_an_empty_match_list_yields_an_empty_schedule(self):
        assert extract_schedule({"matches": []}, "81") == {}

    def test_home_match_names_the_away_side_as_opponent(self):
        match = extract_schedule(SAMPLE_MATCHES, "81")[497855]
        assert match["venue_status"] == "home"
        assert match["opponent_name"] == "Real Madrid CF"
        assert match["opponent_id"] == 86

    def test_away_match_names_the_home_side_as_opponent(self):
        match = extract_schedule(SAMPLE_MATCHES, "86")[497855]
        assert match["venue_status"] == "away"
        assert match["opponent_name"] == "FC Barcelona"
        assert match["opponent_id"] == 81

    def test_team_id_may_be_an_int_or_a_string(self):
        """The api reports ids as ints; callers pass them around as strings."""
        for team_id in (81, "81"):
            match = extract_schedule(SAMPLE_MATCHES, team_id)[497855]
            assert match["venue_status"] == "home"

    def test_primera_division_is_renamed_to_la_liga(self):
        match = extract_schedule(SAMPLE_MATCHES, "81")[497855]
        assert match["competition_name"] == "La Liga"

    def test_other_competition_names_are_left_alone(self):
        payload = {
            "matches": [
                dict(
                    SAMPLE_MATCHES["matches"][0],
                    competition={
                        "id": 2001,
                        "name": "UEFA Champions League",
                        "code": "CL",
                    },
                )
            ]
        }
        match = extract_schedule(payload, "81")[497855]
        assert match["competition_name"] == "UEFA Champions League"
        assert match["competition_id"] == 2001

    def test_carries_the_matchday(self):
        assert extract_schedule(SAMPLE_MATCHES, "81")[497855]["matchday"] == 3


class TestConfiguration:
    def test_missing_token_fails_with_a_clear_message(self, http, frozen_date):
        frozen_date(2026, 8, 27)
        with pytest.raises(RuntimeError) as excinfo:
            fetch_fixtures("81", initial_run=True)
        assert "FOOTBALL_DATA_KEY" in str(excinfo.value)

    def test_missing_token_does_not_open_a_connection(self, http, frozen_date):
        """Fail before dialling out, not with an opaque header TypeError."""
        frozen_date(2026, 8, 27)
        with pytest.raises(RuntimeError):
            fetch_fixtures("81", initial_run=True)
        assert http.created == []

    def test_empty_token_is_treated_as_missing(self, http, frozen_date, monkeypatch):
        monkeypatch.setenv("FOOTBALL_DATA_KEY", "")
        frozen_date(2026, 8, 27)
        with pytest.raises(RuntimeError) as excinfo:
            fetch_fixtures("81", initial_run=True)
        assert "FOOTBALL_DATA_KEY" in str(excinfo.value)

    def test_does_not_read_the_real_dotenv_file(self, http, frozen_date):
        """Regression guard for the test suite itself, not for fetch.py."""
        import os

        frozen_date(2026, 8, 27)
        assert os.getenv("FOOTBALL_DATA_KEY") is None
