# Ku_atsiliepimu_sistema

Paskaitų atsiliepimų kioskas (Raspberry Pi su jutikliniu ekranu arba Windows).
Studentas pasirenka kabinetą, mato vykstančią paskaitą ir dėstytoją, įvertina 1–10,
o jei įvertinimas mažesnis nei 5 – parašo komentarą ekraninėje klaviatūroje.

## Failai (`UI PYGAME/`)

| Failas | Paskirtis |
|---|---|
| `kiosk.py` | Kiosko programa (pygame): kabinetas → paskaita ir įvertinimas → komentaras → ačiū |
| `calendar_lookup.py` | Pagal kabinetą randa, ar dabar vyksta paskaita ir kas ją veda |
| `download_reservations.py` | Atsisiunčia šiandienos tvarkaraštį į `reservations.json` |
| `create_csv.py` | Sukuria `proof_of_concept.csv` (jei jo nėra) ir prideda atsiliepimus |
| `feedback_UI.py` | Ankstesnė UI versija; iš jos naudojama `wrap_text()` |

`reservations.json`, `proof_of_concept.csv` ir `browser_profile/` sukuriami paleidus programą ir į git nekeliami.

## CSV stulpeliai

| kabinetas | dėstytojas | paskaita | laikas | atsiliepimas (1-10) | komentaras |
|---|---|---|---|---|---|
| 311 | Andrius Stulgys | Kompiuterių ir pramoniniai tinklai | 2026-09-29 11:30 | 10 | |

## Paleidimas

```bash
git clone https://github.com/Domauzku6/Ku_atsiliepimu_sistema.git
cd "Ku_atsiliepimu_sistema/UI PYGAME"
pip install -r requirements.txt
python kiosk.py
```

Kioskas atsidaro per visą ekraną. Išeiti: **Esc** arba 15 kartų greitai paliesti paskaitos kortelę.
