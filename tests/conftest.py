"""Shared fakes for the test suite.

Every test runs against an in-memory stand-in for `http.client.HTTPSConnection`,
so nothing here touches the network or spends football-data.org rate limit.
"""

import json

import pytest

from src import api_request, fetch


class FakeResponse:
    """Stands in for `http.client.HTTPResponse`."""

    def __init__(self, body="", status=200, reason="OK"):
        if not isinstance(body, (str, bytes)):
            body = json.dumps(body)
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status
        self.reason = reason

    def read(self):
        return self._body


class FakeConnection:
    """Records what was sent instead of opening a socket."""

    def __init__(self, host, response):
        self.host = host
        self.response = response
        self.requests = []
        self.closed = False

    def request(self, method, url, body=None, headers=None):
        self.requests.append((method, url, dict(headers or {})))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True

    @property
    def last_request(self):
        assert self.requests, "no request was sent"
        return self.requests[-1]


class FakeHTTP:
    """Handle the tests use to stage a response and inspect what was sent."""

    def __init__(self):
        self.response = FakeResponse(SAMPLE_MATCHES)
        self.created = []

    def __call__(self, host, *args, **kwargs):
        conn = FakeConnection(host, self.response)
        self.created.append(conn)
        return conn

    @property
    def connection(self):
        assert self.created, "no connection was opened"
        return self.created[-1]


# Trimmed shape of a real football-data.org /v4/teams/{id}/matches payload.
SAMPLE_MATCHES = {
    "filters": {
        "competitions": "PD",
        "dateFrom": "2026-08-27",
        "dateTo": "2026-09-10",
        "status": ["SCHEDULED"],
    },
    "resultSet": {"count": 1, "first": "2026-08-29", "last": "2026-08-29"},
    "matches": [
        {
            "id": 497855,
            "utcDate": "2026-08-29T19:00:00Z",
            "status": "SCHEDULED",
            "matchday": 3,
            "competition": {"id": 2014, "name": "Primera Division", "code": "PD"},
            "homeTeam": {"id": 81, "name": "FC Barcelona", "shortName": "Barca"},
            "awayTeam": {"id": 86, "name": "Real Madrid CF", "shortName": "Real Madrid"},
        }
    ],
}


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Keep the developer's real .env (and its live token) out of the tests.

    `fetch_fixtures` calls `load_dotenv()` itself, which would otherwise read
    the real .env from the working directory. Tests set the token explicitly.
    """
    monkeypatch.setattr(api_request, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("FOOTBALL_DATA_KEY", raising=False)


@pytest.fixture
def http(monkeypatch):
    fake = FakeHTTP()
    monkeypatch.setattr(api_request.http.client, "HTTPSConnection", fake)
    return fake


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_KEY", "test-token-abc123")
    return "test-token-abc123"


@pytest.fixture
def frozen_date(monkeypatch):
    """Pin the clock inside src.fetch to a chosen date."""
    from datetime import date, datetime

    def freeze(year, month, day):
        pinned = date(year, month, day)

        class FrozenDate(date):
            @classmethod
            def today(cls):
                return pinned

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(year, month, day, 12, 0, tzinfo=tz)

        # Patch both names so the fixture keeps working whether fetch.py reads
        # the clock via date.today() or datetime.now(timezone.utc).
        monkeypatch.setattr(fetch, "date", FrozenDate, raising=False)
        monkeypatch.setattr(fetch, "datetime", FrozenDateTime, raising=False)
        return pinned

    return freeze
