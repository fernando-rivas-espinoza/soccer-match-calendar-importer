"""Tests for src/sync.py against an in-memory stand-in for a CalDAV calendar."""

import pytest

from src.sync import (
    existing_by_uid,
    read_calendar_file,
    split_calendar,
    sync_calendar,
    upsert_event,
)
from src.translate import write_calendar


TEAM = "FC Barcelona"

SCHEDULE = {
    497855: {
        "match_date": "2026-08-29T19:00:00Z",
        "matchday": 3,
        "venue_status": "home",
        "opponent_name": "Real Madrid CF",
        "opponent_id": 86,
        "competition_name": "La Liga",
        "competition_id": 2014,
    },
    497856: {
        "match_date": "2026-09-06T14:15:00Z",
        "matchday": 4,
        "venue_status": "away",
        "opponent_name": "Valencia CF",
        "opponent_id": 95,
        "competition_name": "La Liga",
        "competition_id": 2014,
    },
}


class FakeEvent:
    def __init__(self, calendar, uid):
        self.calendar = calendar
        self.uid = uid
        self.data = calendar.stored[uid]

    @property
    def icalendar_component(self):
        return {"UID": self.uid}

    def save(self):
        self.calendar.stored[self.uid] = self.data
        self.calendar.saves.append(self.uid)


class FakeCalendar:
    """Records writes instead of talking to a server.

    Models only what iCloud actually supports: listing the calendar. It has no
    event_by_uid, because iCloud answers that query with 412 and any code that
    reaches for it here should fail in the tests too.
    """

    def __init__(self):
        self.stored = {}
        self.saves = []
        self.creates = []
        self.listings = 0

    def events(self):
        self.listings += 1
        return [FakeEvent(self, uid) for uid in self.stored]

    def save_event(self, data):
        uid = next(
            line.split(":", 1)[1]
            for line in data.split("\r\n")
            if line.startswith("UID:")
        )
        self.stored[uid] = data
        self.creates.append(uid)
        return FakeEvent(self, uid)


@pytest.fixture
def fixtures_file(tmp_path):
    path = tmp_path / "fixtures.ics"
    write_calendar(SCHEDULE, TEAM, path=str(path))
    return str(path)


class TestSplitCalendar:
    def test_yields_one_document_per_event(self, fixtures_file):
        assert len(list(split_calendar(read_calendar_file(fixtures_file)))) == 2

    def test_each_document_is_a_whole_calendar(self, fixtures_file):
        """CalDAV resources are full VCALENDARs, not bare VEVENTs."""
        for _, document in split_calendar(read_calendar_file(fixtures_file)):
            assert document.startswith("BEGIN:VCALENDAR")
            assert document.rstrip("\r\n").endswith("END:VCALENDAR")

    def test_each_document_holds_exactly_one_event(self, fixtures_file):
        for _, document in split_calendar(read_calendar_file(fixtures_file)):
            assert document.count("BEGIN:VEVENT") == 1

    def test_uids_are_reported_and_unique(self, fixtures_file):
        uids = [uid for uid, _ in split_calendar(read_calendar_file(fixtures_file))]
        assert sorted(uids) == [
            "497855@soccer-match-calendar-importer",
            "497856@soccer-match-calendar-importer",
        ]

    def test_uid_matches_the_document_it_is_paired_with(self, fixtures_file):
        for uid, document in split_calendar(read_calendar_file(fixtures_file)):
            assert f"UID:{uid}" in document

    def test_documents_keep_crlf_line_endings(self, fixtures_file):
        for _, document in split_calendar(read_calendar_file(fixtures_file)):
            assert document.count("\n") == document.count("\r\n")

    def test_long_lines_are_folded(self, tmp_path):
        """icalendar folds at 75 octets where ics.py 0.7 does not."""
        long_name = "Borussia Monchengladbach Fussball-Club 1900 e.V."
        schedule = {1: dict(SCHEDULE[497855], opponent_name=long_name)}
        path = tmp_path / "long.ics"
        write_calendar(schedule, "Fussball-Club Bayern Munchen e.V.", path=str(path))
        for _, document in split_calendar(read_calendar_file(str(path))):
            for line in document.split("\r\n"):
                assert len(line.encode()) <= 75


