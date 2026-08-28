from .fetch import fetch_fixtures
from .models import get_teams
import json
from pathlib import Path

def main():
    if not Path("european_teams.json").is_file():
        with open("european_teams.json", "w") as file:
            json.dump(get_teams(), file, indent=2, ensure_ascii=False)

    if not Path("teams_schedule.json").is_file():
            with open("teams_schedule.json", "w") as file:
                json.dump(fetch_fixtures(team = "81"), file, indent=2, ensure_ascii=False)


if __name__ == "__main__": 
    main()