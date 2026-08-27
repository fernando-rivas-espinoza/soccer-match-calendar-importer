import os
from dotenv import load_dotenv
import http.client
from datetime import date, timedelta

def fetch_schedule(team: str, c: list[str]):
    today = date.today()
    year = today.year
    month = today.month

    # The api sets the 'season' value to be the year a season starts
    season = year if month > 7 else year - 1

    load_dotenv()
    api_key = os.getenv("API_FOOTBALL_KEY")
    client = http.client.HTTPSConnection("v3.football.api-sports.io")
    
    headers = {
        'x-apisports-key': api_key
        }
    
    data = []
 
    request = f"/fixtures?team={team}&season={season}&competition=all&from={today}&to={today + timedelta(weeks=2)}"
    client.request("GET",request, headers=headers)
    res = client.getresponse()
    data.append(res.read().decode("utf-8"))

    return data

