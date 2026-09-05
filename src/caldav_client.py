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
    apple_id = os.getenv("APPLE_ID")
    app_password = os.getenv("APPLE_APP_PASSWORD")

    if not apple_id or not app_password:
        raise RuntimeError(
            "APPLE_ID and APPLE_APP_PASSWORD must be set; add them to .env. "
            "The password is an app-specific password from appleid.apple.com, "
            "not your Apple ID password."
        )

    return DAVClient(
        url=ICLOUD_CALDAV_URL, username=apple_id, password=app_password
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
