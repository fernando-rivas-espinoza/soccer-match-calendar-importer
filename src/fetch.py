from .api_request import make_request
from datetime import datetime, timedelta, timezone

# Keep only necessary information from API output
def extract_schedule(response, team_id) -> dict:
    pruned = {}
    for match in response["matches"]:
        matchdate = match["utcDate"]
        curr_match = pruned.setdefault(matchdate, {})
        curr_match["matchday"] = match["matchday"]

        # The api reports ids as ints; team_id arrives as a string from the caller.
        if int(match["homeTeam"]["id"]) != int(team_id):
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

def fetch_fixtures(team_id: str, initial_run: bool) -> dict:

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

    return extract_schedule(response=response, team_id=team_id)
