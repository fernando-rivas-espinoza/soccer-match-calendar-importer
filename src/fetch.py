import os
from dotenv import load_dotenv
import http.client
from datetime import datetime, timedelta, timezone
import json

API_HOST = "api.football-data.org"


def _error_message(body: str) -> str:
    """football-data.org reports failures as {"message": ..., "errorCode": ...}."""
    try:
        return json.loads(body).get("message", body[:200])
    except ValueError:
        return body[:200]


def fetch_fixtures(team: str):
    today = datetime.now(timezone.utc).date()
    window_end = today + timedelta(weeks=2)

    load_dotenv()
    api_key = os.getenv("FOOTBALL_DATA_KEY")
    if not api_key:
        raise RuntimeError(
            "FOOTBALL_DATA_KEY is not set; add your football-data.org token to .env"
        )

    headers = {
        'X-Auth-Token': api_key
        }

    # The team id is a path segment on this api, and the date window filters
    # across every competition the team is in, so no season filter is needed.
    request = (
        f"/v4/teams/{team}/matches"
        f"?status=SCHEDULED&dateFrom={today}&dateTo={window_end}"
    )

    client = http.client.HTTPSConnection(API_HOST)
    try:
        client.request("GET", request, headers=headers)
        res = client.getresponse()
        body = res.read().decode("utf-8")
        status, reason = res.status, res.reason
    finally:
        client.close()

    if status != 200:
        raise RuntimeError(
            f"football-data.org returned {status} {reason}: {_error_message(body)}"
        )

    try:
        return json.loads(body)
    except ValueError as e:
        raise RuntimeError(f"football-data.org returned malformed JSON: {e}") from e
