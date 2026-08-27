from .fetch import fetch_fixtures

def main():
    raw_fixtures = fetch_fixtures(team="529")
    print(raw_fixtures)

if __name__ == "__main__": 
    main()