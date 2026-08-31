from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ics import Calendar, Event

MATCH_DURATION = timedelta(hours=2)

# Keeps uids from colliding with events from any other source in the calendar.
UID_DOMAIN = "soccer-match-calendar-importer"

# football-data.org sends a midnight-UTC kickoff when the broadcast slot has not
# been announced yet, which is most of the season this far out. Left alone those
# land in the calendar at 2am, so they are parked at a readable placeholder.
# No real fixture kicks off at 00:00 UTC (1am in England, 2am in Spain), so the
# sentinel is safe to test for.
UNANNOUNCED_KICKOFF = time(0, 0)
DEFAULT_KICKOFF = time(15, 0)
# The zone, not a fixed -5 offset: a fixed offset would read as 4pm through the
# EDT half of the season. This keeps it at 3pm on the wall clock all year.
DEFAULT_KICKOFF_ZONE = ZoneInfo("America/New_York")

# Make given datetime format compatible
def parse_match_date(value: str) -> datetime:

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# Park a not-yet-scheduled match at the default kickoff, keeping its date
def apply_default_kickoff(kickoff: datetime) -> datetime:

    in_utc = kickoff.astimezone(timezone.utc)
    if in_utc.time() != UNANNOUNCED_KICKOFF:
        return kickoff

    match_day = in_utc.date()
    local = datetime.combine(match_day, DEFAULT_KICKOFF, tzinfo=DEFAULT_KICKOFF_ZONE)
    return local.astimezone(timezone.utc)


def to_event(match_id, info: dict, team_name:str) -> Event:

    opponent = info["opponent_name"]
    competition = info["competition_name"]
    matchday = info.get("matchday")
    kickoff = apply_default_kickoff(parse_match_date(info["match_date"]))

    event = Event()

    event.name = f"{team_name} at {opponent}" if info["venue_status"] == "away" else f"{opponent} at {team_name}"

    # Cup ties are not numbered, so the api leaves matchday null.
    # TODO: Change to knockout round + leg for cup ties
    event.description = (
        competition if matchday is None else f"{competition} matchday {matchday}"
    )
    event.begin = kickoff
    event.end = kickoff + MATCH_DURATION
    event.uid = f"{match_id}@{UID_DOMAIN}"
    # RFC 5545 requires DTSTAMP on every VEVENT; ics.py only emits it if
    # `.created` is set, and some servers reject a document without it.
    event.created = datetime.now(timezone.utc)
    return event


def to_ics(match_id, info: dict, team_name: str) -> str:
    """One match as a standalone iCalendar document.

    CalDAV stores each event as its own resource, so `sync.py` needs a complete
    VCALENDAR per match rather than one calendar holding all of them.
    """
    calendar = Calendar()
    calendar.events.add(to_event(match_id, info, team_name=team_name))
    return calendar.serialize()


def transform_to_calendar(fixtures_dict: dict, team_name:str) -> Calendar:

    calendar = Calendar()

    # .values() yields values alone; the match id lives in the key, and it is
    # what the uid is built from.
    for fixture_id, fixture_info in fixtures_dict.items():
        # Calendar.events is a set, not a list.
        calendar.events.add(to_event(match_id=fixture_id, info=fixture_info, team_name = team_name))

    return calendar


def write_calendar(fixtures_dict: dict, team_name: str, *, path: str = "fixtures.ics") -> None:
    calendar = transform_to_calendar(fixtures_dict, team_name=team_name)
    # newline="" stops python rewriting the line endings ics.py already emits:
    # in text mode a "\r\n" becomes "\r\r\n" on platforms where linesep is CRLF.
    with open(path, "w", newline="", encoding="utf-8") as file:
        file.write(calendar.serialize())
