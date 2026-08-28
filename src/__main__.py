from .fetch import fetch_fixtures
from .models import get_teams

def main():
    print(get_teams)

    raw_schedule = fetch_fixtures(team = "86")

if __name__ == "__main__": 
    main()