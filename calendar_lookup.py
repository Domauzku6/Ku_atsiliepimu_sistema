import json
import re
from datetime import datetime, timedelta
import download_reservations as dl

TOLERANCE = timedelta(minutes=15)


def _room_number(room_name):
    """'103 A aud., (Bijūnų g. 17)' -> '103A', '201 aud. (...)' -> '201'."""
    m = re.match(r"\s*(\d+(?:\s?[A-Z])?)\b", room_name)
    return m.group(1).replace(" ", "") if m else None
def current_time():
    now = datetime.now()
    time_now = f"{now.hour}:{now.minute}"
    return time_now


def calendar_lookup(cabinet_number, path="reservations.json"):
    dl.download_reservations()
    day = dl.get_todays_date_iso()
    time = current_time()
    """
    cabinet_number: '201', 201 or '103A'
    time:           'HH:MM'
    day:            'YYYY-MM-DD'
    """
    with open(path, encoding="utf-8") as f:
        rooms = json.load(f)["data"]

    cabinet = str(cabinet_number).replace(" ", "").upper()
    t = datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M")

    best, best_gap = None, None
    for room in rooms:
        for r in room["reservations"].get(day, []):
            if _room_number(r["reservable"]["name"]) != cabinet:
                continue
            start = datetime.strptime(r["from"], "%Y-%m-%d %H:%M")
            end = datetime.strptime(r["to"], "%Y-%m-%d %H:%M")
            gap = max(start - t, t - end, timedelta(0))
            if gap <= TOLERANCE and (best_gap is None or gap < best_gap):
                best, best_gap = r, gap

    if best is None:
        return None
    responsible = best.get("responsible")
    lecturer = responsible["name"] if responsible else None
    return lecturer, best["name"]


if __name__ == "__main__":
    # dl = dowloand_reservations.py
    print(dl.get_todays_date_iso())
    print(calendar_lookup("215"))    #funkcija  isgauti destytojui ir kabinetui ar yra paskaita ir ar kas nors vyksta
    print(current_time())  # grazina esama laika
    print(dl.get_todays_date_iso()) # grazina esama diena  'YYYY-MM-DD'
    # truksta gui siulau per belekuri ai svarbu kazka grazaus ir veikiancio
    # truksta funkcijos arba metodo katras gauta atsakyma saugotu i tarkime csv faila lokaliai   kabinetas destytojas paskaita laikas atsiliepimas  1-10
    # csv pavadinimas proof_of_concept.csv
    #testavimas pip install -r requirements.txt
    #python calendar_lookup.py