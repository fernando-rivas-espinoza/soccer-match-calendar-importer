"""Push the generated fixtures into a CalDAV calendar.

`translate.py` writes one file holding every match. CalDAV stores each event as
its own resource, so the file is split back into one document per match here and
each is written under a URL keyed by its uid. That is what lets a later run
update a rescheduled match in place instead of adding a second copy of it.
"""

from typing import Dict, Iterator, Tuple

from icalendar import Calendar as ICalendar

CALENDAR_NAME = "Soccer"
FIXTURES_PATH = "fixtures.ics"


def read_calendar_file(path: str = FIXTURES_PATH) -> str:
    """Read the fixtures file without letting python rewrite its line endings."""
    with open(path, "rb") as file:
        return file.read().decode("utf-8")


def split_calendar(ics_text: str) -> Iterator[Tuple[str, str]]:
    """Yield (uid, single-event iCalendar document) for every VEVENT.

    Rebuilt with `icalendar` rather than re-serialized through `ics`, because
    icalendar folds lines at 75 octets as RFC 5545 requires and ics.py 0.7 does
    not. A Champions League draw against a long German club name is enough to
    push a SUMMARY over the limit.
    """
    source = ICalendar.from_ical(ics_text)

    for vevent in source.walk("VEVENT"):
        document = ICalendar()
        document.add("prodid", source.get("prodid", "-//soccer-match-calendar-importer//EN"))
        document.add("version", source.get("version", "2.0"))
        document.add_component(vevent)
        yield str(vevent["UID"]), document.to_ical().decode("utf-8")


def existing_by_uid(calendar) -> Dict[str, object]:
    """Index the events already on the server by uid, in a single request.

    `Calendar.event_by_uid` would be the obvious call, but it issues a uid
    filtered REPORT that iCloud answers with 412 Precondition Failed. Listing
    the calendar once and indexing it here works there, works on servers that
    do support the query, and costs one request rather than one per fixture.
    """
    found = {}

    for event in calendar.events():
        component = event.icalendar_component
        if component is not None and component.get("UID"):
            found[str(component["UID"])] = event

    return found


def upsert_event(calendar, uid: str, document: str, existing: Dict[str, object]) -> str:
    """Create the event, or overwrite the one already stored under this uid.

    Returns "created" or "updated" so the caller can report what happened.
    """
    stored = existing.get(uid)

    if stored is None:
        calendar.save_event(document)
        return "created"

    stored.data = document
    stored.save()
    return "updated"


def sync_calendar(calendar, path: str = FIXTURES_PATH, dry_run: bool = False) -> Dict[str, int]:
    """Write every fixture in `path` to `calendar`.

    Only ever adds or updates: a match that disappears from the schedule is left
    in the calendar rather than deleted, since a fixture missing from a two-week
    refresh window has usually just fallen outside it, not been cancelled.
    """
    counts = {"created": 0, "updated": 0}
    existing = existing_by_uid(calendar)

    for uid, document in split_calendar(read_calendar_file(path)):
        if dry_run:
            # Reported from what the server actually holds, so a dry run says
            # the same thing the real run will do.
            counts["updated" if uid in existing else "created"] += 1
            continue
        counts[upsert_event(calendar, uid, document, existing)] += 1

    return counts
