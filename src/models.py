from .api_request import make_request 
from datetime import datetime, timezone

# Football-data.org codes for the top 5 european leagues 
LEAGUE_CODES = {
    "la_liga": "PD",
    "premier_league": "PL",
    "ligue_1": "FL1", 
    "bundesliga": "BL1",
    "serie_a": "SA"
}

# Extract team names and ids
def parse_teams_response(response):
    teams = response.get("teams")
    if teams is None:
        raise ValueError(
            "response has no 'teams' key; got keys "
            f"{sorted(response)}"
        )

    return {team["name"]: team["id"] for team in teams}


# Get the teams in each of the top 5 european leagues for this season
def get_teams():
    date = datetime.now(timezone.utc).date()

    # A season is active from august of the starting year to july of the ending year
    season = date.year if date.month > 7 else date.year - 1

    all_teams = {}

    for league_name, league_code in LEAGUE_CODES.items():
        raw_response = make_request(
            f"/competitions/{league_code}/teams", {"season": season}
        )
        all_teams[league_name] = parse_teams_response(raw_response)

    return all_teams





