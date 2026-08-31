from .fetch import fetch_fixtures
from .models import get_teams
from .translate import write_calendar
import json
from pathlib import Path

def main():

    team = "FC Barcelona"
   
    if not Path("european_teams.json").is_file():
        with open("european_teams.json", "w") as file:
            json.dump(get_teams(), file, indent=2, ensure_ascii=False)
            

    with open("european_teams.json", "r") as file:
        teams_dict = json.load(file)

    team_id =  teams_dict["la_liga"]["FC Barcelona"]

    if not Path("teams_schedule.json").is_file():
            with open("teams_schedule.json", "w") as file:
                json.dump(fetch_fixtures(team_id = team_id, initial_run=True), file, indent=2, ensure_ascii=False)

    with open('teams_schedule.json', 'r') as file:
        fixtures_dict = json.load(file)

    write_calendar(fixtures_dict, team_name=team)
    

if __name__ == "__main__": 
    main()