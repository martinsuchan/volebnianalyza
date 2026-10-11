# Forenzní audit – komunální volby Praha 2026 a senátní volby 2026 (1. kolo)

> **Upozornění:** Tato analýza i report byly vytvořeny s pomocí AI modelu **Claude Opus 5.5** (Anthropic) pod dohledem autora.
> Mohou obsahovat chyby ve výpočtech, interpretaci i formulacích.
>
> - Nejde o oficiální výsledky voleb ani o právní či znalecký posudek.
> - Statistické nálezy nejsou důkazem chyby ani úmyslného jednání. Označují místa, kde je vhodné ověřit originální zápisy okrskových komisí.
> - Závazné jsou pouze výsledky vyhlášené Státní volební komisí a údaje Českého statistického úřadu.
> - Před jakýmkoli dalším použitím si nálezy ověřte v primárních datech; každý nález v reportu obsahuje odkaz na volby.gov.cz.

Nezávislá analýza otevřených okrskových dat ČSÚ:

- **Komunální volby 9.–10. 10. 2026:** Zastupitelstvo hl. m. Prahy a 57 zastupitelstev městských částí, srovnání s lety 2018 a 2022.
- **Senátní volby 2026, 1. kolo:** 27 obvodů. Srovnání okrsek po okrsku s komunálními volbami konanými ve stejný den a se senátními volbami 2018, 2020 a 2022.

**Výstupy:**

- `report/index.html` – statický web: manažerský report, nálezy, mapa, testy, metodika, data.
- `report/senat.html` – samostatná stránka senátní analýzy.
- `report/manazersky_report.md` a `report/senat_manazersky_report.md` – manažerská shrnutí.
- `report/data/*.csv` – mezivýsledky ke stažení.

Autor: [Martin Suchan](https://www.facebook.com/martinsuchan85) · Licence: MIT (viz `LICENSE`).

## Jak si analýzu spustit sám

Potřebujete **Python 3.12 nebo novější** (testováno na 3.13) a asi **1 GB volného místa**. Postup má tři kroky:

1. Stažení dat ČSÚ zabere asi 5–10 minut (cca 420 MB).
2. Výpočet zabere asi 5–10 minut.
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
- `scripts/run_all.py` spustí celou pipeline a vygeneruje web do `report/`. Mezivýsledky ukládá do `data/processed/` a `data/results/`.

**Rozdíly proti zveřejněnému reportu:** pokud ČSÚ mezitím data opravil, mohou se výsledky mírně lišit. Report v repozitáři odpovídá datům ke dni 11. 10. 2026.

### Pořadí kroků (pro vývoj)

| Krok | Skript | Co dělá |
|---|---|---|
| 1 | `etl.py`, `geo.py` | výřez Prahy z dat KV, těžiště okrsků |
| 2 | `integrity.py`, `seats.py` | deterministické kontroly zápisů, nezávislý přepočet mandátů |
| 3 | `anomalies.py`, `missing.py`, `stacks.py`, `typos.py` | prostorový model hlasů, chybějící balíky lístků, překlepy u kandidátů |
| 4 | `batches.py`, `fingerprints.py` | XML dávky volební noci, globální forenzní testy |
| 5 | `materiality.py`, `findings.py` | simulace oprav a dopadu na mandáty, registr nálezů |
| 6 | `se_etl.py`, `se_audit.py` | senátní volby: data, kontroly, srovnání s KV, testy |
| 7 | `build_site.py` (+ `build_senat.py`, `svg.py`) | generování statického webu |

`run_all.py` spouští kroky v tomto pořadí. Navíc mezi kroky 3 a 4 dopočítá detektory pro srovnávací rok 2018 (`python scripts/run_all.py year2018`).

Detail jednoho pražského okrsku vypíše `python scripts/deepdive.py 500224/10043`.

## Zdroje dat

- Český statistický úřad, [volby.gov.cz – otevřená data](https://volby.gov.cz/opendata/opendata.htm):
  - komunální volby 2018, 2022, 2026;
  - volby do Senátu 2018, 2020, 2022, 2026;
  - XML dávky;
  - hranice volebních okrsků 2022.
- Data ČSÚ podléhají [podmínkám pro využívání a další zveřejňování statistických údajů ČSÚ](https://csu.gov.cz/podminky_pro_vyuzivani_a_dalsi_zverejnovani_statistickych_udaju_csu).
