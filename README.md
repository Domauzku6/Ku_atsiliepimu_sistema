# Ku_atsiliepimu_sistema

## Failai

| Failas | Paskirtis |
|---|---|
| `download_reservations.py` | Atsisiunčia šiandienos tvarkaraštį į `reservations.json` |
| `calendar_lookup.py` | Pagal kabinetą randa, ar dabar vyksta paskaita ir kas ją veda |

## Funkcijos

```python
import download_reservations as dl

calendar_lookup("215")      # grąžina dėstytoją ir paskaitą kabinete, jei kas nors vyksta
current_time()              # grąžina esamą laiką
dl.get_todays_date_iso()    # grąžina esamą dieną 'YYYY-MM-DD'
```

## Testavimas
```bash
git clone https://github.com/Domauzku6/Ku_atsiliepimu_sistema.git
```

```bash
pip install -r requirements.txt
```

```bash
python calendar_lookup.py
```

## Trūksta

- [ ] **GUI**: siūlau per bet kurį AI, svarbu kažkas gražaus ir veikiančio
siūlau naudot pygame library https://www.pygame.org/docs/
```bash
pip install pygame_ce
```
- [ ] **Atsakymų saugojimas**: funkcija arba metodas, kuris gautą atsakymą saugotų lokaliai CSV faile `proof_of_concept.csv`, su stulpeliais:

| kabinetas | dėstytojas | paskaita | laikas | atsiliepimas (1–10) |
|---|---|---|---|---|
