"""CalDAV connection to iCloud.

This module owns credentials and the server URL; `sync.py` owns what gets
written. Nothing here reads the fixtures file or knows about matches.
"""

import os

from caldav import DAVClient
from dotenv import load_dotenv

# iCloud's CalDAV entry point. The library follows the redirect from here to the
# per-user principal URL, so the account-specific host never has to be hardcoded.
ICLOUD_CALDAV_URL = "https://caldav.icloud.com/"


def connect() -> DAVClient:
    """Open a client against iCloud using credentials from .env.

    The password must be an app-specific password generated at appleid.apple.com;
    iCloud rejects a plain Apple ID password on CalDAV when 2FA is on, which it
    is for every modern account.
    """
    load_dotenv()
    icloud_id = os.getenv("ICLOUD_ID")
    icloud_password = os.getenv("ICLOUD_PASSWORD")

    missing = [
        name
        for name, value in (("ICLOUD_ID", icloud_id), ("ICLOUD_PASSWORD", icloud_password))
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} must be set; add to .env. ICLOUD_ID is the "
            "Apple ID email for the account, and ICLOUD_PASSWORD must be an "
            "app-specific password from appleid.apple.com, not the Apple ID "
            "password itself."
        )

    return DAVClient(
        url=ICLOUD_CALDAV_URL, username=icloud_id, password=icloud_password
    )


def get_calendar(client: DAVClient, name: str):
    """Find the named calendar on the account.

    Deliberately does not create it. iCloud's support for MKCALENDAR is
    unreliable, and a typo silently creating a second calendar is worse than
    failing here, so the calendar is made once by hand in Calendar.app.
    """
    calendars = client.principal().calendars()

    for calendar in calendars:
        if calendar.name == name:
            return calendar

    available = ", ".join(sorted(repr(c.name) for c in calendars)) or "none"
    raise RuntimeError(
        f"no calendar named {name!r} on this account (found: {available}). "
        "Create it in Calendar.app under the iCloud account, then re-run."
    )
