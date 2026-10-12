# Zadání kontroly automatických nálezů (krajská města, KV 2026)

Cílem je ověřit každý automaticky vygenerovaný nález v `data/results/kv/<slug>/findings_2026.json` přímo v datech
a výsledek zapsat do `review/<slug>.json`. Generátor (`scripts/findings_auto.py`) kontrolu při dalším běhu použije.

## Pravidla práce
- Zapisuj **jen** soubor `review/<slug>.json` pro přidělené město. Žádné jiné soubory neměň a nespouštěj skripty, které zapisují
  do `data/` nebo `report/` (např. `findings_auto.py`, `build_unit.py`, `run_all.py`).
- **Nepoužívej síť** (volby.gov.cz blokuje opakované automatické dotazy). Lokální data jsou totožná s daty ČSÚ.
- Python: `.venv/Scripts/python -X utf8` v kořeni repozitáře `C:\git\volebni-analyza`, proměnná prostředí `AUDIT_UNIT=<slug>`.
- Texty piš česky, věcně a s konkrétními čísly. Desetinná čárka, mezera jako oddělovač tisíců. Nic si nedomýšlej: každé tvrzení musí jít ověřit v datech.

## Data
```python
import os, sys; os.environ['AUDIT_UNIT'] = 'brno'; sys.path.insert(0, 'scripts')
from common import load, RES
from anomalies import prep            # d, t3, hl, ros, nb = prep(2026); nb[OID] = 8 nejbližších okrsků
from materiality import outcome        # simulace dopadu opravy na mandáty a zvolené
d = load(2026); t3, hl, ros, rk, cm = d['t3'], d['hl'], d['ros'], d['rk'], d['councils']
```
- `t3` – okrskové zápisy: `OID` (= OBEC/OKRSEK), `ZK` (zastupitelstvo = KODZASTUP*100+COBVODU), `TYPZASTUP` (1 = město, 2 = MČ/MO), `MC`, `MANDATY`,
  `VOL_SEZNAM`, `VYD_OBALKY`, `ODEVZ_OBAL`, `PLAT_LISTKY` (platné lístky), `PL_HL_CELK` (platné hlasy celkem).
- `hl` – hlasy stran v okrscích: `OID`, `ZK`, `POR_STR_HL` (číslo strany), `POC_HLASU`, `HLASY_01` … `HLASY_70` (hlasy kandidátů podle pořadí).
- `ros` – strany: `ZK`, `POR_STR_HL`, `ZKRATKAO30`, `HLASY_STR`, `NCAND` (platní kandidáti); `rk` – kandidáti: `ZK`, `POR_STR_HL`, `PORCISLO`, `JMENO`, `PRIJMENI`, `POCHLASU`, `PLATNOST`, `MANDAT`.
- `cm` – zastupitelstva: index `ZK`, `NAZEVZAST`, `MANDATY`.
- `load(2022)` pro srovnání se stejným okrskem v roce 2022 (pozor: v roce 2022 chybí `PLAT_LISTKY`; hranice okrsků se mohly změnit).
- Výsledky detektorů v `data/results/kv/<slug>/`: `findings_2026.json`, `shares_2026.pkl` (podíl strany vs. sousedé, `e` = očekávaný podíl),
  `stacks_2026.pkl`, `zeros_2026.pkl`, `missing_2026.pkl` (`vpb` = hlasy na lístek / mandáty), `typos_2026.pkl`, `cross_2026.pkl`,
  `materiality_2026.pkl`, `seats.csv` (přepočet mandátů a rezervy), `precinct_2026.pkl`.
- Simulace: `seats, elected = outcome(ros, rk, cm, zk, dV={strana: +hlasy}, dC={(strana, porcislo): +hlasy})` a porovnání s `outcome(ros, rk, cm, zk)`.

## Volební pravidla (zákon č. 491/2001 Sb.)
- Volič může dát až tolik hlasů, kolik je mandátů (M). Křížek u strany dává hlas prvním M kandidátům listiny (resp. všem, je-li jich méně).
  Proto: hlasy kandidáta ≥ počet lístků s křížkem u strany; kandidáti uprostřed listiny nemohou mít výrazně méně než oba sousedé;
  `PL_HL_CELK ≤ PLAT_LISTKY × M`.
- 5% hranice (pro neúplné kandidátky přepočtená), d'Hondt, preferenční posun kandidáta s ≥ 110 % průměru hlasů strany.

## Co u každého nálezu ověřit
1. Že čísla v textu odpovídají datům (zapsané hodnoty, očekávání ze sousedních okrsků, rok 2022).
2. Konkrétní vzorec chyby: např. „kandidáti č. 26–55 mají 0 hlasů, č. 1–25 shodně ~25“ (nedopsaný zápis), „celá strana 0“ (nezapsaný řádek),
   jedna vložená číslice. Popiš ho v poli `zjisteni` konkrétně.