class TestUpsertEvent:
    def test_creates_an_event_that_is_not_there_yet(self, fixtures_file):
        calendar = FakeCalendar()
        uid, document = next(split_calendar(read_calendar_file(fixtures_file)))
        assert upsert_event(calendar, uid, document, {}) == "created"
        assert calendar.creates == [uid]

    def test_updates_an_event_that_already_exists(self, fixtures_file):
        calendar = FakeCalendar()
        uid, document = next(split_calendar(read_calendar_file(fixtures_file)))
        upsert_event(calendar, uid, document, {})
        existing = existing_by_uid(calendar)
        assert upsert_event(calendar, uid, document, existing) == "updated"
        assert calendar.saves == [uid]

    def test_creating_twice_does_not_duplicate(self, fixtures_file):
        """Second safety net: caldav PUTs to a url derived from the uid, so even
        a lookup that wrongly reports the event as absent overwrites it."""
        calendar = FakeCalendar()
        uid, document = next(split_calendar(read_calendar_file(fixtures_file)))
        upsert_event(calendar, uid, document, {})
        upsert_event(calendar, uid, document, {})
        assert len(calendar.stored) == 1

    def test_an_update_overwrites_the_stored_document(self, fixtures_file):
        calendar = FakeCalendar()
        uid, document = next(split_calendar(read_calendar_file(fixtures_file)))
        upsert_event(calendar, uid, document, {})
        moved = document.replace("DTSTART:20260829T190000Z", "DTSTART:20260830T150000Z")
        upsert_event(calendar, uid, moved, existing_by_uid(calendar))
        assert "DTSTART:20260830T150000Z" in calendar.stored[uid]


class TestSyncCalendar:
    def test_writes_every_fixture(self, fixtures_file):
        calendar = FakeCalendar()
        assert sync_calendar(calendar, fixtures_file) == {"created": 2, "updated": 0}
        assert len(calendar.stored) == 2

    def test_a_second_run_updates_rather_than_duplicating(self, fixtures_file):
        """The whole point of a stable uid: re-running must not double the calendar."""
        calendar = FakeCalendar()
        sync_calendar(calendar, fixtures_file)
        assert sync_calendar(calendar, fixtures_file) == {"created": 0, "updated": 2}
        assert len(calendar.stored) == 2

    def test_a_rescheduled_match_moves_the_same_event(self, tmp_path, fixtures_file):
        calendar = FakeCalendar()
        sync_calendar(calendar, fixtures_file)

        moved_path = tmp_path / "moved.ics"
        moved = dict(SCHEDULE)
        moved[497855] = dict(SCHEDULE[497855], match_date="2026-08-30T15:00:00Z")
        write_calendar(moved, TEAM, path=str(moved_path))

        assert sync_calendar(calendar, str(moved_path))["updated"] == 2
        assert len(calendar.stored) == 2
        stored = calendar.stored["497855@soccer-match-calendar-importer"]
        assert "DTSTART:20260830T150000Z" in stored

    def test_dry_run_writes_nothing(self, fixtures_file):
        calendar = FakeCalendar()
        counts = sync_calendar(calendar, fixtures_file, dry_run=True)
        assert counts["created"] == 2
        assert calendar.stored == {}
        assert calendar.creates == []

    def test_dry_run_reports_updates_for_events_already_on_the_server(
        self, fixtures_file
    ):
        """A dry run must predict what the real run does, not assume an empty calendar."""
        calendar = FakeCalendar()
        sync_calendar(calendar, fixtures_file)
        assert sync_calendar(calendar, fixtures_file, dry_run=True) == {
            "created": 0,
            "updated": 2,
        }

    def test_the_server_is_listed_once_not_once_per_fixture(self, fixtures_file):
        """iCloud rejects the per-uid REPORT, and 36 round trips would be wasteful."""
        calendar = FakeCalendar()
        sync_calendar(calendar, fixtures_file)
        assert calendar.listings == 1
