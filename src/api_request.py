import os
from dotenv import load_dotenv
import http.client
import json
from typing import Optional
from urllib.parse import urlencode

API_HOST = "api.football-data.org"

def _error_message(body: str) -> str:
    """football-data.org reports failures as {"message": ..., "errorCode": ...}."""
    try:
        return json.loads(body).get("message", body[:200])
    except ValueError:
        return body[:200]

def make_request(resource: str, params: Optional[dict] = None):
    load_dotenv()
    api_key = os.getenv("FOOTBALL_DATA_KEY")
    if not api_key:
        raise RuntimeError(
            "FOOTBALL_DATA_KEY is not set; add your football-data.org token to .env"
        )

    headers = {
        'X-Auth-Token': api_key
        }

    # urlencode handles the "?" separator, escaping and str() conversion,
    # so callers pass plain values rather than pre-built query strings.
    query = f"?{urlencode(params)}" if params else ""
    request = f"/v4{resource}{query}"

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
