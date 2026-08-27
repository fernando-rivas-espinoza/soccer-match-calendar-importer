import http.client

def api_football_client(Api_key):
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")

    headers = {
        'x-apisports-key': Api_key
        }

    return conn