from .api_request import make_request 
from datetime import datetime, timedelta, timezone

LEAGUE_IDS = {
    "la_liga": "PD",
    "premier_league": "PL",
    "ligue_1": "FL1", 
    "bundesliga": "BL1",
    "serie_a": "SA"
}

def parse_api_response(response):
    name_id_map = {}

    for team in response["teams"]:
        name_id_map[team["name"]] = team["id"]

    return name_id_map


def get_teams():
    date = datetime.now(timezone.utc).date()

    # A season is active from august of the starting year to july of the ending year
    season = date.year if date.month > 7 else date.year - 1

    all_teams = {}

    for league_name, league_id in LEAGUE_IDS.items():
        resource = f"/competitions/{league_id}/teams"
        filters = f"?season={season}"
        raw_response = make_request(Resource=resource, Filters=filters)
        all_teams[league_name] = parse_api_response(raw_response)

    return all_teams





