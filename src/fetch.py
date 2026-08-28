from .api_request import make_request
from datetime import datetime, timedelta, timezone

def fetch_fixtures(team: str):
    today = datetime.now(timezone.utc).date()
    window_end = today + timedelta(weeks=2)

    return make_request(
        f"/teams/{team}/matches",
        {"status": "SCHEDULED", "dateFrom": today, "dateTo": window_end},
    )
