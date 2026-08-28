"""Tests for src/fetch.py against the football-data.org v4 api."""

from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from src.fetch import fetch_fixtures
from tests.conftest import FakeResponse


def query_of(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


class TestRequest:
    def test_connects_to_the_bare_host_without_a_path(self, http, api_key, frozen_date):
        """HTTPSConnection takes a host only; a '/v4' suffix breaks DNS."""
        frozen_date(2026, 8, 27)
        fetch_fixtures("81")
        assert http.connection.host == "api.football-data.org"
        assert "/" not in http.connection.host

    def test_sends_a_get_to_the_versioned_team_matches_path(
        self, http, api_key, frozen_date
    ):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81")
        method, url, _ = http.connection.last_request
        assert method == "GET"
        assert urlparse(url).path == "/v4/teams/81/matches"

    def test_team_id_is_a_path_segment_not_a_query_param(
        self, http, api_key, frozen_date
    ):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81")
        url = http.connection.last_request[1]
        assert "/teams/81/" in urlparse(url).path
        assert "team" not in query_of(url)

    def test_window_runs_from_today_to_two_weeks_out(self, http, api_key, frozen_date):
        today = frozen_date(2026, 8, 27)
        fetch_fixtures("81")
        params = query_of(http.connection.last_request[1])
        assert params["dateFrom"] == "2026-08-27"
        assert params["dateTo"] == "2026-09-10"
        assert date.fromisoformat(params["dateTo"]) - today == timedelta(weeks=2)

    def test_window_is_built_from_utc_not_local_time(self, http, api_key):
        """The api works in UTC, so the window edges must be UTC dates."""
        from datetime import datetime, timezone

        fetch_fixtures("81")
        assert query_of(http.connection.last_request[1])["dateFrom"] == (
            datetime.now(timezone.utc).date().isoformat()
        )

    def test_asks_only_for_scheduled_matches(self, http, api_key, frozen_date):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81")
        assert query_of(http.connection.last_request[1])["status"] == "SCHEDULED"

    def test_does_not_send_a_season_filter(self, http, api_key, frozen_date):
        """The date window already spans every competition; season is api-football's model."""
        frozen_date(2026, 8, 27)
        fetch_fixtures("81")
        assert "season" not in query_of(http.connection.last_request[1])

    def test_does_not_filter_by_competition(self, http, api_key, frozen_date):
        """README: pull "every competition a team is in"."""
        frozen_date(2026, 8, 27)
        fetch_fixtures("81")
        assert "competitions" not in query_of(http.connection.last_request[1])

    def test_authenticates_with_the_football_data_token_header(
        self, http, api_key, frozen_date
    ):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81")
        headers = http.connection.last_request[2]
        assert headers["X-Auth-Token"] == api_key
        assert "x-apisports-key" not in headers


class TestResponse:
    def test_returns_the_parsed_payload(self, http, api_key, frozen_date):
        frozen_date(2026, 8, 27)
        payload = fetch_fixtures("81")
        assert payload["matches"][0]["homeTeam"]["name"] == "FC Barcelona"
        assert payload["matches"][0]["utcDate"] == "2026-08-29T19:00:00Z"

    def test_closes_the_connection_on_success(self, http, api_key, frozen_date):
        frozen_date(2026, 8, 27)
        fetch_fixtures("81")
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
            fetch_fixtures("81")
        assert str(status) in str(excinfo.value)
        assert message in str(excinfo.value)

    def test_closes_the_connection_on_http_error(self, http, api_key, frozen_date):
        frozen_date(2026, 8, 27)
        http.response = FakeResponse({"message": "nope"}, status=403, reason="Forbidden")
        with pytest.raises(RuntimeError):
            fetch_fixtures("81")
        assert http.connection.closed

    def test_malformed_json_raises_rather_than_exiting(self, http, api_key, frozen_date):
        frozen_date(2026, 8, 27)
        http.response = FakeResponse("<html>502 Bad Gateway</html>")
        with pytest.raises(RuntimeError) as excinfo:
            fetch_fixtures("81")
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
            fetch_fixtures("81")
        assert "502" in str(excinfo.value)


class TestConfiguration:
    def test_missing_token_fails_with_a_clear_message(self, http, frozen_date):
        frozen_date(2026, 8, 27)
        with pytest.raises(RuntimeError) as excinfo:
            fetch_fixtures("81")
        assert "FOOTBALL_DATA_KEY" in str(excinfo.value)

    def test_missing_token_does_not_open_a_connection(self, http, frozen_date):
        """Fail before dialling out, not with an opaque header TypeError."""
        frozen_date(2026, 8, 27)
        with pytest.raises(RuntimeError):
            fetch_fixtures("81")
        assert http.created == []

    def test_empty_token_is_treated_as_missing(self, http, frozen_date, monkeypatch):
        monkeypatch.setenv("FOOTBALL_DATA_KEY", "")
        frozen_date(2026, 8, 27)
        with pytest.raises(RuntimeError) as excinfo:
            fetch_fixtures("81")
        assert "FOOTBALL_DATA_KEY" in str(excinfo.value)

    def test_does_not_read_the_real_dotenv_file(self, http, frozen_date):
        """Regression guard for the test suite itself, not for fetch.py."""
        import os

        frozen_date(2026, 8, 27)
        assert os.getenv("FOOTBALL_DATA_KEY") is None
