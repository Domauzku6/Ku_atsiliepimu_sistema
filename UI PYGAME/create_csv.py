import csv
from pathlib import Path

import download_reservations as dl
from calendar_lookup import calendar_lookup, current_time

CSV_FILE = Path(__file__).parent / "proof_of_concept.csv"
HEADERS = ["kabinetas", "dėstytojas", "paskaita", "laikas", "atsiliepimas (1-10)", "komentaras"]


def create_csv(path: Path = CSV_FILE) -> bool:
    """Sukuria CSV su antrašte tik jei failo dar nėra. Esamo failo neliečia.
    Grąžina True, jei failas buvo sukurtas."""
    if path.exists():
        return False
    # utf-8-sig, kad Excel teisingai rodytų ą, č, ž...
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow(HEADERS)
    return True


def save_to_csv(kabinetas: str, atsiliepimas: int, komentaras: str = "",
                path: Path = CSV_FILE, lecture: tuple | None = None) -> list | None:
    """Suranda, kas dabar vyksta kabinete, ir prideda atsiliepimą į CSV.
    lecture – jau rastas (dėstytojas, paskaita), kad nereikėtų ieškoti dar kartą.
    Grąžina įrašytą eilutę arba None, jei kabinete paskaitos nėra."""
    if not 1 <= atsiliepimas <= 10:
        raise ValueError("Atsiliepimas turi būti nuo 1 iki 10")

    result = lecture or calendar_lookup(kabinetas)
    if result is None:
        return None
    destytojas, paskaita = result

    laikas = f"{dl.get_todays_date_iso()} {current_time()}"
    row = [kabinetas, destytojas or "", paskaita, laikas, atsiliepimas, komentaras.strip()]

    create_csv(path)
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)
    return row


if __name__ == "__main__":
    print("Sukurtas naujas failas" if create_csv() else f"{CSV_FILE.name} jau yra – nekeičiamas")
    print(save_to_csv("311", 10, "Puiki paskaita") or "Kabinete 311 dabar paskaitos nėra")
