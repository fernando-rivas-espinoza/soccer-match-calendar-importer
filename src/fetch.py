from .api_request import make_request
from datetime import datetime, timedelta, timezone

def extract_schedule(Response, team_id):
    pruned = {}
    for match in Response["matches"]:
        matchdate = match["utcDate"]
        pruned["matchday"] = matchdate
        curr_match = pruned[matchdate]
        curr_match["matchday"] = match["season"]["currentMatchday"]

        if match["homeTeam"]["id"] != team_id:
            curr_match["venue_status"] = "away"
            curr_match["opponent_name"] = match["homeTeam"]["name"]
            curr_match["opponent_id"] = match["homeTeam"]["id"]
        else:
            curr_match["venue_status"] = "home"
            curr_match["opponent_name"] = match["awayTeam"]["name"]
            curr_match["opponent_id"] = match["awayTeam"]["id"]

        curr_match["competition_name"] = match["competition"]["name"]
        curr_match["competition_id"] = match["competition"]["id"]

    return pruned

def fetch_fixtures(team_id: str, initial_run: bool):

    if initial_run:
        response = make_request(
            f"/teams/{team_id}/matches",
            {"status": "SCHEDULED"},
        )
        
    else:
        today = datetime.now(timezone.utc).date()
        window_end = today + timedelta(weeks=2)

        response = make_request(
            f"/teams/{team_id}/matches",
            {"status": "SCHEDULED", "dateFrom": today, "dateTo": window_end},
        )

    return extract_schedule(Response=response)
