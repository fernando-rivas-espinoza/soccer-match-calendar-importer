"""Tests for src/translate.py.

Nothing here touches the network or a calendar server; the fixtures below are
the shape `fetch.extract_schedule` returns.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from src.translate import (
    MATCH_DURATION,
    apply_default_kickoff,
    parse_match_date,
    to_event,
    to_ics,
    transform_to_calendar,
    write_calendar,
)


TEAM = "FC Barcelona"

HOME_MATCH = {
    "match_date": "2026-08-29T19:00:00Z",
    "matchday": 3,
    "venue_status": "home",
    "opponent_name": "Real Madrid CF",
    "opponent_id": 86,
    "competition_name": "La Liga",
    "competition_id": 2014,
}

AWAY_MATCH = dict(HOME_MATCH, venue_status="away", opponent_name="Valencia CF")


def lines(ics):
    return ics.split("\r\n")


def property_of(ics, name):
    return [line for line in lines(ics) if line.startswith(name + ":")]


class TestParseMatchDate:
    def test_reads_the_apis_z_suffix(self):
        """`fromisoformat` only accepts "Z" from 3.11; this project supports 3.9."""
        assert parse_match_date("2026-08-29T19:00:00Z") == datetime(
            2026, 8, 29, 19, 0, tzinfo=timezone.utc
        )

    def test_result_is_timezone_aware(self):
        """A naive kickoff would be written to the calendar as local time."""
        assert parse_match_date("2026-08-29T19:00:00Z").tzinfo is not None

    def test_an_explicit_offset_is_preserved(self):
        assert parse_match_date("2026-08-29T21:00:00+02:00") == datetime(
            2026, 8, 29, 19, 0, tzinfo=timezone.utc
        )

    def test_a_naive_timestamp_is_assumed_to_be_utc(self):
        assert parse_match_date("2026-08-29T19:00:00").tzinfo == timezone.utc


class TestApplyDefaultKickoff:
    """A 00:00:00Z kickoff is the api saying "slot not announced yet"."""

    def test_an_announced_kickoff_is_left_alone(self):
        announced = parse_match_date("2026-08-29T19:00:00Z")
        assert apply_default_kickoff(announced) == announced

    def test_an_unannounced_kickoff_moves_to_3pm_eastern(self):
        moved = apply_default_kickoff(parse_match_date("2026-09-13T00:00:00Z"))
        assert moved == datetime(2026, 9, 13, 19, 0, tzinfo=timezone.utc)

    def test_the_default_reads_as_3pm_eastern_in_summer_time(self):
        moved = apply_default_kickoff(parse_match_date("2026-09-13T00:00:00Z"))
        assert moved.astimezone(ZoneInfo("America/New_York")).hour == 15

    def test_the_default_reads_as_3pm_eastern_in_winter_time(self):
        """A fixed -5 offset would drift to 4pm across the DST boundary."""
        moved = apply_default_kickoff(parse_match_date("2026-01-17T00:00:00Z"))
        assert moved == datetime(2026, 1, 17, 20, 0, tzinfo=timezone.utc)
        assert moved.astimezone(ZoneInfo("America/New_York")).hour == 15

    def test_the_match_keeps_its_own_date(self):
        """Only the time is a placeholder; the date is real."""
        moved = apply_default_kickoff(parse_match_date("2026-09-13T00:00:00Z"))
        assert moved.astimezone(ZoneInfo("America/New_York")).date().isoformat() == (
            "2026-09-13"
        )

    def test_a_kickoff_one_minute_off_midnight_is_not_treated_as_a_placeholder(self):
        real = parse_match_date("2026-09-13T00:01:00Z")
        assert apply_default_kickoff(real) == real


class TestToEvent:
    def test_home_match_puts_the_opponent_at_our_ground(self):
        assert to_event(497855, HOME_MATCH, TEAM).name == "Real Madrid CF at FC Barcelona"

    def test_away_match_puts_us_at_the_opponents_ground(self):
        assert to_event(497855, AWAY_MATCH, TEAM).name == "FC Barcelona at Valencia CF"

    def test_description_carries_competition_and_matchday(self):
        assert to_event(497855, HOME_MATCH, TEAM).description == "La Liga matchday 3"

    def test_a_null_matchday_is_left_out_of_the_description(self):
        """Cup ties are not numbered, so the api sends matchday as null."""
        cup = dict(HOME_MATCH, matchday=None, competition_name="UEFA Champions League")
        assert to_event(1, cup, TEAM).description == "UEFA Champions League"

    def test_a_missing_matchday_does_not_raise(self):
        no_matchday = {k: v for k, v in HOME_MATCH.items() if k != "matchday"}
        assert to_event(1, no_matchday, TEAM).description == "La Liga"

    def test_uid_is_built_from_the_match_id(self):
        assert to_event(497855, HOME_MATCH, TEAM).uid.startswith("497855@")

    def test_uid_is_namespaced_so_it_cannot_clash_with_other_sources(self):
        assert "@" in to_event(497855, HOME_MATCH, TEAM).uid

    def test_starts_at_the_api_kickoff(self):
        event = to_event(497855, HOME_MATCH, TEAM)
        assert event.begin.datetime == datetime(2026, 8, 29, 19, 0, tzinfo=timezone.utc)

    def test_ends_one_match_duration_after_kickoff(self):
        event = to_event(497855, HOME_MATCH, TEAM)
        assert event.end.datetime - event.begin.datetime == MATCH_DURATION

    def test_an_unannounced_kickoff_is_defaulted_on_the_event(self):
        tbc = dict(HOME_MATCH, match_date="2026-09-13T00:00:00Z")
        assert to_event(1, tbc, TEAM).begin.datetime == datetime(
            2026, 9, 13, 19, 0, tzinfo=timezone.utc
        )

    def test_kickoff_is_not_hardcoded(self):
        """Regression: every event once carried the same literal date."""
        other = dict(HOME_MATCH, match_date="2026-09-06T14:15:00Z")
        assert to_event(1, other, TEAM).begin.datetime == datetime(
            2026, 9, 6, 14, 15, tzinfo=timezone.utc
        )


class TestToIcs:
    def test_is_a_complete_calendar_document(self):
        """CalDAV wants a whole VCALENDAR per resource, not a bare VEVENT."""
        ics = to_ics(497855, HOME_MATCH, TEAM)
        assert lines(ics)[0] == "BEGIN:VCALENDAR"
        assert lines(ics)[-1] == "END:VCALENDAR"

    def test_holds_exactly_one_event(self):
        ics = to_ics(497855, HOME_MATCH, TEAM)
        assert ics.count("BEGIN:VEVENT") == 1

    def test_summary_reaches_the_serialised_output(self):
        """Regression: ics.py reads SUMMARY from `.name`; `.summary` is dropped."""
        assert property_of(to_ics(497855, HOME_MATCH, TEAM), "SUMMARY") == [
            "SUMMARY:Real Madrid CF at FC Barcelona"
        ]

    def test_carries_a_dtstamp(self):
        """RFC 5545 requires it, and ics.py omits it unless `.created` is set."""
        assert property_of(to_ics(497855, HOME_MATCH, TEAM), "DTSTAMP")

    def test_start_and_end_are_utc(self):
        ics = to_ics(497855, HOME_MATCH, TEAM)
        assert property_of(ics, "DTSTART") == ["DTSTART:20260829T190000Z"]
        assert property_of(ics, "DTEND") == ["DTEND:20260829T210000Z"]

    def test_lines_end_with_crlf(self):
        ics = to_ics(497855, HOME_MATCH, TEAM)
        assert "\r\n" in ics
        assert ics.count("\n") == ics.count("\r\n")


class TestTransformToCalendar:
    def test_one_event_per_fixture(self):
        schedule = {497855: HOME_MATCH, 497856: AWAY_MATCH}
        assert len(transform_to_calendar(schedule, TEAM).events) == 2

    def test_each_event_takes_its_uid_from_its_key(self):
        """Regression: iterating .values() lost the id the uid is built from."""
        schedule = {497855: HOME_MATCH, 497856: AWAY_MATCH}
        uids = {event.uid for event in transform_to_calendar(schedule, TEAM).events}
        assert uids == {
            "497855@soccer-match-calendar-importer",
            "497856@soccer-match-calendar-importer",
        }

    def test_an_empty_schedule_yields_an_empty_calendar(self):
        assert len(transform_to_calendar({}, TEAM).events) == 0


class TestWriteCalendar:
    def test_writes_crlf_line_endings(self, tmp_path):
        """Text mode would rewrite ics.py's CRLF where linesep is CRLF."""
        path = tmp_path / "fixtures.ics"
        write_calendar({497855: HOME_MATCH}, TEAM, path=str(path))
        raw = path.read_bytes()
        assert b"\r\n" in raw
        assert raw.count(b"\n") == raw.count(b"\r\n")

    def test_writes_a_readable_calendar(self, tmp_path):
        path = tmp_path / "fixtures.ics"
        write_calendar({497855: HOME_MATCH}, TEAM, path=str(path))
        text = path.read_text()
        assert text.startswith("BEGIN:VCALENDAR")
        assert "SUMMARY:Real Madrid CF at FC Barcelona" in text
