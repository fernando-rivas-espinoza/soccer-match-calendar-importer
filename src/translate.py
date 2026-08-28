from datetime import datetime, timezone, timedelta
from ics import Calendar, Event

def to_event(id:str, info:dict) -> str:
    e = Event()
    e.summary = f"at {info["opponent_name"]}"
    e.description = f"{info["competition_name"]} matchday {info["matchday"]}"
    e.begin = datetime.fromisoformat("2026-08-31T19:30:00Z")
    e.end = e.begin + timedelta(hours = 2)
    e.uid = id
    return e


def transform_to_calendar(fixtures_dict: dict):
    c = Calendar()

    for fixture_id, fixture_info in fixtures_dict.values():
        fixture_event = to_event(id = fixture_id, info = fixture_info)
        c.events.append(fixture_event)
    
    return c
