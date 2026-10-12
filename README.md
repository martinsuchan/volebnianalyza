# Forenzní audit – komunální volby Praha 2026 a senátní volby 2026 (1. kolo)

> **Upozornění:** Tato analýza i report byly vytvořeny s pomocí AI modelu **Claude Opus 5.5** (Anthropic) pod dohledem autora.
> Mohou obsahovat chyby ve výpočtech, interpretaci i formulacích.
>
> - Nejde o oficiální výsledky voleb ani o právní či znalecký posudek.
> - Statistické nálezy nejsou důkazem chyby ani úmyslného jednání. Označují místa, kde je vhodné ověřit originální zápisy okrskových komisí.
> - Závazné jsou pouze výsledky vyhlášené Státní volební komisí a údaje Českého statistického úřadu.
> - Před jakýmkoli dalším použitím si nálezy ověřte v primárních datech; každý nález v reportu obsahuje odkaz na volby.gov.cz.

Nezávislá analýza otevřených okrskových dat ČSÚ:

- **Komunální volby 9.–10. 10. 2026:** všech 13 krajských měst včetně jejich městských částí a obvodů sídla ostatních 193 obcí s rozšířenou působností (ORP) a 183 dalších obcí s pověřeným obecním úřadem (POU), srovnání s lety 2018 a 2022.
  - Praha má registr nálezů jednotlivě ověřený v datech.
  - U ostatních obcí registr sestavuje šablona; kontrolu jednotlivých nálezů v datech provádějí AI agenti podle `review/ZADANI.md` a zapisuje se do `review/<obec>.json`.
- **Senátní volby 2026, 1. kolo:** 27 obvodů. Srovnání okrsek po okrsku s komunálními volbami konanými ve stejný den a se senátními volbami 2018, 2020 a 2022.

**Výstupy:**

- `report/index.html` – statický web (rozcestník s vyhledáváním obce, MČ nebo senátního obvodu). Obsahuje:
  - `kv/index.html` – seznam obcí s auditem komunálních voleb;
  - `kv/<obec>/` – stránky obce se záložkami Přehled, Nálezy, Mapa okrsků a Forenzní testy (zatím `kv/praha/`);
  - `senat/index.html` – senátní volby;
  - `nalezy.html` – společný registr všech nálezů s filtry;
  - `metodika.html` a `data.html`.
- `report/manazersky_report.md` a `report/senat_manazersky_report.md` – manažerská shrnutí.
- `report/data/*.csv` – mezivýsledky ke stažení.