3. Alternativní vysvětlení: skutečná místní preference (projeví se i v roce 2022 nebo na druhém lístku), malý nebo zvláštní okrsek
   (nemocnice, domov seniorů), změna hranic okrsku, kratší kandidátka, než je počet mandátů.
4. Dopad: u nálezů s určenou stranou simuluj opravu (`outcome`) – konzervativně i horní odhad – a uveď, zda se mění mandáty nebo zvolení
   (konkrétně kdo). U nálezů „Může změnit mandáty“ bez simulace se pokus stranu identifikovat a simulovat; pokud to nejde, dopad zmírni a vysvětli.
5. Souhrnné nálezy (překlepy, nulová neplatnost, rozdíl obálek, těsné výsledky, rozdíly mezi lístky) zkontroluj namátkou a u „k ověření“ (klíč `cross`)
   rozhodni, zda jde o chyby, nebo o místní vzorce; případně jistotu uprav nebo nález vyřaď.

## Škála jistoty (pravděpodobnost, že zveřejněný údaj neodpovídá skutečnosti)
5 Jistá – deterministický rozpor · 4 Velmi vysoká ≥ 95 % (dvě nezávislé linie důkazů nebo logická nemožnost) · 3 Vysoká 80–95 % · 2 Střední 50–80 % · 1 Nízká < 50 % (riziko, nikoli zjištěná chyba)

## Formát `review/<slug>.json`
Objekt klíčovaný polem `klic` nálezu. Uveď **každý** nález. Pole `kontrola` je povinné (1–2 věty: co a jak bylo ověřeno); ostatní pole jen při změně:
```json
{
  "stack:551007/13009:58278601:4": {
    "kontrola": "Ověřeno v datech okrsku: kandidáti ANO č. 1–25 mají 25–29 hlasů, č. 26–55 nulu; v roce 2022 měla strana v okrsku 21 %.",
    "zjisteni": "…", "dukaz": "…", "jistota": 4, "dopad_kat": "Bez vlivu", "dopad": "…", "umysl": "…", "doporuceni": "…",
    "vyradit": false
  }
}
```
Povolené hodnoty `dopad_kat`: „Mění mandáty“, „Mění zvolené“, „Může změnit mandáty“, „Těsný výsledek“, „Bez vlivu“.

## Výstup pro zadavatele
Na konci stručně shrň: počet nálezů potvrzených / upravených / vyřazených, nálezy s vlivem na výsledek (s čísly) a podezření na chybu
detektoru (např. systematické falešné nálezy), které by se mělo opravit v kódu.

## Druhé kolo (nové typy nálezů)
Generátor byl po prvním kole doplněn o dva nové typy nálezů; v `findings_2026.json` je poznáte podle `stav_kontroly = "automaticky"`:
- `row:<OID>:<ZK>:<strana>` – **neúplně opsaný řádek kandidátů**: kandidáti č. 1–k mají zhruba stejně hlasů (lístky s křížkem u strany),
  další kandidáti do počtu mandátů mají nuly. Ověř vektor hlasů kandidátů (`hl` sloupce `HLASY_xx`), porovnej s druhým lístkem téhož okrsku
  a s rokem 2022; zvaž legitimní vysvětlení (křížek u strany + hlasy pro kandidáty jiných stran dává straně jen prvních M − k kandidátů;
  strana bez lístků s křížkem má jen preferenční hlasy). Simuluj dopad doplnění.
- `swap:<OID>:<ZK>:<a>:<b>` – **možná záměna hlasů dvou stran**: ověř, zda prohození odpovídá okolí i druhému lístku a roku 2022, nebo jde o místní vzorec.

Do existujícího `review/<slug>.json` **přidej** nové klíče; stávající záznamy ponech beze změny (soubor načti, doplň a zapiš celý).

## Obce s rozšířenou působností (ORP)
Od 12. 10. 2026 se stejná šablona počítá i pro sídla ORP (slug v `data/processed/units_2026.json`, `typ = "orp"`). Postup i formát jsou stejné,
navíc platí:
- Malé obce mají jen několik okrsků. Očekávání „podle sousedních okrsků“ je proto slabé – opírej se hlavně o vnitřní logiku zápisu
  (vektor hlasů kandidátů, `PL_HL_CELK ≤ PLAT_LISTKY × M`, druhý lístek, pokud existuje) a o rok 2022 (`load(2022)`).
- U překlepů (`typo:`) u **lídra kandidátky** nebo kandidáta s výraznou preferencí ověř, zda je náskok vidět i v ostatních okrscích obce
  a v roce 2022; pokud ano, jde o skutečnou preferenci → nález vyřaď (`"vyradit": true`).
- U „Mění mandáty“ vždy ověř, **proč** se mandáty mění (často posun 5% hranice jiné strany kvůli změně celkového počtu hlasů) a napiš to do `dopad`.
- Pokud obec nemá žádné nálezy, soubor nevytvářej.
