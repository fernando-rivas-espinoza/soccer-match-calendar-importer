import os
from dotenv import load_dotenv
import http.client
from datetime import date, timedelta

def fetch_schedule(team: str, c: list[str]):
    today = date.today()

    # The api sets the 'season' value to be the year a season starts
    season = today.year if today.month > 7 else today.year - timedelta(days=-365)

    load_dotenv()
    api_key = os.getenv("API_FOOTBALL_KEY")
    client = http.client.HTTPSConnection("v3.football.api-sports.io")
    
    headers = {
        'x-apisports-key': api_key
        }
    
    request = f"/fixtures?team={team}&season={season}&competition=all&from={today}&to={today + timedelta(weeks=2)}"
    client.request("GET",request, headers=headers)
    res = client.getresponse()

    return res.read().decode("utf-8")

