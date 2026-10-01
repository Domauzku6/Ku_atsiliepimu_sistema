import json
import time
import urllib.parse
from datetime import date
from pathlib import Path
import requests
import truststore
from playwright.sync_api import sync_playwright
truststore.inject_into_ssl()

BASE = "https://tvarkarasciai.ku.lt"
DOMAIN = "tvarkarasciai.ku.lt"
PROFILE_DIR = Path(__file__).parent / "browser_profile"
LOGIN_TIMEOUT = 300


def make_session(cookies, resource_id):
    session = requests.Session()
    for c in cookies:
        if DOMAIN.endswith(c["domain"].lstrip(".")):
            session.cookies.set(c["name"], c["value"], domain=c["domain"], path=c["path"])
    xsrf = session.cookies.get("XSRF-TOKEN", "")
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/resources/{resource_id}",
        "X-XSRF-TOKEN": urllib.parse.unquote(xsrf),
    })
    return session


def get_reservations(session, resource_id, date_from, date_to):
    resp = session.get(
        f"{BASE}/api/resources/{resource_id}/reservations",
        params={"from": date_from, "to": date_to},
    )
    if resp.status_code in (401, 419):
        return None
    resp.raise_for_status()
    return resp.json()


def open_browser(p, headless):
    for channel in ("chrome", "msedge"):
        try:
            return p.chromium.launch_persistent_context(
                PROFILE_DIR, channel=channel, headless=headless
            )
        except Exception:
            continue
    raise SystemExit("Couldn't start Chrome or Edge. Is one of them installed?")


def try_saved_login(p, resource_id, date_from, date_to):
    context = open_browser(p, headless=True)
    try:
        page = context.new_page()
        page.goto(BASE, wait_until="domcontentloaded")
        session = make_session(context.cookies(), resource_id)
        return get_reservations(session, resource_id, date_from, date_to)
    finally:
        context.close()


def interactive_login(p, resource_id, date_from, date_to):
    context = open_browser(p, headless=False)
    try:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(BASE)
        print("Sign in to the timetable site in the Chrome window that opened...")

        deadline = time.time() + LOGIN_TIMEOUT
        while time.time() < deadline:
            if page.is_closed():
                raise SystemExit("Chrome window was closed before signing in.")
            session = make_session(context.cookies(), resource_id)
            data = get_reservations(session, resource_id, date_from, date_to)
            if data is not None:
                print("Signed in.")
                return data
            page.wait_for_timeout(2000)
        raise SystemExit(f"Didn't see a successful sign-in within {LOGIN_TIMEOUT} seconds.")
    finally:
        context.close()


def fetch_resource(resource_id, date_from, date_to):
    """Fetch all reservations of one resource between two dates (YYYY-MM-DD)."""
    with sync_playwright() as p:
        data = try_saved_login(p, resource_id, date_from, date_to)
        if data is None:
            data = interactive_login(p, resource_id, date_from, date_to)
        return data


def get_todays_date_iso():

    todays_Date = date.fromtimestamp(time.time())
    date_in_ISOFormat = todays_Date.isoformat()
    #print(date_in_ISOFormat)
    return date_in_ISOFormat


def download_reservations():
    date_from: str = get_todays_date_iso()
    resource_id: int = 16
    date_to = date_from

    data = fetch_resource(resource_id, date_from, date_to)

    out = "reservations.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # response is {"data": [room, ...]}, each room has {"reservations": {date: [...]}}
    rooms = data["data"]
    count = sum(len(day) for room in rooms for day in room["reservations"].values())
    print(f"Saved {count} reservations in {len(rooms)} rooms to {out}")
if __name__ == "__main__":
    download_reservations()