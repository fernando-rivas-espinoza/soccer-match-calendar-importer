import os
from dotenv import load_dotenv
import http.client
from datetime import date, timedelta, timezone
import json

def fetch_schedule(team: str):
    today = date.today(timezone.utc).date()

    # The api sets the 'season' value to be the year a season starts
    # A european season ends after July when including int'l competitions
    season = today.year if today.month > 7 else today.year - 1

    load_dotenv()
    api_key = os.getenv("API_FOOTBALL_KEY")
    client = http.client.HTTPSConnection("v3.football.api-sports.io")
    
    headers = {
        'x-apisports-key': api_key
        }
    
    request = f"/fixtures?team={team}&season={season}&from={today}&to={today + timedelta(weeks=2)}"
    client.request("GET",request, headers=headers)
    res = client.getresponse()
    body = res.read().decode("utf-8")

    if res.status != 200:
        raise RuntimeError(f"api-football returned {res.status} {res.reason}")

    try:
        payload = json.loads(body)
    except Exception as e:
        print(f"Error: Malformed JSON \n{e}")
        exit(1)
    finally:
        client.close()

    return payload

