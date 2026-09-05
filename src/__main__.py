"""Fetch the team's fixtures, turn them into events, and sync them to iCloud.

Run with --dry-run to do everything except write to the calendar.
"""

import json
import sys
from pathlib import Path

from .caldav_client import connect, get_calendar
from .fetch import fetch_fixtures
from .models import get_teams
from .sync import CALENDAR_NAME, FIXTURES_PATH, sync_calendar
from .translate import write_calendar

TEAM_NAME = "FC Barcelona"
TEAMS_PATH = "european_teams.json"
SCHEDULE_PATH = "teams_schedule.json"


def save_json(path: str, data: dict) -> None:
    with open(path, "w") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def load_json(path: str) -> dict:
    with open(path) as file:
        return json.load(file)


def find_team_id(teams: dict, team_name: str):
    """Look the team up across every league rather than assuming one of them."""
    for league_teams in teams.values():
        if team_name in league_teams:
            return league_teams[team_name]

    raise RuntimeError(
        f"{team_name!r} is not in {TEAMS_PATH}. Only the top 5 European leagues "
        f"are listed there; delete the file to rebuild it."
    )


def load_or_fetch_teams() -> dict:
    """The team list changes once a season, so it is fetched once and cached."""
    if not Path(TEAMS_PATH).is_file():
        save_json(TEAMS_PATH, get_teams())

    return load_json(TEAMS_PATH)


def load_or_fetch_schedule(team_id) -> dict:
    """Seed the whole season on a first run, then refresh the near window.

    Kickoff times are announced a few weeks ahead, so a weekly run re-fetches
    the next fortnight and merges it over the cache. Matches outside that window
    are kept as they were: absent from a refresh means "not in the window", not
    "cancelled".
    """
    if not Path(SCHEDULE_PATH).is_file():
        schedule = normalise_keys(fetch_fixtures(team_id=team_id, initial_run=True))
        save_json(SCHEDULE_PATH, schedule)
        return schedule

    schedule = load_json(SCHEDULE_PATH)
    refreshed = normalise_keys(fetch_fixtures(team_id=team_id, initial_run=False))
    schedule.update(refreshed)
    save_json(SCHEDULE_PATH, schedule)
    return schedule


def normalise_keys(schedule: dict) -> dict:
    """Match ids as strings, the way they survive a json round trip.

    fetch returns int keys and the cache reloads them as strings, so merging the
    two without this would file the same match under both 564650 and "564650".
    """
    return {str(match_id): info for match_id, info in schedule.items()}


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    teams = load_or_fetch_teams()
    team_id = find_team_id(teams, TEAM_NAME)

    schedule = load_or_fetch_schedule(team_id)
    print(f"{len(schedule)} fixtures for {TEAM_NAME}")

    write_calendar(schedule, team_name=TEAM_NAME)
    print(f"wrote {FIXTURES_PATH}")

    calendar = get_calendar(connect(), CALENDAR_NAME)
    counts = sync_calendar(calendar, dry_run=dry_run)

    action = "would create/update" if dry_run else "created/updated"
    print(f"{action} {counts['created']}/{counts['updated']} in {CALENDAR_NAME!r}")


if __name__ == "__main__":
    main()