Autor: [Martin Suchan](https://www.facebook.com/martinsuchan85) · Licence: MIT (viz `LICENSE`).

## Jak si analýzu spustit sám

Potřebujete **Python 3.12 nebo novější** (testováno na 3.13) a asi **1 GB volného místa**. Postup má tři kroky:

1. Stažení dat ČSÚ zabere asi 5–10 minut (cca 420 MB).
2. Výpočet 13 krajských měst a senátu zabere asi 15 minut; 193 sídel ORP dalších zhruba 90 minut (`--units orp`), 183 sídel POU zhruba 75 minut (`--units pou`).
3. Výsledek otevřete v prohlížeči.

### Windows (PowerShell)

```powershell
git clone https://github.com/martinsuchan/volebnianalyza.git
cd volebnianalyza
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\download.py
.venv\Scripts\python scripts\run_all.py
start report\index.html
```

### Linux / macOS

```bash
git clone https://github.com/martinsuchan/volebnianalyza.git
cd volebnianalyza
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/download.py
.venv/bin/python scripts/run_all.py
open report/index.html        # na Linuxu: xdg-open report/index.html
```

### Co skripty dělají

- `scripts/download.py` stáhne do `data/raw/`:
  - okrsková data, registry kandidátů a číselníky KV 2018/2022/2026 a Senátu 2018/2020/2022/2026;
  - XML dávky z volební noci 2026;
  - hranice volebních okrsků.

  Názvy souborů zjišťuje z indexových stránek [volby.gov.cz/opendata](https://volby.gov.cz/opendata/opendata.htm), protože ČSÚ při opravě dat mění datum v názvu. Už stažené soubory přeskakuje; `--force` stáhne vše znovu.
- `scripts/run_all.py` spustí celou pipeline a vygeneruje web do `report/`.
  - Komunální volby počítá postupně pro každé město; město se volí proměnnou prostředí `AUDIT_UNIT`, např. `brno`.
  - Mezivýsledky měst ukládá do `data/processed/kv/<město>/` a `data/results/kv/<město>/`, senátní do `data/processed/` a `data/results/`.
  - Jen vybraná města: `python scripts/run_all.py --units brno,plzen`.
  - Sídla obcí s rozšířenou působností: `python scripts/run_all.py --units orp --keep-going --no-global`, pak `python scripts/build_site.py`.
    Sídlo ORP se určuje z registru ČSÚ (`kvrzcoco.csv`, sloupec `ORP`) v `scripts/units.py`.
  - Sídla pověřených obecních úřadů: `--units pou`; sídlo POU je obec, která je registračním úřadem (`kvrzcoco.csv`, sloupec `REGURAD`).

**Rozdíly proti zveřejněnému reportu:** pokud ČSÚ mezitím data opravil, mohou se výsledky mírně lišit. Report v repozitáři odpovídá datům ke dni 11. 10. 2026.

### Pořadí kroků (pro vývoj)

| Krok | Skript | Co dělá |
|---|---|---|
| 1 | `etl.py`, `geo.py` | výřez města (`AUDIT_UNIT`) z celostátních dat KV, těžiště okrsků |
| 2 | `integrity.py`, `seats.py` | deterministické kontroly zápisů, nezávislý přepočet mandátů |
| 3 | `anomalies.py`, `missing.py`, `stacks.py`, `typos.py` | prostorový model hlasů, chybějící balíky lístků, překlepy u kandidátů |
| 4 | `batches.py`, `fingerprints.py` | XML dávky volební noci, globální forenzní testy |
| 5 | `materiality.py`, `findings.py` / `findings_auto.py` | simulace oprav a dopadu na mandáty, registr nálezů (Praha ručně, ostatní šablonou) |
| 6 | `se_etl.py`, `se_audit.py` | senátní volby: data, kontroly, srovnání s KV, testy |
| 7 | `build_unit.py` (stránky měst), `build_site.py` (+ `build_senat.py`, `sablona.py`, `units.py`, `svg.py`) | generování statického webu: šablona stránek, registr obcí, grafy |

`run_all.py` spouští kroky 1–5 pro každé město, pak krok 6 a 7. Navíc:

- Mezi kroky 3 a 4 dopočítá detektory pro srovnávací rok 2018 (`python scripts/run_all.py year2018`).
- Pro Prahu se v kroku 5 použije ručně psaný `findings.py`.
- Pro ostatní města se použije šablona `findings_auto.py` a stránky města vygeneruje `build_unit.py`.
- Kontrola nálezů (AI agenti, případně člověk): zadání je v `review/ZADANI.md`, výsledky v `review/<obec>.json` (podle klíče nálezu). Generátor je při dalším běhu použije.

Detail jednoho okrsku vypíše `python scripts/deepdive.py 500224/10043` (s `AUDIT_UNIT` pro jiné město než Prahu).

## Zdroje dat

- Český statistický úřad, [volby.gov.cz – otevřená data](https://volby.gov.cz/opendata/opendata.htm):
  - komunální volby 2018, 2022, 2026;
  - volby do Senátu 2018, 2020, 2022, 2026;
  - XML dávky;
  - hranice volebních okrsků 2022.
- Data ČSÚ podléhají [podmínkám pro využívání a další zveřejňování statistických údajů ČSÚ](https://csu.gov.cz/podminky_pro_vyuzivani_a_dalsi_zverejnovani_statistickych_udaju_csu).
